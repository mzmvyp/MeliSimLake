"""DAG: transformation_dbt_to_gold — Silver → Gold via dbt."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from orchestration.dags.lib.callbacks import datahub_success_callback, slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": slack_failure_callback,
    "on_success_callback": datahub_success_callback,
}

DBT_DIR = "/opt/airflow/dags/../../../transformation/dbt_project"


@dag(
    dag_id="transformation_dbt_to_gold",
    default_args=DEFAULT_ARGS,
    schedule="0 5 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["gold", "transformation", "dbt"],
    description="Constrói camada Gold com dbt — modelagem dimensional Kimball",
)
def transformation_dbt_to_gold() -> None:

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {DBT_DIR} && dbt deps",
    )

    dbt_build_staging = BashOperator(
        task_id="dbt_build_staging",
        bash_command=f"cd {DBT_DIR} && dbt build --select staging",
    )

    dbt_build_core = BashOperator(
        task_id="dbt_build_core",
        bash_command=f"cd {DBT_DIR} && dbt build --select marts.core",
    )

    dbt_build_analytics = BashOperator(
        task_id="dbt_build_analytics",
        bash_command=f"cd {DBT_DIR} && dbt build --select marts.analytics",
    )

    dbt_build_ml_features = BashOperator(
        task_id="dbt_build_ml_features",
        bash_command=f"cd {DBT_DIR} && dbt build --select marts.ml_features",
    )

    dbt_deps >> dbt_build_staging >> dbt_build_core >> [dbt_build_analytics, dbt_build_ml_features]


transformation_dbt_to_gold()
