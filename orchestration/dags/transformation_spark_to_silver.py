"""DAG: transformation_spark_to_silver — Bronze → Silver via PySpark."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

from orchestration.dags.lib.callbacks import datahub_success_callback, slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=3),
    "on_failure_callback": slack_failure_callback,
    "on_success_callback": datahub_success_callback,
}

SPARK_PACKAGES = (
    "io.delta:delta-spark_2.12:3.2.0,"
    "org.apache.hadoop:hadoop-aws:3.3.4"
)


@dag(
    dag_id="transformation_spark_to_silver",
    default_args=DEFAULT_ARGS,
    schedule="0 4 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["silver", "transformation", "spark"],
    description="Transforma Bronze em Silver com PySpark + Delta Lake (SCD2)",
)
def transformation_spark_to_silver() -> None:

    silver_users = SparkSubmitOperator(
        task_id="silver_users",
        application="/opt/spark-jobs/src/jobs/bronze_to_silver_users.py",
        conn_id="spark_default",
        packages=SPARK_PACKAGES,
        application_args=["--date", "{{ ds }}"],
    )

    silver_products = SparkSubmitOperator(
        task_id="silver_products",
        application="/opt/spark-jobs/src/jobs/bronze_to_silver_products.py",
        conn_id="spark_default",
        packages=SPARK_PACKAGES,
        application_args=["--date", "{{ ds }}"],
    )

    silver_orders = SparkSubmitOperator(
        task_id="silver_orders",
        application="/opt/spark-jobs/src/jobs/bronze_to_silver_orders.py",
        conn_id="spark_default",
        packages=SPARK_PACKAGES,
        application_args=["--date", "{{ ds }}"],
    )

    silver_events = SparkSubmitOperator(
        task_id="silver_events",
        application="/opt/spark-jobs/src/jobs/bronze_to_silver_events.py",
        conn_id="spark_default",
        packages=SPARK_PACKAGES,
        application_args=["--date", "{{ ds }}"],
    )

    # Users e products em paralelo, depois orders e events
    [silver_users, silver_products] >> [silver_orders, silver_events]


transformation_spark_to_silver()
