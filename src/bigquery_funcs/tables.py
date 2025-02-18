from dataclasses import dataclass
from typing import Sequence

import google.cloud.bigquery as bigquery

from .auth import SecretSet


@dataclass
class BigQueryTable(SecretSet):
    GOOGLE_PROJECT_ID: str
    GOOGLE_DATASET_ID: str
    GOOGLE_TABLE_ID: str

    # _ <- tells SecretSet to ignore this field
    _bq_client: bigquery.Client = bigquery.Client()

    @property
    def full_table_id(self) -> str:
        return f"{self.GOOGLE_PROJECT_ID.lower()}.{self.GOOGLE_DATASET_ID.lower()}.{self.GOOGLE_TABLE_ID.lower()}"

    @property
    def table(self) -> bigquery.Table:
        table_ref = self._bq_client.dataset(self.GOOGLE_DATASET_ID).table(
            self.GOOGLE_TABLE_ID
        )
        table = self._bq_client.get_table(table_ref)
        return table

    @property
    def schema(self) -> list[bigquery.SchemaField]:
        return self.table.schema

    def modify_schema(self, new_schema: list[bigquery.SchemaField]) -> None:
        self.table.schema = new_schema
        self._bq_client.update_table(self.table, ["schema"])

    @property
    def bq_client(self):
        return self._bq_client


