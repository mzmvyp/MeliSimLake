from __future__ import annotations

from pyspark.sql import SparkSession

from ingestion.cdc_consumer.src.config import settings


def build_spark_session(app_name: str = "cdc_consumer") -> SparkSession:
    """Cria SparkSession configurada para Delta Lake + MinIO.

    Args:
        app_name: Nome da aplicação Spark.

    Returns:
        SparkSession pronta para uso.
    """
    import os

    driver_host = os.environ.get("SPARK_DRIVER_HOST", "melisimlake-cdc-consumer")
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
                    "io.delta:delta-spark_2.12:3.2.0",
                    "org.apache.hadoop:hadoop-aws:3.3.4",
                    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
                    "io.confluent:kafka-schema-registry-client:7.6.0",
                ]
            ),
        )
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.hadoop.fs.s3a.endpoint", settings.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", settings.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )
