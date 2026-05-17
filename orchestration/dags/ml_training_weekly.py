"""DAG: ml_training_weekly — treina modelos LSTM semanalmente."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from orchestration.dags.lib.callbacks import slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 1,
    "retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=8),
    "on_failure_callback": slack_failure_callback,
}


@dag(
    dag_id="ml_training_weekly",
    default_args=DEFAULT_ARGS,
    schedule="0 8 * * 0",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ml", "training", "lstm"],
    description="Re-treino semanal: GRU4Rec, SASRec, LSTM Demand Forecast",
)
def ml_training_weekly() -> None:

    @task
    def train_gru4rec(ds: str) -> str:
        from ml.recommendation_gru4rec.src.train import run
        return run(run_date=ds)

    @task
    def train_sasrec(ds: str) -> str:
        from ml.recommendation_sasrec.src.train import run
        return run(run_date=ds)

    @task
    def train_demand_forecast(ds: str) -> str:
        from ml.demand_forecast_lstm.src.train import run
        return run(run_date=ds)

    gru = train_gru4rec()
    sas = train_sasrec()
    demand = train_demand_forecast()

    [gru, sas, demand]


ml_training_weekly()
