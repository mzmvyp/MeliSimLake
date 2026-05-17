"""Schemas Avro e Spark para os tópicos de eventos do Melisim."""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

CLICK_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), True),
        StructField("session_id", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("page_type", StringType(), True),
        StructField("position", LongType(), True),
        StructField("ts", TimestampType(), False),
    ]
)

CART_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), True),
        StructField("session_id", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("quantity", LongType(), True),
        StructField("unit_price", DoubleType(), True),
        StructField("action", StringType(), True),
        StructField("ts", TimestampType(), False),
    ]
)

SEARCH_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), True),
        StructField("session_id", StringType(), True),
        StructField("query", StringType(), True),
        StructField("results_count", LongType(), True),
        StructField("category_filter", StringType(), True),
        StructField("ts", TimestampType(), False),
    ]
)

PURCHASE_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("user_id", StringType(), False),
        StructField("session_id", StringType(), True),
        StructField("order_id", StringType(), False),
        StructField("total_amount", DoubleType(), False),
        StructField("items_count", LongType(), True),
        StructField("payment_method", StringType(), True),
        StructField("ts", TimestampType(), False),
    ]
)

TOPIC_SCHEMAS: dict[str, StructType] = {
    "events.clicks": CLICK_SCHEMA,
    "events.cart": CART_SCHEMA,
    "events.search": SEARCH_SCHEMA,
    "events.purchase": PURCHASE_SCHEMA,
}
