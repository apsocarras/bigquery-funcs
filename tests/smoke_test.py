PROJECT_ID = "my-project"
DATASET_ID = "my-dataset"
TABLE_ID = "my-table"


from bigquery_funcs.auth import ApplicationCredentials

value_error = False
try:
    creds = ApplicationCredentials.from_env(secret_context="local", env_path=None)
except ValueError:
    value_error = True

assert value_error

from bigquery_funcs.queries import list_datasets_query

query_str = list_datasets_query(project_id=PROJECT_ID)
expected = f"""SELECT schema_name FROM {PROJECT_ID}.`region-us`.`INFORMATION_SCHEMA.SCHEMATA`;"""
assert (
    query_str
    == f"""SELECT schema_name FROM {PROJECT_ID}.`region-us`.`INFORMATION_SCHEMA.SCHEMATA`;"""
), {"given": query_str, "expected": expected}

from bigquery_funcs.models import BigQueryTable

my_table = BigQueryTable(
    GOOGLE_PROJECT_ID=PROJECT_ID,
    GOOGLE_DATASET_ID="my-dataset",
    GOOGLE_TABLE_ID="my-table",
)
assert my_table.full_table_id == f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
