"""DAG: ingestion_api_hourly — busca cotações, CEP e dados externos."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from orchestration.dags.lib.callbacks import datahub_success_callback, slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": slack_failure_callback,
}


@dag(
    dag_id="ingestion_api_hourly",
    default_args=DEFAULT_ARGS,
    schedule="0 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bronze", "ingestion", "api"],
    description="Coleta APIs externas (exchange rates, ViaCEP) para Bronze",
)
def ingestion_api_hourly() -> None:

    @task
    def fetch_apis(ds: str) -> None:
        """Executa todos os fetchers de API."""
        from ingestion.api_fetcher.src.fetcher_main import run
        run(date=ds)

    fetch_apis()


ingestion_api_hourly()
