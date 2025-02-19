import logging

import pytest
from faker import Faker

from bigquery_funcs._types import LatLon
from bigquery_funcs.queries import make_unnest_cte, structify

from . import logging_config
from .utils import are_same_parsed_query, is_valid_query

logger = logging.getLogger(__name__)


@pytest.fixture
def known_lat_lons() -> tuple[LatLon, ...]:
    ## Test with a known set
    return tuple(
        (
            LatLon(2, 4),
            LatLon(1, 3),
        )
    )


@pytest.fixture
def rand_lat_lons() -> tuple[LatLon, ...]:
    fake = Faker()
    coords = tuple(
        LatLon(lat=float(lat), lon=float(lon))
        for lat, lon in (fake.location_on_land(coords_only=True) for _ in range(10))
    )
    return coords


def test_structify(
    rand_lat_lons: tuple[LatLon, ...], known_lat_lons: tuple[LatLon, ...]
) -> None:
    ## Test with a known set
    aliases = ("hello", "world")
    struct_tuple1 = structify(data=known_lat_lons, aliases=aliases)
    assert struct_tuple1 == (
        "STRUCT(2 AS hello, 4 AS world)",
        "STRUCT(1 AS hello, 3 AS world)",
    )

    ## Test with random set that it produces a valid query in bigquery
    struct_tuple2 = structify(data=rand_lat_lons, aliases=aliases)
    query_str = f"""SELECT {",".join(aliases)} FROM UNNEST([{struct_tuple2}])"""
    is_valid, error_msg = is_valid_query(query_str)
    assert is_valid, error_msg


def test_make_unnest_cte_query(
    rand_lat_lons: tuple[LatLon, ...],
    known_lat_lons: tuple[LatLon, ...],
) -> None:
    cte_name = "latlon_cte"
    aliases = ["point"]

    ## Test with a known set of points
    result_cte = make_unnest_cte(known_lat_lons, cte_name, aliases, as_points=True)
    expected_cte = f"""
        {cte_name} AS (
            SELECT * 
            FROM UNNEST([
                ST_GEOGPOINT(4, 2),
                ST_GEOGPOINT(3, 1)
            ]) {aliases[0]}
        )
    """.strip()

    assert are_same_parsed_query(
        query1=f"WITH {result_cte} SELECT * FROM {cte_name}",
        query2=f"WITH {expected_cte} SELECT * FROM {cte_name}",
    ), f"result: {result_cte}, expected: {expected_cte}"

    # Test with random set that it produces a valid query in bigquery
    result_cte = make_unnest_cte(rand_lat_lons, cte_name, aliases, as_points=True)
    is_valid, error_msg = is_valid_query(f"WITH {result_cte} SELECT * FROM {cte_name}")
    assert is_valid, error_msg

    # Test with as_points off
    result_cte = make_unnest_cte(
        known_lat_lons, cte_name, aliases=["lat", "lon"], as_points=False
    )
    expected_cte = f"""
        {cte_name} AS (
            SELECT lat, lon 
            FROM UNNEST([
                STRUCT(2 AS lat, 4 AS lon),
                STRUCT(1 AS lat, 3 AS lon)
            ])
        )
    """.strip()

    assert are_same_parsed_query(
        query1=f"WITH {result_cte} SELECT * FROM {cte_name}",
        query2=f"WITH {expected_cte} SELECT * FROM {cte_name}",
    ), f"result: {result_cte}, expected: {expected_cte}"

    # Test with random set that it produces a valid query in bigquery
    result_cte = make_unnest_cte(
        rand_lat_lons, cte_name, aliases=["lat", "lon"], as_points=False
    )
    is_valid, error_msg = is_valid_query(f"WITH {result_cte} SELECT * FROM {cte_name}")
    assert is_valid, error_msg


logging_config
