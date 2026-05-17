"""Spark Structured Streaming: lê eventos de domínio do Kafka do Melisim
(`melisim-kafka:9092`, rede `melisim_melisim`) e grava em Bronze como Parquet
particionado por `event_date`.

Topicos consumidos (definidos em `MeliSim/infra/kafka/topics.sh`):
  - order-created       (orders-service via outbox)
  - payment-confirmed   (payments-service)
  - payment-failed      (payments-service)
  - product-created     (products-service)
  - stock-updates       (products-service / stock changes)
  - stock-alert         (stock-monitor)

Cada topico vira um stream independente que escreve em
`s3a://bronze/events/<event_name>/`. O nome do arquivo bronze contem
event_date (data Kafka), o payload bruto JSON e metadados Kafka
(partition/offset/timestamp).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Final

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, lit, to_date, to_timestamp


EVENT_TOPICS: Final[dict[str, str]] = {
    "order_created": "order-created",
    "payment_confirmed": "payment-confirmed",
    "payment_failed": "payment-failed",
    "product_created": "product-created",
    "stock_updates": "stock-updates",
    "stock_alert": "stock-alert",
}


def _build_spark(app_name: str) -> SparkSession:
    minio_endpoint = os.environ.get("MELISIMLAKE_MINIO_ENDPOINT", "http://minio:9000")
    minio_access = os.environ.get("MELISIMLAKE_MINIO_ACCESS_KEY", "minioadmin")
    minio_secret = os.environ.get("MELISIMLAKE_MINIO_SECRET_KEY", "minioadmin123")
    driver_host = os.environ.get("SPARK_DRIVER_HOST", "melisimlake-events-consumer")
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.driver.host", driver_host)
        .config("spark.driver.bindAddress", "0.0.0.0")
        .config("spark.cores.max", "2")
        .config("spark.executor.cores", "1")
        .config("spark.executor.memory", "768m")
        .config(
            "spark.jars.packages",
            ",".join(
                [
                    "org.apache.hadoop:hadoop-aws:3.3.4",
                    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
                ]
            ),
        )
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", minio_access)
        .config("spark.hadoop.fs.s3a.secret.key", minio_secret)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def _stream_topic(
    spark: SparkSession,
    *,
    bootstrap: str,
    topic: str,
    event_name: str,
    bronze_bucket: str,
    checkpoint_bucket: str,
    trigger_seconds: int,
) -> object:
    bronze_path = f"s3a://{bronze_bucket}/events/{event_name}/"
    checkpoint_path = f"s3a://{checkpoint_bucket}/events/{event_name}/"

    logger.info(
        "Iniciando stream evento",
        extra={"event": event_name, "topic": topic, "path": bronze_path},
    )

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 50_000)
        .load()
    )

    parsed = (
        raw.selectExpr(
            "CAST(key AS STRING) as record_key",
            "CAST(value AS STRING) as payload_json",
            "timestamp as kafka_timestamp",
            "partition as kafka_partition",
            "offset as kafka_offset",
            "topic as kafka_topic",
        )
        .withColumn("event_name", lit(event_name))
        .withColumn("event_ts", to_timestamp(col("kafka_timestamp")))
        .withColumn("event_date", to_date(col("event_ts")))
    )

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
    parser = argparse.ArgumentParser(description="MeliSim Events Consumer")
    parser.add_argument(
        "--events",
        nargs="+",
        default=list(EVENT_TOPICS.keys()),
        choices=list(EVENT_TOPICS.keys()),
    )
    parser.add_argument("--trigger-seconds", type=int, default=15)
    args = parser.parse_args(argv)

    bootstrap = os.environ.get("MELISIM_KAFKA_BOOTSTRAP_SERVERS", "melisim-kafka:9092")
    bronze = os.environ.get("MELISIMLAKE_BRONZE_BUCKET", "bronze")
    checkpoint = os.environ.get("MELISIMLAKE_CHECKPOINT_BUCKET", "checkpoints")

    spark = _build_spark("melisim_events_consumer")
    spark.sparkContext.setLogLevel("WARN")

    queries = []
    for ev in args.events:
        topic = EVENT_TOPICS[ev]
        q = _stream_topic(
            spark,
            bootstrap=bootstrap,
            topic=topic,
            event_name=ev,
            bronze_bucket=bronze,
            checkpoint_bucket=checkpoint,
            trigger_seconds=args.trigger_seconds,
        )
        queries.append(q)

    logger.info(f"{len(queries)} streams ativos. Aguardando terminação...")
    for q in queries:
        q.awaitTermination()


if __name__ == "__main__":
    main(sys.argv[1:])
