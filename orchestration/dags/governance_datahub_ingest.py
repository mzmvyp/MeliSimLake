"""DAG — Ingestão diária no DataHub (0 9 * * *)."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from orchestration.dags.lib.callbacks import slack_failure_callback

_RECIPES_DIR = "/opt/airflow/infra/datahub/recipes"

_default_args = {
    "owner": "melisimlake",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": slack_failure_callback,
}

with DAG(
    dag_id="governance_datahub_ingest",
    default_args=_default_args,
    description="Executa receitas DataHub para catalogar metadados de todas as fontes",
    schedule_interval="0 9 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["governance", "datahub", "catalog"],
    max_active_runs=1,
) as dag:

    ingest_postgres_airflow = BashOperator(
        task_id="ingest_postgres_airflow",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/postgres_airflow.yml",
    )

    ingest_postgres_mlflow = BashOperator(
        task_id="ingest_postgres_mlflow",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/postgres_mlflow.yml",
    )

    ingest_minio = BashOperator(
        task_id="ingest_minio_s3",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/minio_s3.yml",
    )

    ingest_dbt = BashOperator(
        task_id="ingest_dbt",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/dbt_cloud.yml",
    )

    ingest_mlflow = BashOperator(
        task_id="ingest_mlflow",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/mlflow_recipe.yml",
    )

    ingest_airflow = BashOperator(
        task_id="ingest_airflow_lineage",
        bash_command=f"datahub ingest -c {_RECIPES_DIR}/airflow_lineage.yml",
    )

    load_glossary = BashOperator(
        task_id="load_business_glossary",
        bash_command=(
            "datahub put --aspect glossaryTermInfo "
            "--urn 'urn:li:glossaryTerm:MeliSimLake' "
            f"--aspect-file /opt/airflow/infra/datahub/glossary/business_glossary.yml"
        ),
    )

    # Metadata sources can run in parallel; glossary runs last
    [ingest_postgres_airflow, ingest_postgres_mlflow, ingest_minio, ingest_mlflow] >> ingest_dbt
    ingest_dbt >> ingest_airflow >> load_glossary
