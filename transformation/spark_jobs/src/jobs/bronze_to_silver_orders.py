"""Job Bronze → Silver: tabela orders (append-only, sem SCD2)."""

from __future__ import annotations

import argparse
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from transformation.spark_jobs.src.lib.delta_utils import upsert_append
from transformation.spark_jobs.src.lib.spark_session import get_spark_session

BRONZE_PATH: Final[str] = "s3a://bronze/cdc/orders/"
SILVER_PATH: Final[str] = "s3a://silver/orders/"

ORDER_PAYLOAD_SCHEMA = StructType(
    [
        StructField("order_id", StringType(), True),
        StructField("user_id", StringType(), True),
        StructField("status", StringType(), True),
        StructField("total_amount", DecimalType(15, 2), True),
        StructField("currency", StringType(), True),
        StructField("payment_method", StringType(), True),
        StructField("shipping_address_id", StringType(), True),
        StructField("created_at", StringType(), True),
        StructField("updated_at", StringType(), True),
        StructField("completed_at", StringType(), True),
        StructField("items_count", IntegerType(), True),
    ]
)


def _read_bronze(spark: SparkSession, date: str | None) -> DataFrame:
    path = f"{BRONZE_PATH}event_date={date}/" if date else BRONZE_PATH
    raw = spark.read.parquet(path)
    parsed = raw.withColumn("payload", from_json(col("payload_after"), ORDER_PAYLOAD_SCHEMA))
    return parsed.select(
        col("payload.order_id").alias("order_id"),
        col("payload.user_id").alias("user_id"),
        col("payload.status").alias("status"),
        col("payload.total_amount").alias("total_amount"),
        col("payload.currency").alias("currency"),
        col("payload.payment_method").alias("payment_method"),
        col("payload.shipping_address_id").alias("shipping_address_id"),
        to_timestamp(col("payload.created_at")).alias("created_at"),
        to_timestamp(col("payload.updated_at")).alias("updated_at"),
        to_timestamp(col("payload.completed_at")).alias("completed_at"),
        col("payload.items_count").alias("items_count"),
    ).filter(col("order_id").isNotNull()).dropDuplicates(["order_id"])


def run(date: str | None = None) -> None:
    """Executa job Bronze → Silver para orders."""
    spark = get_spark_session("melisimlake_bronze_to_silver_orders")
    spark.sparkContext.setLogLevel("WARN")
    logger.info("Iniciando Bronze→Silver orders", extra={"date": date})
    df = _read_bronze(spark, date)
    count = df.count()
    if count == 0:
        logger.warning("Nenhum registro", extra={"date": date})
        return
    upsert_append(spark, SILVER_PATH, df, "order_id", "updated_at")
    logger.info("Silver orders atualizado", extra={"rows": count})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    run(args.date)


if __name__ == "__main__":
    main(sys.argv[1:])
