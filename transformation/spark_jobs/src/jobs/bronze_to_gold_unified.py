"""Pipeline unificado Bronze -> Gold (Delta) para o dominio Melisim.

Le os dados crus de:
    s3a://bronze/cdc/users/         (Debezium MySQL CDC, pre-parseado)
    s3a://bronze/cdc/products/      (Debezium Postgres CDC)
    s3a://bronze/cdc/orders/        (Debezium MySQL CDC)
    s3a://bronze/cdc/payments/      (Debezium Postgres CDC)
    s3a://bronze/cdc/notifications/ (Debezium Postgres CDC)
    s3a://bronze/events/order_created/      (Kafka melisim-kafka)
    s3a://bronze/events/payment_confirmed/  (Kafka)
    s3a://bronze/events/payment_failed/     (Kafka)
    s3a://bronze/events/stock_alert/        (Kafka)
    s3a://bronze/events/stock_updates/      (Kafka)
    s3a://bronze/events/product_created/    (Kafka)

Materializa no Gold (Delta Lake em s3a://delta-metastore/catalog/gold/<table>):
    dim_users
    dim_products
    fact_orders
    fact_payments
    fact_stock_alerts
    notifications_daily
    product_metrics_daily
    seller_metrics_daily
    customer_rfm

Cada tabela e idempotente: overwrite total a cada execucao (volume baixo
do simulador permite). Para volumes grandes, evoluir para incremental MERGE.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone

from loguru import logger
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


GOLD_BASE = "s3a://delta-metastore/catalog/gold"


def build_spark() -> SparkSession:
    minio_endpoint = os.environ.get("MELISIMLAKE_MINIO_ENDPOINT", "http://minio:9000")
    minio_access = os.environ.get("MELISIMLAKE_MINIO_ACCESS_KEY", "minioadmin")
    minio_secret = os.environ.get("MELISIMLAKE_MINIO_SECRET_KEY", "minioadmin123")
    driver_host = os.environ.get("SPARK_DRIVER_HOST", "melisimlake-batch-runner")
    return (
        SparkSession.builder.appName("melisimlake_bronze_to_gold")
        .config("spark.driver.host", driver_host)
        .config("spark.driver.bindAddress", "0.0.0.0")
        .config("spark.cores.max", "4")
        .config("spark.executor.cores", "1")
        .config("spark.executor.memory", "1g")
        .config(
            "spark.jars.packages",
            ",".join(
                [
                    "io.delta:delta-spark_2.12:3.2.0",
                    "org.apache.hadoop:hadoop-aws:3.3.4",
                ]
            ),
        )
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
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


# ----------------------------------------------------------------------------
# Helpers para ler bronze CDC (Debezium) e bronze events (Kafka).
# Bronze CDC tem colunas: payload_after (json), payload_before (json),
# cdc_op (c=create,u=update,d=delete,r=read snapshot), cdc_ts_ms,
# event_ts (kafka timestamp).
# Para SCD 'current state', selecionamos por chave a linha mais recente
# (order by cdc_ts_ms desc), e ignoramos tombstones (cdc_op='d').
# ----------------------------------------------------------------------------


def _read_cdc(spark: SparkSession, table: str) -> DataFrame | None:
    path = f"s3a://bronze/cdc/{table}/"
    try:
        df = spark.read.parquet(path)
        if df.rdd.isEmpty():
            logger.warning(f"bronze cdc {table} vazio")
            return None
        return df
    except Exception as exc:
        logger.warning(f"bronze cdc {table} indisponivel: {exc}")
        return None


def _read_event(spark: SparkSession, event: str) -> DataFrame | None:
    path = f"s3a://bronze/events/{event}/"
    try:
        df = spark.read.parquet(path)
        if df.rdd.isEmpty():
            logger.warning(f"bronze events {event} vazio")
            return None
        return df
    except Exception as exc:
        logger.warning(f"bronze events {event} indisponivel: {exc}")
        return None


def _latest_per_key(df: DataFrame, key_col: str) -> DataFrame:
    """Mantem apenas a linha mais recente por chave (CDC: usa cdc_ts_ms)."""
    from pyspark.sql.window import Window

    w = Window.partitionBy(key_col).orderBy(F.col("cdc_ts_ms").desc_nulls_last())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


# ----------------------------------------------------------------------------
# DIM users — bronze CDC (MySQL)
# ----------------------------------------------------------------------------
USERS_SCHEMA = StructType(
    [
        StructField("id", LongType()),
        StructField("name", StringType()),
        StructField("email", StringType()),
        StructField("user_type", StringType()),
        StructField("created_at", StringType()),
        StructField("updated_at", StringType()),
    ]
)


def build_dim_users(spark: SparkSession) -> None:
    df = _read_cdc(spark, "users")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_after"), USERS_SCHEMA))
        .filter(F.col("cdc_op") != "d")
        .filter(F.col("payload.id").isNotNull())
        .select(
            F.col("payload.id").alias("user_id"),
            F.col("payload.name").alias("name"),
            F.col("payload.email").alias("email"),
            F.col("payload.user_type").alias("user_type"),
            F.to_timestamp(F.col("payload.created_at")).alias("created_at"),
            F.to_timestamp(F.col("payload.updated_at")).alias("updated_at"),
            F.col("cdc_ts_ms"),
        )
    )
    latest = _latest_per_key(parsed, "user_id").drop("cdc_ts_ms")
    target = f"{GOLD_BASE}/dim_users"
    latest.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"dim_users => {latest.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# DIM products — bronze CDC (Postgres)
# ----------------------------------------------------------------------------
PRODUCTS_SCHEMA = StructType(
    [
        StructField("id", LongType()),
        StructField("seller_id", LongType()),
        StructField("title", StringType()),
        StructField("description", StringType()),
        StructField("category", StringType()),
        StructField("price", DoubleType()),
        StructField("stock", IntegerType()),
        StructField("created_at", StringType()),
        StructField("updated_at", StringType()),
    ]
)


def build_dim_products(spark: SparkSession) -> None:
    df = _read_cdc(spark, "products")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_after"), PRODUCTS_SCHEMA))
        .filter(F.col("cdc_op") != "d")
        .filter(F.col("payload.id").isNotNull())
        .select(
            F.col("payload.id").alias("product_id"),
            F.col("payload.seller_id").alias("seller_id"),
            F.col("payload.title").alias("title"),
            F.col("payload.description").alias("description"),
            F.col("payload.category").alias("category"),
            F.col("payload.price").alias("price"),
            F.col("payload.stock").alias("stock"),
            F.to_timestamp(F.col("payload.created_at")).alias("created_at"),
            F.to_timestamp(F.col("payload.updated_at")).alias("updated_at"),
            F.col("cdc_ts_ms"),
        )
    )
    latest = _latest_per_key(parsed, "product_id").drop("cdc_ts_ms")
    target = f"{GOLD_BASE}/dim_products"
    latest.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"dim_products => {latest.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# FACT orders — bronze CDC orders (MySQL) + payload Kafka order-created
# Preferimos CDC porque captura tambem updates de status.
# ----------------------------------------------------------------------------
ORDERS_SCHEMA = StructType(
    [
        StructField("id", LongType()),
        StructField("buyer_id", LongType()),
        StructField("product_id", LongType()),
        StructField("quantity", IntegerType()),
        StructField("unit_price", DoubleType()),
        StructField("total_amount", DoubleType()),
        StructField("status", StringType()),
        StructField("created_at", StringType()),
        StructField("updated_at", StringType()),
    ]
)


def build_fact_orders(spark: SparkSession) -> None:
    df = _read_cdc(spark, "orders")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_after"), ORDERS_SCHEMA))
        .filter(F.col("cdc_op") != "d")
        .filter(F.col("payload.id").isNotNull())
        .select(
            F.col("payload.id").alias("order_id"),
            F.col("payload.buyer_id").alias("buyer_id"),
            F.col("payload.product_id").alias("product_id"),
            F.col("payload.quantity").alias("quantity"),
            F.col("payload.unit_price").alias("unit_price"),
            F.col("payload.total_amount").alias("total_amount"),
            F.col("payload.status").alias("status"),
            F.to_timestamp(F.col("payload.created_at")).alias("created_at"),
            F.to_timestamp(F.col("payload.updated_at")).alias("updated_at"),
            F.col("cdc_ts_ms"),
        )
    )
    latest = _latest_per_key(parsed, "order_id").drop("cdc_ts_ms")
    target = f"{GOLD_BASE}/fact_orders"
    latest.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"fact_orders => {latest.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# FACT payments — bronze CDC payments (Postgres)
# ----------------------------------------------------------------------------
PAYMENTS_SCHEMA = StructType(
    [
        StructField("id", LongType()),
        StructField("order_id", LongType()),
        StructField("amount", DoubleType()),
        StructField("method", StringType()),
        StructField("status", StringType()),
        StructField("created_at", StringType()),
        StructField("processed_at", StringType()),
    ]
)


def build_fact_payments(spark: SparkSession) -> None:
    df = _read_cdc(spark, "payments")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_after"), PAYMENTS_SCHEMA))
        .filter(F.col("cdc_op") != "d")
        .filter(F.col("payload.id").isNotNull())
        .select(
            F.col("payload.id").alias("payment_id"),
            F.col("payload.order_id").alias("order_id"),
            F.col("payload.amount").alias("amount"),
            F.col("payload.method").alias("method"),
            F.col("payload.status").alias("status"),
            F.to_timestamp(F.col("payload.created_at")).alias("created_at"),
            F.to_timestamp(F.col("payload.processed_at")).alias("processed_at"),
            F.col("cdc_ts_ms"),
        )
    )
    latest = _latest_per_key(parsed, "payment_id").drop("cdc_ts_ms")
    target = f"{GOLD_BASE}/fact_payments"
    latest.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"fact_payments => {latest.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# FACT stock alerts — eventos Kafka stock-alert
# Payload: {product_id, seller_id, title, stock, threshold}
# ----------------------------------------------------------------------------
STOCK_ALERT_SCHEMA = StructType(
    [
        StructField("product_id", LongType()),
        StructField("seller_id", LongType()),
        StructField("title", StringType()),
        StructField("stock", IntegerType()),
        StructField("threshold", IntegerType()),
    ]
)


def build_fact_stock_alerts(spark: SparkSession) -> None:
    df = _read_event(spark, "stock_alert")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_json"), STOCK_ALERT_SCHEMA))
        .filter(F.col("payload.product_id").isNotNull())
        .select(
            F.col("payload.product_id").alias("product_id"),
            F.col("payload.seller_id").alias("seller_id"),
            F.col("payload.title").alias("title"),
            F.col("payload.stock").alias("stock"),
            F.col("payload.threshold").alias("threshold"),
            F.col("event_ts"),
            F.col("event_date"),
        )
    )
    target = f"{GOLD_BASE}/fact_stock_alerts"
    parsed.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"fact_stock_alerts => {parsed.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# Notifications daily — bronze CDC notifications agregado por dia
# ----------------------------------------------------------------------------
NOTIFS_SCHEMA = StructType(
    [
        StructField("id", LongType()),
        StructField("user_id", LongType()),
        StructField("channel", StringType()),
        StructField("event_type", StringType()),
        StructField("subject", StringType()),
        StructField("body", StringType()),
        StructField("created_at", StringType()),
    ]
)


def build_notifications_daily(spark: SparkSession) -> None:
    df = _read_cdc(spark, "notifications")
    if df is None:
        return
    parsed = (
        df.withColumn("payload", F.from_json(F.col("payload_after"), NOTIFS_SCHEMA))
        .filter(F.col("cdc_op") != "d")
        .filter(F.col("payload.id").isNotNull())
        .select(
            F.col("payload.id").alias("notif_id"),
            F.col("payload.user_id").alias("user_id"),
            F.col("payload.channel").alias("channel"),
            F.col("payload.event_type").alias("event_type"),
            F.to_timestamp(F.col("payload.created_at")).alias("created_at"),
            F.col("cdc_ts_ms"),
        )
    )
    latest = _latest_per_key(parsed, "notif_id").drop("cdc_ts_ms")
    daily = (
        latest.withColumn("notif_date", F.to_date("created_at"))
        .groupBy("notif_date", "channel", "event_type")
        .agg(F.count("*").alias("notifications"))
    )
    target = f"{GOLD_BASE}/notifications_daily"
    daily.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"notifications_daily => {daily.count()} rows -> {target}")


# ----------------------------------------------------------------------------
# Aggregates: product_metrics_daily, seller_metrics_daily, customer_rfm
# Sao construidos em cima de fact_orders + dim_products.
# ----------------------------------------------------------------------------
def build_aggregates(spark: SparkSession) -> None:
    try:
        orders = spark.read.format("delta").load(f"{GOLD_BASE}/fact_orders")
    except Exception:
        logger.warning("fact_orders inexistente, skip agregados")
        return

    try:
        products = spark.read.format("delta").load(f"{GOLD_BASE}/dim_products")
    except Exception:
        products = None

    sold = orders.filter(
        F.col("status").isin("CREATED", "CONFIRMED", "SHIPPED", "DELIVERED")
    )

    # product_metrics_daily
    pmd = (
        sold.withColumn("order_date", F.to_date("created_at"))
        .groupBy("order_date", "product_id")
        .agg(
            F.count("*").alias("orders"),
            F.sum("quantity").alias("units_sold"),
            F.sum("total_amount").alias("gmv"),
        )
    )
    if products is not None:
        pmd = pmd.join(
            products.select("product_id", "title", "category", "seller_id"),
            on="product_id",
            how="left",
        )
    pmd.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        f"{GOLD_BASE}/product_metrics_daily"
    )
    logger.info(f"product_metrics_daily => {pmd.count()} rows")

    # seller_metrics_daily
    if products is not None:
        smd = (
            sold.withColumn("order_date", F.to_date("created_at"))
            .join(products.select("product_id", "seller_id"), on="product_id", how="left")
            .groupBy("order_date", "seller_id")
            .agg(
                F.count("*").alias("orders"),
                F.sum("quantity").alias("units_sold"),
                F.sum("total_amount").alias("gmv"),
            )
        )
        smd.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
            f"{GOLD_BASE}/seller_metrics_daily"
        )
        logger.info(f"seller_metrics_daily => {smd.count()} rows")

    # customer_rfm
    today = F.lit(datetime.now(tz=timezone.utc))
    rfm = (
        sold.groupBy("buyer_id")
        .agg(
            F.max("created_at").alias("last_order_at"),
            F.count("*").alias("frequency"),
            F.sum("total_amount").alias("monetary"),
        )
        .withColumn(
            "recency_days",
            (F.unix_timestamp(today) - F.unix_timestamp("last_order_at")) / 86400,
        )
    )
    rfm.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        f"{GOLD_BASE}/customer_rfm"
    )
    logger.info(f"customer_rfm => {rfm.count()} rows")


GOLD_ML_BASE = "s3a://delta-metastore/catalog/gold_ml"


def build_ml_features(spark: SparkSession) -> None:
    """Materializa features ML em delta.gold_ml.* a partir do gold core."""
    try:
        users = spark.read.format("delta").load(f"{GOLD_BASE}/dim_users")
        products = spark.read.format("delta").load(f"{GOLD_BASE}/dim_products")
        orders = spark.read.format("delta").load(f"{GOLD_BASE}/fact_orders")
        payments = spark.read.format("delta").load(f"{GOLD_BASE}/fact_payments")
    except Exception as exc:
        logger.warning(f"Tabelas core ausentes, skip ML features: {exc}")
        return

    today = F.lit(datetime.now(tz=timezone.utc))
    sold_statuses = ("CREATED", "PAID", "CONFIRMED", "SHIPPED", "DELIVERED")

    sold = orders.filter(F.col("status").isin(*sold_statuses))

    # ---- user_features (per buyer) ----
    user_orders = sold.groupBy("buyer_id").agg(
        F.count("*").alias("orders_total"),
        F.sum("total_amount").alias("monetary"),
        F.avg("total_amount").alias("avg_order_value"),
        F.max("created_at").alias("last_order_at"),
        F.min("created_at").alias("first_order_at"),
        F.countDistinct("product_id").alias("distinct_products"),
    )

    payments_join = (
        payments.alias("p")
        .join(orders.alias("o"), F.col("p.order_id") == F.col("o.order_id"), "left")
        .select(
            F.col("o.buyer_id").alias("buyer_id"),
            F.col("p.status").alias("pay_status"),
            F.col("p.method").alias("method"),
            F.col("p.amount").alias("amount"),
            F.col("p.created_at").alias("pay_created_at"),
        )
    )
    user_pay = payments_join.groupBy("buyer_id").agg(
        F.count("*").alias("payments_total"),
        (F.sum(F.when(F.col("pay_status") == "FAILED", 1.0).otherwise(0.0)) /
         F.count("*")).alias("payment_fail_rate"),
        F.avg("amount").alias("avg_payment_amount"),
    )

    user_features = (
        user_orders.join(user_pay, on="buyer_id", how="left")
        .join(
            users.select(
                F.col("user_id").alias("buyer_id"),
                "name",
                "email",
                "user_type",
                F.col("created_at").alias("user_created_at"),
            ),
            on="buyer_id",
            how="left",
        )
        .withColumn(
            "recency_days",
            (F.unix_timestamp(today) - F.unix_timestamp("last_order_at")) / 86400.0,
        )
        .withColumn(
            "tenure_days",
            (F.unix_timestamp(today) - F.unix_timestamp("first_order_at")) / 86400.0,
        )
        .withColumn(
            "frequency_per_week",
            F.when(F.col("tenure_days") > 0, F.col("orders_total") / (F.col("tenure_days") / 7.0))
            .otherwise(F.col("orders_total")),
        )
        .fillna(
            {
                "payments_total": 0,
                "payment_fail_rate": 0.0,
                "avg_payment_amount": 0.0,
                "distinct_products": 0,
                "orders_total": 0,
                "monetary": 0.0,
                "avg_order_value": 0.0,
            }
        )
    )
    target = f"{GOLD_ML_BASE}/user_features"
    user_features.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.user_features => {user_features.count()} rows")

    # ---- product_features ----
    product_sales = sold.groupBy("product_id").agg(
        F.count("*").alias("orders_30d"),
        F.sum("quantity").alias("units_30d"),
        F.sum("total_amount").alias("gmv_30d"),
        F.countDistinct("buyer_id").alias("distinct_buyers_30d"),
    )
    product_features = (
        products.join(product_sales, on="product_id", how="left")
        .fillna({"orders_30d": 0, "units_30d": 0, "gmv_30d": 0.0, "distinct_buyers_30d": 0})
        .select(
            "product_id",
            "title",
            "category",
            "price",
            "stock",
            "seller_id",
            "orders_30d",
            "units_30d",
            "gmv_30d",
            "distinct_buyers_30d",
        )
    )
    target = f"{GOLD_ML_BASE}/product_features"
    product_features.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.product_features => {product_features.count()} rows")

    # ---- churn_labels (buyer churn = recency > 14d) ----
    churn = user_features.select(
        "buyer_id",
        "recency_days",
        "frequency_per_week",
        "monetary",
        "avg_order_value",
        "tenure_days",
        "payment_fail_rate",
        "payments_total",
        "distinct_products",
        F.when(F.col("recency_days") > 14, 1).otherwise(0).alias("churn_label"),
    )
    target = f"{GOLD_ML_BASE}/churn_dataset"
    churn.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.churn_dataset => {churn.count()} rows")

    # ---- payment_dataset (treino fraud/failure) ----
    pay_user_hist = (
        payments_join.groupBy("buyer_id")
        .agg(
            F.count("*").alias("buyer_pay_count"),
            F.avg("amount").alias("buyer_avg_amount"),
            (F.sum(F.when(F.col("pay_status") == "FAILED", 1.0).otherwise(0.0)) /
             F.count("*")).alias("buyer_fail_rate_hist"),
        )
    )
    pay_features = (
        payments.alias("p")
        .join(orders.alias("o"), F.col("p.order_id") == F.col("o.order_id"), "left")
        .join(pay_user_hist.alias("h"), F.col("o.buyer_id") == F.col("h.buyer_id"), "left")
        .select(
            F.col("p.payment_id").alias("payment_id"),
            F.col("o.buyer_id").alias("buyer_id"),
            F.col("p.amount").alias("amount"),
            F.col("p.method").alias("method"),
            F.col("p.status").alias("status"),
            F.col("p.created_at").alias("created_at"),
            F.hour("p.created_at").alias("hour"),
            F.dayofweek("p.created_at").alias("dow"),
            F.col("h.buyer_pay_count").alias("buyer_pay_count"),
            F.col("h.buyer_avg_amount").alias("buyer_avg_amount"),
            F.col("h.buyer_fail_rate_hist").alias("buyer_fail_rate_hist"),
            F.when(F.col("p.status") == "FAILED", 1).otherwise(0).alias("failed_label"),
        )
        .fillna({"buyer_pay_count": 0, "buyer_avg_amount": 0.0, "buyer_fail_rate_hist": 0.0})
    )
    target = f"{GOLD_ML_BASE}/payment_dataset"
    pay_features.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.payment_dataset => {pay_features.count()} rows")

    # ---- daily_demand (serie temporal global pra forecast) ----
    daily = (
        sold.withColumn("ds", F.to_date("created_at"))
        .groupBy("ds")
        .agg(
            F.count("*").alias("orders"),
            F.sum("total_amount").alias("gmv"),
            F.countDistinct("buyer_id").alias("buyers"),
            F.sum("quantity").alias("units"),
        )
        .orderBy("ds")
    )
    target = f"{GOLD_ML_BASE}/daily_demand"
    daily.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.daily_demand => {daily.count()} rows")

    # ---- user_item_matrix (treino ALS) ----
    user_item = (
        sold.groupBy("buyer_id", "product_id")
        .agg(
            F.sum("quantity").alias("units"),
            F.count("*").alias("orders"),
            F.sum("total_amount").alias("gmv"),
        )
    )
    target = f"{GOLD_ML_BASE}/user_item_matrix"
    user_item.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(target)
    logger.info(f"gold_ml.user_item_matrix => {user_item.count()} rows")


def main() -> int:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    failures: list[str] = []
    for name, fn in [
        ("dim_users", build_dim_users),
        ("dim_products", build_dim_products),
        ("fact_orders", build_fact_orders),
        ("fact_payments", build_fact_payments),
        ("fact_stock_alerts", build_fact_stock_alerts),
        ("notifications_daily", build_notifications_daily),
        ("aggregates", build_aggregates),
        ("ml_features", build_ml_features),
    ]:
        try:
            fn(spark)
        except Exception as exc:
            logger.error(f"falha em {name}: {exc}")
            traceback.print_exc()
            failures.append(name)
    if failures:
        logger.warning(f"jobs com falha: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
