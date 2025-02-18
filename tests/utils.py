import os

import sqlglot
from sqlglot import transpile
from sqlglot.dialects.bigquery import BigQuery
from sqlglot.errors import ParseError


def is_valid_query(query_str: str) -> tuple[bool, str]:
    try:
        _ = transpile(sql=query_str, read=BigQuery)
        return True, "(valid_syntax)"
    except ParseError as e:
        return False, str(e)


def del_vars(monkeypatch, vars: list[str]):
    """Utility to remove environmental variables in a pytest test.
    Requires passing the pytest 'monkeypatch' fixture"""

    # Clear env vars before testing
    for var in vars:
        monkeypatch.delenv(var, raising=False)
    assert not any(os.getenv(var, None) for var in vars)  # ensure that deletion worked


def are_same_parsed_query(query1: str, query2: str):
    q1_parsed = sqlglot.parse_one(query1).sql()
    q2_parsed = sqlglot.parse_one(query2).sql()
    return q1_parsed == q2_parsed
