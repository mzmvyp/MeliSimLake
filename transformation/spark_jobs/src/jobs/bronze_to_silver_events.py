"""Job Bronze → Silver: eventos comportamentais (append-only)."""

from __future__ import annotations

import argparse
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, lit, to_date, to_timestamp, unix_timestamp
from pyspark.sql.types import StringType

from transformation.spark_jobs.src.lib.delta_utils import upsert_append
from transformation.spark_jobs.src.lib.spark_session import get_spark_session

BRONZE_EVENTS_BASE: Final[str] = "s3a://bronze/events/"
SILVER_PATH: Final[str] = "s3a://silver/events/"

EVENT_TOPICS: Final[list[str]] = ["clicks", "cart", "search", "purchase"]


def _read_bronze_topic(spark: SparkSession, topic: str, date: str | None) -> DataFrame:
    """Lê Parquet de um tópico de eventos do Bronze.

    Args:
        spark: SparkSession ativa.
        topic: Nome do tópico (ex: clicks).
        date: Partição de data (None = todos).

    Returns:
        DataFrame normalizado com coluna event_type.
    """
    path = f"{BRONZE_EVENTS_BASE}{topic}/"
    if date:
        path += f"event_date={date}/"

    df = spark.read.parquet(path)

    common_cols = ["event_id", "user_id", "session_id", "ts"]
    available = [c for c in common_cols if c in df.columns]
    product_col = col("product_id") if "product_id" in df.columns else lit(None).cast(StringType())

    return (
        df.select(*available, product_col.alias("product_id"))
        .withColumn("event_type", lit(topic))
        .withColumn("payload", lit(None).cast(StringType()))
        .withColumn(
            "ts", to_timestamp(col("ts"))
        )
        .withColumn("event_date", to_date(col("ts")))
        .filter(col("event_id").isNotNull())
    )


def run(date: str | None = None) -> None:
    """Executa job Bronze → Silver para eventos."""
    spark = get_spark_session("melisimlake_bronze_to_silver_events")
    spark.sparkContext.setLogLevel("WARN")
    logger.info("Iniciando Bronze→Silver events", extra={"date": date})

    dfs = []
    for topic in EVENT_TOPICS:
        try:
            df = _read_bronze_topic(spark, topic, date)
            dfs.append(df)
            logger.info("Tópico lido", extra={"topic": topic, "rows": df.count()})
        except Exception as exc:
            logger.warning("Tópico sem dados", extra={"topic": topic, "error": str(exc)})

    if not dfs:
        logger.warning("Nenhum evento disponível", extra={"date": date})
        return

    from functools import reduce
    combined = reduce(lambda a, b: a.union(b), dfs).dropDuplicates(["event_id"])
    upsert_append(spark, SILVER_PATH, combined, "event_id", "ts")
    logger.info("Silver events atualizado", extra={"total_rows": combined.count()})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args(argv)
    run(args.date)


if __name__ == "__main__":
    main(sys.argv[1:])
