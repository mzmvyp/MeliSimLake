"""Fraud Detection — XGBoost supervisionado com rótulos sintéticos."""

from __future__ import annotations

from typing import Final

import mlflow
import numpy as np
import pandas as pd
import xgboost as xgb
from loguru import logger
from sklearn.metrics import classification_report, precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

MODEL_NAME: Final[str] = "fraud_xgboost"
EXPERIMENT_NAME: Final[str] = "melisimlake/fraud_detection"

FEATURE_COLS: Final[list[str]] = [
    "total_amount",
    "items_count",
    "hour_of_day",
    "days_since_account_creation",
    "orders_in_last_hour",
    "avg_order_value_deviation",
]


def _generate_labeled_data(n: int = 5000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        {
            "total_amount": np.abs(rng.normal(300, 200, n)),
            "items_count": rng.integers(1, 20, n),
            "hour_of_day": rng.integers(0, 24, n),
            "days_since_account_creation": rng.integers(0, 3000, n),
            "orders_in_last_hour": rng.integers(0, 10, n),
            "avg_order_value_deviation": rng.normal(0, 1, n),
            "is_fraud": 0,
        }
    )
    fraud_idx = rng.choice(n, size=int(n * 0.05), replace=False)
    df.loc[fraud_idx, "is_fraud"] = 1
    df.loc[fraud_idx, "total_amount"] = rng.uniform(5000, 20000, len(fraud_idx))
    df.loc[fraud_idx, "orders_in_last_hour"] = rng.integers(5, 20, len(fraud_idx))
    return df


def run(run_date: str = "2026-01-01") -> str:
    """Treina XGBoost para detecção de fraude supervisionada.

    Args:
        run_date: Data de referência.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    df = _generate_labeled_data()
    X = df[FEATURE_COLS].values
    y = df["is_fraud"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=19,
        use_label_encoder=False,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, verbose=False)

    preds_proba = model.predict_proba(X_test)[:, 1]
    preds_class = (preds_proba > 0.5).astype(int)
    auc = roc_auc_score(y_test, preds_proba)
    prec_top1 = precision_score(y_test, (preds_proba >= np.percentile(preds_proba, 99)).astype(int))

    logger.info("XGBoost fraude treinado", extra={"auc": auc, "prec_top1pct": prec_top1})

    with start_run(f"fraud_xgb_{run_date}", tags={"model": "XGBoost", "task": "fraud"}) as run:
        mlflow.log_params(
            {"n_estimators": 300, "max_depth": 5, "scale_pos_weight": 19}
        )
        mlflow.log_metrics({"test_auc": auc, "precision_top1pct": prec_top1})
        mlflow.xgboost.log_model(model, "model")
        run_id = run.info.run_id

    register_model(f"runs:/{run_id}/model", MODEL_NAME, stage="Staging")
    return run_id


if __name__ == "__main__":
    run()
