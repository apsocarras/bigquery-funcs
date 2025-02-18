from unittest.mock import MagicMock

import google.cloud.bigquery as bigquery

from bigquery_funcs._types import LatLon
from bigquery_funcs.auth import ApplicationCredentials
from bigquery_funcs.models import BigQueryTable
from bigquery_funcs.queries import list_datasets_query, pointify

PROJECT_ID = "my-project"
DATASET_ID = "my-dataset"
TABLE_ID = "my-table"


## AUTH
value_error = False
try:
    creds = ApplicationCredentials.from_env(secret_context="local", env_path=None)
except ValueError:
    value_error = True

assert value_error

## QUERIES
query_str = list_datasets_query(project_id=PROJECT_ID)
expected = f"""SELECT schema_name FROM {PROJECT_ID}.`region-us`.`INFORMATION_SCHEMA.SCHEMATA`;"""
assert query_str == expected, {"given": query_str, "expected": expected}

point_strings = pointify([LatLon(1, 3), LatLon(2, 4)])
assert point_strings == ("ST_GEOGPOINT(3, 1)", "ST_GEOGPOINT(4, 2)")

## MODELS
client = MagicMock(bigquery.Client)
my_table = BigQueryTable(
    GOOGLE_PROJECT_ID=PROJECT_ID,
    GOOGLE_DATASET_ID="my-dataset",
    GOOGLE_TABLE_ID="my-table",
    _bq_client=client,
)
assert my_table.full_table_id == f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
