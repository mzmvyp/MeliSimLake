"""Cliente Trino simples para puxar features ML como pandas DataFrame."""
from __future__ import annotations

import os

import pandas as pd
from trino.dbapi import connect


def _conn():
    host = os.getenv("TRINO_HOST", "trino")
    port = int(os.getenv("TRINO_PORT", "8080"))
    user = os.getenv("TRINO_USER", "ml-trainer")
    catalog = os.getenv("TRINO_CATALOG", "delta")
    schema = os.getenv("TRINO_SCHEMA", "gold_ml")
    return connect(host=host, port=port, user=user, catalog=catalog, schema=schema)


def query(sql: str) -> pd.DataFrame:
    with _conn() as c:
        cur = c.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)
