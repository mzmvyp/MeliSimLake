"""DAG: ingestion_csv_daily — carrega CSVs da landing para Bronze."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.providers.amazon.aws.operators.s3 import S3ListOperator
from loguru import logger

from orchestration.dags.lib.callbacks import datahub_success_callback, slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
    "on_failure_callback": slack_failure_callback,
    "on_success_callback": datahub_success_callback,
}


@dag(
    dag_id="ingestion_csv_daily",
    default_args=DEFAULT_ARGS,
    schedule="0 1 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bronze", "ingestion", "csv", "batch"],
    description="Carrega CSVs da landing zone para Bronze (Parquet)",
)
def ingestion_csv_daily() -> None:
    """Pipeline de ingestão CSV diária: landing → Bronze."""

    @task
    def load_catalog_csv(ds: str) -> int:
        """Processa CSVs de catálogo legado."""
        from ingestion.batch_csv_loader.src.csv_loader import process_file_type
        return process_file_type("catalog", ds)

    @task
    def load_logistics_csv(ds: str) -> int:
        """Processa CSVs de logística."""
        from ingestion.batch_csv_loader.src.csv_loader import process_file_type
        return process_file_type("logistics", ds)

    @task
    def log_summary(catalog_count: int, logistics_count: int) -> None:
        """Loga resumo da execução."""
        total = catalog_count + logistics_count
        logger.info("CSV daily ingestion concluído", extra={"total_files": total})

    cat = load_catalog_csv()
    log = load_logistics_csv()
    log_summary(cat, log)


ingestion_csv_daily()
