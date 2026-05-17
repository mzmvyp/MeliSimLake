"""CDC Streaming Job — consome tópicos Debezium e escreve em Bronze (Parquet)."""

from __future__ import annotations

import argparse
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, from_json, lit, to_date, to_timestamp
from pyspark.sql.types import StringType, StructField, StructType

from ingestion.cdc_consumer.src.config import settings
from ingestion.cdc_consumer.src.spark_builder import build_spark_session

DEBEZIUM_ENVELOPE_SCHEMA: Final[StructType] = StructType(
    [
        StructField("op", StringType(), True),
        StructField("ts_ms", StringType(), True),
        StructField("before", StringType(), True),
        StructField("after", StringType(), True),
        StructField("source", StringType(), True),
    ]
)

CDC_TOPICS: Final[dict[str, str]] = {
    "products": "cdc.melisim.public.products",
    "payments": "cdc.melisim.public.payments",
    "notifications": "cdc.melisim.public.notifications",
    "users": "cdc.melisim.mysql.melisim.users",
    "orders": "cdc.melisim.mysql.melisim.orders",
}


def _read_kafka_stream(spark: SparkSession, topic: str) -> DataFrame:
    """Lê stream Kafka de um tópico CDC.

    Args:
        spark: SparkSession ativa.
        topic: Nome do tópico Kafka.

    Returns:
        DataFrame com colunas raw do Kafka.
    """
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 100_000)
        .load()
    )


def _parse_debezium_envelope(raw: DataFrame) -> DataFrame:
    """Decodifica envelope Debezium do campo value (bytes → JSON).

    Args:
        raw: DataFrame com campo `value` em bytes.

    Returns:
        DataFrame com campos `op`, `ts_ms`, `payload`, `event_date`.
    """
    parsed = raw.selectExpr(
        "CAST(key AS STRING) as record_key",
        "CAST(value AS STRING) as raw_json",
        "timestamp as kafka_timestamp",
        "partition as kafka_partition",
        "offset as kafka_offset",
    )

    envelope = parsed.withColumn(
        "envelope",
        from_json(col("raw_json"), DEBEZIUM_ENVELOPE_SCHEMA),
    )

    return (
        envelope.select(
            col("record_key"),
            col("raw_json"),
            col("envelope.op").alias("cdc_op"),
            col("envelope.ts_ms").alias("cdc_ts_ms"),
            col("envelope.after").alias("payload_after"),
            col("envelope.before").alias("payload_before"),
            col("kafka_timestamp"),
            col("kafka_partition"),
            col("kafka_offset"),
        )
        .withColumn("event_ts", to_timestamp(col("kafka_timestamp")))
        .withColumn("event_date", to_date(col("event_ts")))
        .withColumn("ingested_at", lit("current_timestamp()"))
    )


def stream_table(
    spark: SparkSession,
    table_name: str,
    *,
    trigger_seconds: int = 30,
) -> object:
    """Inicia streaming de uma tabela CDC para Bronze.

    Args:
        spark: SparkSession ativa.
        table_name: Nome da tabela (chave em CDC_TOPICS).
        trigger_seconds: Intervalo de micro-batch em segundos.

    Returns:
        StreamingQuery ativa.

    Raises:
        ValueError: Se table_name não estiver em CDC_TOPICS.
    """
    if table_name not in CDC_TOPICS:
        raise ValueError(
            f"Tabela '{table_name}' inválida. Opções: {list(CDC_TOPICS.keys())}"
        )

    topic = CDC_TOPICS[table_name]
    bronze_path = f"s3a://{settings.bronze_bucket}/cdc/{table_name}/"
    checkpoint_path = (
        f"s3a://{settings.checkpoint_bucket}/cdc/{table_name}/"
    )

    logger.info(
        "Iniciando CDC streaming",
        extra={"table": table_name, "topic": topic, "path": bronze_path},
    )

    raw = _read_kafka_stream(spark, topic)
    parsed = _parse_debezium_envelope(raw)

    return (
        parsed.writeStream.format("parquet")
        .partitionBy("event_date")
        .option("path", bronze_path)
        .option("checkpointLocation", checkpoint_path)
        .outputMode("append")
        .trigger(processingTime=f"{trigger_seconds} seconds")
        .start()
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point — inicia streaming de todas as tabelas CDC.

    Args:
        argv: Argumentos CLI. Se None, usa sys.argv.
    """
    parser = argparse.ArgumentParser(description="MeliSimLake CDC Consumer")
    parser.add_argument(
        "--tables",
        nargs="+",
        default=list(CDC_TOPICS.keys()),
        choices=list(CDC_TOPICS.keys()),
        help="Tabelas a consumir (padrão: todas)",
    )
    parser.add_argument(
        "--trigger-seconds",
        type=int,
        default=settings.streaming_trigger_seconds,
        help="Intervalo de micro-batch em segundos",
    )
    args = parser.parse_args(argv)

    spark = build_spark_session("melisimlake_cdc_consumer")
    spark.sparkContext.setLogLevel("WARN")

    queries = []
    for table in args.tables:
        q = stream_table(spark, table, trigger_seconds=args.trigger_seconds)
        queries.append(q)
        logger.info("Stream iniciado", extra={"table": table, "query_id": q.id})

    logger.info(f"{len(queries)} streams ativos. Aguardando terminação...")
    for q in queries:
        q.awaitTermination()


if __name__ == "__main__":
    main(sys.argv[1:])
