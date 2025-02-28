import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

import google.cloud.bigquery as bigquery
from google.cloud.bigquery.job import _AsyncJob

from ._types import DateTimeFormatter, FullTableID, JsonRows, LatLon


@dataclass
class BigQueryTable:
    GOOGLE_PROJECT_ID: str
    GOOGLE_DATASET_ID: str
    GOOGLE_TABLE_ID: str
    bq_client: bigquery.Client

    @property
    def time_zone(self) -> dt.timezone:
        return dt.timezone.utc

    @property
    def datetime_formatter(self) -> DateTimeFormatter:
        return lambda x: x.isoformat()

    @property
    def full_table_id(self) -> str:
        return f"{self.GOOGLE_PROJECT_ID.lower()}.{self.GOOGLE_DATASET_ID.lower()}.{self.GOOGLE_TABLE_ID.lower()}"

    @property
    def table(self) -> bigquery.Table:
        table_ref = self.bq_client.dataset(self.GOOGLE_DATASET_ID).table(
            self.GOOGLE_TABLE_ID
        )
        table = self.bq_client.get_table(table_ref)
        return table

    @property
    def table_schema(self) -> list[bigquery.SchemaField]:
        return self.table.schema  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]

    def modify_schema(self, new_schema: list[bigquery.SchemaField]) -> None:
        self.table.schema = new_schema
        _ = self.bq_client.update_table(self.table, ["schema"])

    @classmethod
    def from_full_table_id(
        cls, id: FullTableID, bq_client: bigquery.Client
    ) -> "BigQueryTable":
        try:
            project_id, dataset_id, table_id = id.split(".")
        except ValueError:
            raise ValueError(f"Failed to split table id {id}")

        table = BigQueryTable(
            GOOGLE_PROJECT_ID=project_id,
            GOOGLE_DATASET_ID=dataset_id,
            GOOGLE_TABLE_ID=table_id,
            bq_client=bq_client,
        )

        return table

    def load_rows(
        self,
        data: JsonRows,
        add_timestamp: bool = True,
    ) -> _AsyncJob:
        if add_timestamp:
            date_added = self.datetime_formatter(dt.datetime.now(self.time_zone))
            for row in data:
                row["date_added"] = date_added

        job_config = bigquery.LoadJobConfig(schema=self.table_schema)
        job = self.bq_client.load_table_from_json(
            json_rows=data, destination=self.table, job_config=job_config
        )
        result = job.result()
        return result


@dataclass
class GeoSpatialJoinArgs:
    coords: Sequence[LatLon]
    geo_lookup_table: BigQueryTable
    lat_column: str = "lat"
    lon_column: str = "lon"
    new_coords_point_alias: str = "new_coords"
    new_coords_cte_name: str = "new_coords_cte"
    geo_lookup_table_point_alias: str = (
        "lonlat_geo"  # alias to combine lat and lon column
    )
    geo_lookup_table_cte_name: str = "lookup_coords"
    country_column: str = "country"
    city_column: str = "city"
    state_column: str = "state"

    @classmethod
    def defaults(cls) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
        return {field.name: field.default for field in fields(GeoSpatialJoinArgs)}
