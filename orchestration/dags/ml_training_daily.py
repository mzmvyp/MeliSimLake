"""DAG: ml_training_daily — treina ALS e XGBoost Churn diariamente."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from orchestration.dags.lib.callbacks import datahub_success_callback, slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
    "execution_timeout": timedelta(hours=3),
    "on_failure_callback": slack_failure_callback,
    "on_success_callback": datahub_success_callback,
}


@dag(
    dag_id="ml_training_daily",
    default_args=DEFAULT_ARGS,
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ml", "training"],
    description="Re-treino diário: ALS recomendação + XGBoost churn",
)
def ml_training_daily() -> None:

    @task
    def train_als(ds: str) -> str:
        """Treina modelo ALS e registra no MLflow."""
        from ml.recommendation_als.src.train import run as als_run
        return als_run(run_date=ds)

    @task
    def train_churn_xgboost(ds: str) -> str:
        """Treina XGBoost churn e registra no MLflow."""
        from ml.churn_xgboost.src.train import run as churn_run
        return churn_run(run_date=ds)

    @task
    def train_fraud_detection(ds: str) -> str:
        """Treina modelos de detecção de fraude."""
        from ml.fraud_detection.src.isolation_forest import run as fraud_run
        return fraud_run(run_date=ds)

    als = train_als()
    churn = train_churn_xgboost()
    fraud = train_fraud_detection()

    [als, churn, fraud]


ml_training_daily()
