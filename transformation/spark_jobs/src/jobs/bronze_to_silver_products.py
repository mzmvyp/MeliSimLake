"""Job Bronze → Silver: tabela products (SCD Type 2)."""

from __future__ import annotations

import argparse
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, trim
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from transformation.spark_jobs.src.lib.delta_utils import merge_scd2
from transformation.spark_jobs.src.lib.spark_session import get_spark_session

BRONZE_PATH: Final[str] = "s3a://bronze/cdc/products/"
SILVER_PATH: Final[str] = "s3a://silver/products/"

PRODUCT_PAYLOAD_SCHEMA = StructType(
    [
        StructField("product_id", StringType(), True),
        StructField("title", StringType(), True),
        StructField("description", StringType(), True),
        StructField("category_id", StringType(), True),
        StructField("brand", StringType(), True),
        StructField("sku", StringType(), True),
        StructField("price", DecimalType(15, 2), True),
        StructField("stock_quantity", IntegerType(), True),
        StructField("status", StringType(), True),
        StructField("created_at", StringType(), True),
        StructField("updated_at", StringType(), True),
    ]
)

BUSINESS_KEY_COLUMNS: Final[list[str]] = [
    "title", "price", "stock_quantity", "status", "category_id",
]


def _read_bronze(spark: SparkSession, date: str | None) -> DataFrame:
    path = f"{BRONZE_PATH}event_date={date}/" if date else BRONZE_PATH
    raw = spark.read.parquet(path)
    filtered = raw.filter(col("cdc_op").isin(["c", "u", "r"]))
    parsed = filtered.withColumn(
        "payload", from_json(col("payload_after"), PRODUCT_PAYLOAD_SCHEMA)
    )
    return parsed.select(
        col("payload.product_id").alias("product_id"),
        trim(col("payload.title")).alias("title"),
        col("payload.description").alias("description"),
        col("payload.category_id").alias("category_id"),
        trim(col("payload.brand")).alias("brand"),
        col("payload.sku").alias("sku"),
        col("payload.price").alias("price"),
        col("payload.stock_quantity").alias("stock_quantity"),
        col("payload.status").alias("status"),
        to_timestamp(col("payload.created_at")).alias("created_at"),
        to_timestamp(col("payload.updated_at")).alias("updated_at"),
    ).filter(col("product_id").isNotNull())


def run(date: str | None = None) -> None:
    """Executa job Bronze → Silver para products."""
    spark = get_spark_session("melisimlake_bronze_to_silver_products")
    spark.sparkContext.setLogLevel("WARN")
    logger.info("Iniciando Bronze→Silver products", extra={"date": date})
    df = _read_bronze(spark, date)
    count = df.count()
    if count == 0:
        logger.warning("Nenhum registro", extra={"date": date})
        return
    merge_scd2(spark, SILVER_PATH, df, "product_id", BUSINESS_KEY_COLUMNS)
    logger.info("Silver products atualizado", extra={"rows": count})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    run(args.date)


if __name__ == "__main__":
    main(sys.argv[1:])
