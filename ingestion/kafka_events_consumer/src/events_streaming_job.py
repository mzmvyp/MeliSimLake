"""Kafka Events Consumer — consome eventos do Melisim e escreve em Bronze."""

from __future__ import annotations

import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json, to_date, to_timestamp
from pyspark.sql.types import StructType

from ingestion.cdc_consumer.src.config import settings
from ingestion.cdc_consumer.src.spark_builder import build_spark_session
from ingestion.kafka_events_consumer.src.schemas import TOPIC_SCHEMAS

BRONZE_BASE: Final[str] = f"s3a://{settings.bronze_bucket}/events"
CHECKPOINT_BASE: Final[str] = f"s3a://{settings.checkpoint_bucket}/events"


def _read_event_stream(spark: SparkSession, topic: str) -> DataFrame:
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 50_000)
        .load()
    )


def _parse_event(raw: DataFrame, schema: StructType) -> DataFrame:
    """Parseia mensagem JSON com schema explícito.

    Args:
        raw: DataFrame raw do Kafka.
        schema: Schema Spark do evento.

    Returns:
        DataFrame com campos do evento + partição por data.
    """
    value_str = raw.selectExpr(
        "CAST(value AS STRING) as json_str",
        "timestamp as kafka_ts",
        "partition as kafka_partition",
        "offset as kafka_offset",
    )

    parsed = value_str.withColumn("event", from_json(col("json_str"), schema))

    fields = [f"event.{f.name}" for f in schema.fields]
    return (
        parsed.select(*fields, "kafka_ts", "kafka_partition", "kafka_offset")
        .withColumn("event_date", to_date(to_timestamp(col("ts"))))
    )


def stream_topic(
    spark: SparkSession,
    topic: str,
    schema: StructType,
    *,
    trigger_seconds: int = 30,
) -> object:
    """Inicia streaming de um tópico de eventos para Bronze.

    Args:
        spark: SparkSession ativa.
        topic: Nome do tópico Kafka.
        schema: Schema Spark esperado.
        trigger_seconds: Intervalo de micro-batch.

    Returns:
        StreamingQuery ativa.
    """
    topic_short = topic.split(".")[-1]
    bronze_path = f"{BRONZE_BASE}/{topic_short}/"
    checkpoint_path = f"{CHECKPOINT_BASE}/{topic_short}/"

    logger.info("Iniciando eventos streaming", extra={"topic": topic, "path": bronze_path})

    raw = _read_event_stream(spark, topic)
    parsed = _parse_event(raw, schema)

    return (
        parsed.writeStream.format("parquet")
        .partitionBy("event_date")
        .option("path", bronze_path)
        .option("checkpointLocation", checkpoint_path)
        .outputMode("append")
        .trigger(processingTime=f"{trigger_seconds} seconds")
        .start()
    )


def main() -> None:
    """Entry point — inicia streaming de todos os tópicos de eventos."""
    spark = build_spark_session("melisimlake_events_consumer")
    spark.sparkContext.setLogLevel("WARN")

    queries = []
    for topic, schema in TOPIC_SCHEMAS.items():
        q = stream_topic(spark, topic, schema)
        queries.append(q)
        logger.info("Stream ativo", extra={"topic": topic, "query_id": q.id})

    logger.info(f"{len(queries)} streams de eventos ativos.")
    for q in queries:
        q.awaitTermination()


if __name__ == "__main__":
    main()
