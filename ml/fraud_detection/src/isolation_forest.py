"""Fraud Detection — Isolation Forest (não-supervisionado)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import mlflow

from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

MODEL_NAME = "fraud_isolation_forest"
EXPERIMENT_NAME = "melisimlake/fraud_detection"

FEATURE_COLS = [
    "total_amount",
    "items_count",
    "hour_of_day",
    "days_since_account_creation",
    "orders_in_last_hour",
    "avg_order_value_deviation",
]


def _load_data(run_date: str) -> pd.DataFrame:
    """Carrega features de pedidos para detecção de fraude."""
    rng = np.random.default_rng(42)
    n = 5000
    df = pd.DataFrame(
        {
            "order_id": [f"o{i}" for i in range(n)],
            "total_amount": np.abs(rng.normal(300, 200, n)),
            "items_count": rng.integers(1, 20, n),
            "hour_of_day": rng.integers(0, 24, n),
            "days_since_account_creation": rng.integers(0, 3000, n),
            "orders_in_last_hour": rng.integers(0, 10, n),
            "avg_order_value_deviation": rng.normal(0, 1, n),
        }
    )
    # Injeta 5% de fraudes sintéticas
    fraud_idx = rng.choice(n, size=int(n * 0.05), replace=False)
    df.loc[fraud_idx, "total_amount"] = rng.uniform(5000, 20000, len(fraud_idx))
    df.loc[fraud_idx, "orders_in_last_hour"] = rng.integers(5, 20, len(fraud_idx))
    return df


def run(run_date: str = "2026-01-01") -> str:
    """Treina Isolation Forest e registra no MLflow.

    Args:
        run_date: Data de referência.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    df = _load_data(run_date)
    available = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        max_samples="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)
    scores = model.decision_function(X_scaled)
    predictions = model.predict(X_scaled)
    fraud_rate = (predictions == -1).mean()

    logger.info("Isolation Forest treinado", extra={"fraud_rate": fraud_rate})

    with start_run(f"fraud_if_{run_date}", tags={"model": "IsolationForest"}) as run:
        mlflow.log_params(
            {
                "n_estimators": 200,
                "contamination": 0.05,
                "n_features": len(available),
                "n_samples": len(df),
            }
        )
        mlflow.log_metric("train_fraud_rate", float(fraud_rate))
        mlflow.sklearn.log_model(
            {"model": model, "scaler": scaler},
            "model",
        )
        run_id = run.info.run_id

    register_model(f"runs:/{run_id}/model", MODEL_NAME, stage="Staging")
    return run_id


if __name__ == "__main__":
    run()
