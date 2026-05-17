"""Faz SELECT em cada tabela gold via Trino para validar leitura."""

from __future__ import annotations

import os
import sys
import time

import httpx

TRINO_URL = os.environ.get("TRINO_URL", "http://localhost:8084")
TRINO_USER = os.environ.get("TRINO_USER", "admin")


def query(sql: str) -> tuple[bool, list, list, str]:
    headers = {"X-Trino-User": TRINO_USER, "Content-Type": "text/plain"}
    cols: list = []
    rows: list = []
    last_err = ""
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{TRINO_URL}/v1/statement", headers=headers, data=sql.encode())
        if r.status_code != 200:
            return False, cols, rows, f"HTTP {r.status_code}"
        data = r.json()
        while True:
            if "columns" in data and not cols:
                cols = [c["name"] for c in data["columns"]]
            if "data" in data:
                rows.extend(data["data"])
            err = data.get("error")
            if err:
                last_err = f"{err.get('errorName')}: {err.get('message')}"
            if not data.get("nextUri"):
                break
            r = client.get(data["nextUri"], headers=headers)
            if r.status_code != 200:
                return False, cols, rows, f"HTTP {r.status_code}"
            data = r.json()
            time.sleep(0.05)
    return (not last_err), cols, rows, last_err


def main() -> int:
    queries = [
        ("count dim_users", "SELECT count(*) FROM delta.gold.dim_users"),
        ("count dim_products", "SELECT count(*) FROM delta.gold.dim_products"),
        ("count fact_orders", "SELECT count(*) FROM delta.gold.fact_orders"),
        ("count fact_payments", "SELECT count(*) FROM delta.gold.fact_payments"),
        ("count notifications_daily", "SELECT count(*) FROM delta.gold.notifications_daily"),
        ("count product_metrics_daily", "SELECT count(*) FROM delta.gold.product_metrics_daily"),
        ("count seller_metrics_daily", "SELECT count(*) FROM delta.gold.seller_metrics_daily"),
        ("count customer_rfm", "SELECT count(*) FROM delta.gold.customer_rfm"),
        (
            "fact_orders sample",
            "SELECT order_id, buyer_id, product_id, quantity, total_amount, status, "
            "created_at FROM delta.gold.fact_orders ORDER BY created_at DESC LIMIT 5",
        ),
        (
            "gmv by date",
            "SELECT CAST(created_at AS date) AS d, COUNT(*) o, SUM(total_amount) gmv "
            "FROM delta.gold.fact_orders GROUP BY 1 ORDER BY 1",
        ),
    ]
    for name, sql in queries:
        ok, cols, rows, err = query(sql)
        print(f"\n=== {name} ===  ok={ok}")
        if err:
            print(f"  err: {err}")
        if cols:
            print(f"  cols: {cols}")
        for r in rows[:8]:
            print(f"  row: {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
