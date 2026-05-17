"""Acesso ao Trino para puxar features de inferencia em tempo real."""
from __future__ import annotations

import os
from typing import Any

import pandas as pd
from loguru import logger
from trino.dbapi import connect


def _conn():
    return connect(
        host=os.getenv("TRINO_HOST", "trino"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        user=os.getenv("TRINO_USER", "ml-api"),
        catalog="delta",
        schema="gold_ml",
    )


def query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    try:
        with _conn() as c:
            cur = c.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    except Exception as exc:
        logger.warning(f"[trino] query failed: {exc}")
        return pd.DataFrame()


def _coerce_id(buyer_id: str) -> str:
    """Devolve representacao SQL segura para buyer_id (bigint quando numerico)."""
    s = str(buyer_id).strip()
    if s.lstrip("-").isdigit():
        return s
    return f"'{s}'"


def user_features_row(buyer_id: str) -> dict[str, Any] | None:
    bid = _coerce_id(buyer_id)
    df = query(
        f"SELECT recency_days, frequency_per_week, monetary, avg_order_value, tenure_days, "
        f"payment_fail_rate, payments_total, distinct_products "
        f"FROM delta.gold_ml.user_features WHERE buyer_id = {bid}"
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def user_payment_history(buyer_id: str) -> dict[str, Any] | None:
    bid = _coerce_id(buyer_id)
    df = query(
        f"SELECT buyer_pay_count, buyer_avg_amount, buyer_fail_rate_hist "
        f"FROM delta.gold_ml.payment_dataset WHERE buyer_id = {bid} "
        f"ORDER BY created_at DESC LIMIT 1"
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def latest_demand_window(seq_len: int = 7) -> pd.DataFrame:
    df = query(
        f"SELECT ds, orders, gmv FROM delta.gold_ml.daily_demand "
        f"ORDER BY ds DESC LIMIT {seq_len}"
    )
    if df.empty:
        return df
    return df.sort_values("ds").reset_index(drop=True)


def product_lookup(product_ids: list[str]) -> pd.DataFrame:
    if not product_ids:
        return pd.DataFrame()
    parts = []
    for p in product_ids:
        s = str(p).strip()
        parts.append(s if s.lstrip("-").isdigit() else f"'{s}'")
    quoted = ",".join(parts)
    return query(
        f"SELECT product_id, title, category, price FROM delta.gold_ml.product_features "
        f"WHERE product_id IN ({quoted})"
    )
