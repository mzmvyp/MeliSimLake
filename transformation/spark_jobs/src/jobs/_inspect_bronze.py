"""Inspeciona payload bronze de orders/payments/users para descobrir formato real
dos campos created_at/updated_at (string ISO vs long ms vs long us)."""

from __future__ import annotations

import os

from pyspark.sql import SparkSession


def main() -> None:
    spark = (
        SparkSession.builder.appName("inspect")
        .config("spark.driver.host", os.environ.get("SPARK_DRIVER_HOST", "melisimlake-batch-runner"))
        .config("spark.driver.bindAddress", "0.0.0.0")
        .config("spark.cores.max", "1")
        .config("spark.executor.cores", "1")
        .config("spark.executor.memory", "512m")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    for tbl in ("orders", "users", "payments", "products"):
        try:
            df = spark.read.parquet(f"s3a://bronze/cdc/{tbl}/")
            print(f"\n=== bronze/cdc/{tbl} count={df.count()} ===")
            df.select("payload_after", "cdc_op", "cdc_ts_ms").show(2, truncate=False)
        except Exception as exc:
            print(f"{tbl}: {exc}")


if __name__ == "__main__":
    main()
