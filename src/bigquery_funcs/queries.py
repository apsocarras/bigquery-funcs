import warnings
from collections.abc import Sequence
from dataclasses import asdict
from typing import Never, cast, overload

from functag import warn_str
from google.cloud.bigquery.exceptions import BigQueryError
from jinja2 import Template

from bigquery_funcs._types import LatLon, LonLat, MatchedCoord, OrderedPairs
from bigquery_funcs.models import BigQueryTable, GeoSpatialJoinArgs


class SchemaError(BigQueryError):
    pass


@overload
def structify(data: OrderedPairs, aliases: str) -> Never: ...
@overload
def structify(data: OrderedPairs, aliases: Sequence[str]) -> tuple[str, ...]: ...
@warn_str("aliases")
def structify(
    data: OrderedPairs,
    aliases: Sequence[str],
) -> tuple[str, ...]:
    """
    Convert data into a list of `STRUCT` statements with new aliases to use.
    Aliases are matched to data values by order of appearance.
    """
    if any(incorrect_lengths := [str(d) for d in data if len(d) != len(aliases)]):
        e = ValueError(
            f"Each collection in data must match the number of aliases ({len(aliases)})"
        )
        e.add_note(", ".join(incorrect_lengths))
        raise e

    return tuple(
        "STRUCT("
        + ", ".join([f"{val} AS {alias}" for val, alias in zip(d, aliases)])
        + ")"
        for d in data
    )


def pointify(data: Sequence[LatLon] | Sequence[LonLat]) -> tuple[str, ...]:
    return tuple(str(f"ST_GEOGPOINT({d.lon}, {d.lat})") for d in data)


@warn_str("aliases")
def make_unnest_cte(
    data: OrderedPairs,
    cte_name: str,
    aliases: Sequence[str],
    value_clause_indent: int = 12,
    as_points: bool = False,
) -> str:
    """Take sequences of data and make into a CTE"""
    if as_points and all(isinstance(d, LatLon) for d in data):
        data = cast(Sequence[LatLon], data)
        indent = ", \n" + " " * value_clause_indent
        point_strs = pointify(data)

        template_str = """
        {{ cte_name }} AS (
            SELECT *
            FROM UNNEST([
                {%- for value in point_strs %}
                {{ value }}{% if not loop.last %}, {% endif %}{%- endfor %}
            ]) AS new_coords
        )
        """
        template = Template(template_str.strip())
        rendered_query = template.render(
            cte_name=cte_name, aliases=aliases, point_strs=point_strs
        )
        return rendered_query
    else:
        if not aliases:
            raise ValueError(
                "Must provide aliases unless processing a special type (LatLon)"
            )
        template_str = """
        {{ cte_name }} AS (
            SELECT {{ aliases | join(', ')}}
            FROM UNNEST([
                {% for value in struct_values %}
                    {{ indent }}{{ value }}{% if not loop.last %}, {% endif %}
                {% endfor %}            
            ])
        )
        """
        struct_values: tuple[str, ...] = structify(data=data, aliases=aliases)
        indent = " " * value_clause_indent

        template = Template(template_str.strip())
        rendered_query = template.render(
            cte_name=cte_name,
            aliases=aliases,
            struct_values=struct_values,
            indent=indent,
        )

        return rendered_query


@warn_str("aliases")
def make_filter_query(
    data: OrderedPairs,
    aliases: Sequence[str],
    cte_name: str,
    table: BigQueryTable,
    cte_alias: str = "b",
    table_alias: str = "a",
) -> str:
    cte = make_unnest_cte(
        data=data, cte_name=cte_name, aliases=aliases, as_points=False
    )
    select_columns = ", ".join([f"{cte_alias}.{alias}" for alias in aliases])
    join_conditions = " AND ".join(
        [f"{table_alias}.{alias} = {cte_alias}.{alias}" for alias in aliases]
    )
    where_conditions = " AND ".join(
        [f"{table_alias}.{alias} IS NULL" for alias in aliases]
    )
    query_str = f"""
    WITH {cte}

    SELECT {select_columns}
    FROM {cte_name} as {cte_alias}
    LEFT JOIN `{table.full_table_id}` as {table_alias} 
    ON {join_conditions}  
    WHERE {where_conditions}
    """
    return query_str


def filter_coords(
    coords: Sequence[LatLon],
    geo_lookup_table: BigQueryTable,
    lat_column: str = "lat",
    lon_column: str = "lon",
) -> tuple[LatLon, ...]:
    lon_lat_ordered = [LonLat(d.lon, d.lat) for d in coords]
    query_str = make_filter_query(
        data=lon_lat_ordered,
        aliases=[lon_column, lat_column],
        cte_name="new_lon_lats",
        table=geo_lookup_table,
    )
    query_job = geo_lookup_table._bq_client.query(query_str)
    results = query_job.result()
    new_lat_lons = tuple(
        LatLon(lat=row[lat_column], lon=row[lon_column]) for row in results
    )
    coords_to_lookup = new_lat_lons

    return coords_to_lookup


def make_geospatial_join_query(args: GeoSpatialJoinArgs) -> str:
    if any(
        missing_cols := (
            x
            for x in (args.lat_column, args.lon_column)
            if x in args.geo_lookup_table.schema
        )
    ):
        raise SchemaError(
            f"Geolookup table `{args.geo_lookup_table.full_table_id}` is missing {', '.join(missing_cols)}"
        )

    new_point, new_cte_name = args.new_coords_point_alias, args.new_coords_cte_name
    new_coord_cte_query = make_unnest_cte(
        data=args.coords,
        cte_name=new_cte_name,
        aliases=(new_point,),
        as_points=True,
    )

    lookup_point, lookup_cte_name = (
        args.geo_lookup_table_point_alias,
        args.geo_lookup_table_cte_name,
    )
    lookup_cte_query = f"""
    {lookup_cte_name} AS (
        SELECT *, ST_GEOGPOINT({args.lon_column}, {args.lat_column}) {lookup_point}
        FROM `{args.geo_lookup_table.full_table_id}`
    )
    """

    query_str = f"""
    WITH {new_coord_cte_query}, 
    {lookup_cte_query} 

    SELECT {new_point}, {args.city_column}, {args.state_column}, {args.country_column}
    FROM (
        SELECT loc.*, {new_point}
        FROM (
            SELECT ST_ASTEXT({new_point}) {new_point},
            ANY_VALUE({new_point}) geop, 
            ARRAY_AGG(
                STRUCT({args.city_column}, {args.state_column}, {args.country_column})
                ORDER BY ST_DISTANCE({new_cte_name}.{new_point}, {lookup_cte_name}.{lookup_point}) LIMIT 1
            )[SAFE_OFFSET(0)] loc
            FROM {new_cte_name}, {lookup_cte_name}
            WHERE ST_DWITHIN({new_cte_name}.{new_point}, {lookup_cte_name}.{lookup_point}, 100000)
            GROUP BY {new_point}
        )
    )
    GROUP BY {new_point}, {args.city_column}, {args.state_column}, {args.country_column}
    """

    return query_str


def join_geospatial(
    args: GeoSpatialJoinArgs, filter_first: bool = True
) -> list[MatchedCoord]:
    if filter_first:
        filtered_coords = filter_coords(
            coords=args.coords,
            geo_lookup_table=args.geo_lookup_table,
            lat_column=args.lat_column,
            lon_column=args.lon_column,
        )
        old_args = asdict(args)
        old_args["coords"] = filtered_coords
        coords_to_lookup = GeoSpatialJoinArgs(**old_args)
    else:
        coords_to_lookup = args

    query_str = make_geospatial_join_query(coords_to_lookup)
    query_job = args.geo_lookup_table.bq_client.query(query_str)
    results = query_job.result()

    return [
        MatchedCoord(
            given_coord=coord,
            matched_coord=LatLon(lat=row[args.lat_column], lon=row[args.lon_column]),
            city_match=row[args.city_column],
            state_match=row[args.state_column],
            country_match=row[args.country_column],
        )
        for coord, row in zip(coords_to_lookup.coords, results)
    ]


def search_column_in_dataset_query(
    project_id: str, dataset_id: str, columns: Sequence[str], exact: bool = False
) -> str:
    """
    Query to search for all tables in a dataset which contain a given column or set of columns.
    """

    column_like_condition = " OR ".join(
        [
            "column_name " + (f'LIKE "%{col}%"' if not exact else f'= "{col}"')
            for col in (columns if not isinstance(columns, str) else [columns])
        ]
    )

    query_str = """
    SELECT 
        column_name,
        ARRAY_AGG(DISTINCT table_name ORDER BY table_name) AS table_names
    FROM `{{ project_id }}.{{ dataset_id }}.INFORMATION_SCHEMA.COLUMNS`
    WHERE {{ column_like_condition }}
    GROUP BY column_name
    ORDER BY column_name ASC;
    """

    template = Template(query_str.strip())
    rendered_template = template.render(
        project_id=project_id,
        dataset_id=dataset_id,
        column_like_condition=column_like_condition,
    )

    return rendered_template


def list_datasets_query(
    project_id: str,
    region: str = "us",
) -> str:
    """
    >>> list_datasets_query("my-report")
    SELECT schema_name FROM my-report.`region-us`.`INFORMATION_SCHEMA.SCHEMATA`;
    """
    query_str = f"""SELECT schema_name FROM {project_id}.`region-{region}`.`INFORMATION_SCHEMA.SCHEMATA`;"""
    return query_str


def display_query_markdown(query_str: str) -> None:
    try:
        from IPython.display import Markdown, display

        _ = display(Markdown(f"```sql\n{query_str}\n```"))
    except ImportError:
        warnings.warn("IPython is not importable -- check your installation.")
        return None
