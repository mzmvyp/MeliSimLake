"""DAG: quality_great_expectations — roda suítes GE em Bronze, Silver e Gold."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from orchestration.dags.lib.callbacks import slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
    "on_failure_callback": slack_failure_callback,
}

GE_DIR = "/opt/airflow/dags/../../../transformation/great_expectations"


@dag(
    dag_id="quality_great_expectations",
    default_args=DEFAULT_ARGS,
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["quality", "great_expectations"],
)
def quality_great_expectations() -> None:

    ge_bronze = BashOperator(
        task_id="ge_bronze_users",
        bash_command=f"cd {GE_DIR} && great_expectations checkpoint run bronze_users || true",
    )

    ge_silver_users = BashOperator(
        task_id="ge_silver_users",
        bash_command=f"cd {GE_DIR} && great_expectations checkpoint run silver_users",
    )

    ge_silver_orders = BashOperator(
        task_id="ge_silver_orders",
        bash_command=f"cd {GE_DIR} && great_expectations checkpoint run silver_orders",
    )

    ge_gold = BashOperator(
        task_id="ge_gold_fact_orders",
        bash_command=f"cd {GE_DIR} && great_expectations checkpoint run gold_fact_orders",
    )

    ge_build_docs = BashOperator(
        task_id="ge_build_docs",
        bash_command=f"cd {GE_DIR} && great_expectations docs build",
    )

    ge_bronze >> [ge_silver_users, ge_silver_orders] >> ge_gold >> ge_build_docs


quality_great_expectations()
