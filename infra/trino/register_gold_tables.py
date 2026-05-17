"""Registra cada tabela Delta materializada em s3a://delta-metastore/catalog/gold/<t>
no catalogo Trino `delta`, schema `gold`. Idempotente: cria schema se nao existir
e ignora 'TableAlreadyExistsException' nos register_table calls.

Roda no host (necessita Python + httpx). Pode ser invocado via:
    docker exec -it melisimlake-batch-runner python /app/register_gold_tables.py
ou direto do host.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Final

import httpx

TRINO_URL = os.environ.get("TRINO_URL", "http://localhost:8084")
TRINO_USER = os.environ.get("TRINO_USER", "admin")
GOLD_TABLES: Final[list[str]] = [
    "dim_users",
    "dim_products",
    "fact_orders",
    "fact_payments",
    "fact_stock_alerts",
    "notifications_daily",
    "product_metrics_daily",
    "seller_metrics_daily",
    "customer_rfm",
]

GOLD_ML_TABLES: Final[list[str]] = [
    "user_features",
    "product_features",
    "churn_dataset",
    "payment_dataset",
    "daily_demand",
    "user_item_matrix",
]


def run_query(sql: str) -> tuple[bool, str]:
    """Submete uma query no Trino e drena ate completar. Retorna (ok, last_error)."""
    headers = {"X-Trino-User": TRINO_USER, "Content-Type": "text/plain"}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{TRINO_URL}/v1/statement", headers=headers, data=sql.encode())
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:300]}"
        data = r.json()
        last_err = ""
        while True:
            err = data.get("error")
            if err:
                last_err = f"{err.get('errorName')}: {err.get('message')}"
            next_uri = data.get("nextUri")
            if not next_uri:
                break
            r = client.get(next_uri, headers=headers)
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}: {r.text[:300]}"
            data = r.json()
            time.sleep(0.05)
        if last_err:
            return False, last_err
        return True, ""


def _create_schema(schema: str) -> bool:
    ok, err = run_query(
        f"CREATE SCHEMA IF NOT EXISTS delta.{schema} "
        f"WITH (location = 's3a://delta-metastore/catalog/{schema}')"
    )
    if not ok:
        print(f"[schema] {schema} FAIL: {err}")
        return False
    print(f"[schema] delta.{schema} OK")
    return True


def _register(schema: str, tables: list[str]) -> None:
    for t in tables:
        location = f"s3a://delta-metastore/catalog/{schema}/{t}"
        sql = (
            f"CALL delta.system.register_table("
            f"schema_name => '{schema}', "
            f"table_name => '{t}', "
            f"table_location => '{location}')"
        )
        ok, err = run_query(sql)
        if ok:
            print(f"[register] {schema}.{t} OK")
        elif "already exists" in err.lower() or "alreadyexists" in err.lower():
            print(f"[register] {schema}.{t} already-registered (ok)")
        else:
            print(f"[register] {schema}.{t} FAIL: {err}")


def main() -> int:
    if not _create_schema("gold"):
        return 1
    if not _create_schema("gold_ml"):
        return 1
    _register("gold", GOLD_TABLES)
    _register("gold_ml", GOLD_ML_TABLES)
    print("---listing gold---")
    ok, _ = run_query("SHOW TABLES FROM delta.gold")
    print(f"show: ok={ok}")
    print("---listing gold_ml---")
    ok, _ = run_query("SHOW TABLES FROM delta.gold_ml")
    print(f"show: ok={ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
