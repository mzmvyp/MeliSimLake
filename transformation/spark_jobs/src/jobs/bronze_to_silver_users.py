"""Job Bronze → Silver: tabela users (SCD Type 2)."""

from __future__ import annotations

import argparse
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    col,
    from_json,
    lower,
    to_timestamp,
    trim,
    when,
)
from pyspark.sql.types import StringType, StructField, StructType, TimestampType

from transformation.spark_jobs.src.lib.delta_utils import merge_scd2
from transformation.spark_jobs.src.lib.schemas import SILVER_USERS_SCHEMA
from transformation.spark_jobs.src.lib.spark_session import get_spark_session

BRONZE_PATH: Final[str] = "s3a://bronze/cdc/users/"
SILVER_PATH: Final[str] = "s3a://silver/users/"

USER_PAYLOAD_SCHEMA = StructType(
    [
        StructField("user_id", StringType(), True),
        StructField("email", StringType(), True),
        StructField("name", StringType(), True),
        StructField("phone", StringType(), True),
        StructField("document_type", StringType(), True),
        StructField("document_number", StringType(), True),
        StructField("birth_date", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("status", StringType(), True),
        StructField("created_at", StringType(), True),
        StructField("updated_at", StringType(), True),
    ]
)

BUSINESS_KEY_COLUMNS: Final[list[str]] = [
    "email", "name", "phone", "document_number", "status",
]


def _read_bronze(spark: SparkSession, date: str | None) -> DataFrame:
    """Lê Parquet da camada Bronze.

    Args:
        spark: SparkSession ativa.
        date: Partição de data YYYY-MM-DD (None = todos).

    Returns:
        DataFrame com payload_after parseado.
    """
    path = f"{BRONZE_PATH}event_date={date}/" if date else BRONZE_PATH
    raw = spark.read.parquet(path)

    # Filtra apenas inserts e updates (não deletes para SCD2)
    filtered = raw.filter(col("cdc_op").isin(["c", "u", "r"]))

    parsed = filtered.withColumn(
        "payload", from_json(col("payload_after"), USER_PAYLOAD_SCHEMA)
    )

    return parsed.select(
        col("payload.user_id").alias("user_id"),
        lower(trim(col("payload.email"))).alias("email"),
        trim(col("payload.name")).alias("name"),
        trim(col("payload.phone")).alias("phone"),
        col("payload.document_type").alias("document_type"),
        col("payload.document_number").alias("document_number"),
        col("payload.birth_date").alias("birth_date"),
        col("payload.gender").alias("gender"),
        when(col("payload.status").isNull(), "unknown")
        .otherwise(col("payload.status"))
        .alias("status"),
        to_timestamp(col("payload.created_at")).alias("created_at"),
        to_timestamp(col("payload.updated_at")).alias("updated_at"),
    ).filter(col("user_id").isNotNull())


def run(date: str | None = None) -> None:
    """Executa job Bronze → Silver para users.

    Args:
        date: Partição de data (None = reprocessa tudo).
    """
    spark = get_spark_session("melisimlake_bronze_to_silver_users")
    spark.sparkContext.setLogLevel("WARN")

    logger.info("Iniciando Bronze→Silver users", extra={"date": date})
    df = _read_bronze(spark, date)
    row_count = df.count()
    logger.info("Registros lidos do Bronze", extra={"count": row_count})

    if row_count == 0:
        logger.warning("Nenhum registro no Bronze para a data", extra={"date": date})
        return

    merge_scd2(spark, SILVER_PATH, df, "user_id", BUSINESS_KEY_COLUMNS)
    logger.info("Silver users atualizado", extra={"path": SILVER_PATH})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bronze→Silver users")
    parser.add_argument("--date", default=None, help="Partição YYYY-MM-DD")
    args = parser.parse_args(argv)
    run(args.date)


if __name__ == "__main__":
    main(sys.argv[1:])
