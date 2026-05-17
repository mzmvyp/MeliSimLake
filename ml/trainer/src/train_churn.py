"""Treina classificador de churn (XGBoost) sobre delta.gold_ml.churn_dataset."""
from __future__ import annotations

import json
from typing import Final

import mlflow
import numpy as np
import pandas as pd
from loguru import logger
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from .mlflow_utils import ensure_experiment, promote_to_production, setup
from .trino_client import query

EXPERIMENT: Final = "melisimlake/churn"
MODEL_NAME: Final = "melisimlake_churn_xgb"

FEATURES: Final[list[str]] = [
    "recency_days",
    "frequency_per_week",
    "monetary",
    "avg_order_value",
    "tenure_days",
    "payment_fail_rate",
    "payments_total",
    "distinct_products",
]


def _safe_metric(fn, y_true, y_pred, **kw) -> float:
    try:
        return float(fn(y_true, y_pred, **kw))
    except Exception:
        return float("nan")


def run() -> dict:
    df = query(
        "SELECT buyer_id, recency_days, frequency_per_week, monetary, avg_order_value, "
        "tenure_days, payment_fail_rate, payments_total, distinct_products, churn_label "
        "FROM delta.gold_ml.churn_dataset"
    )
    if df.empty:
        logger.warning("[churn] dataset vazio, skip")
        return {"status": "skipped", "reason": "empty_dataset"}

    df = df.dropna(subset=["churn_label"]).copy()
    df[FEATURES] = df[FEATURES].astype(float).fillna(0.0)
    df["churn_label"] = df["churn_label"].astype(int)
    n = len(df)
    pos = int(df["churn_label"].sum())

    if df["churn_label"].nunique() < 2 or n < 6:
        logger.warning(f"[churn] dataset insuficiente n={n} pos={pos}, skip")
        return {"status": "skipped", "reason": "single_class_or_too_small", "n": n, "pos": pos}

    X = df[FEATURES].values
    y = df["churn_label"].values
    test_size = 0.25 if n >= 12 else 0.34
    min_class = int(min((y == 0).sum(), (y == 1).sum()))
    use_stratify = min_class >= 2
    X_tr, X_te, y_tr, y_te = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=42,
        stratify=y if use_stratify else None,
    )
    if len(set(y_tr)) < 2:
        logger.warning("[churn] split nao tem ambas classes no treino, usando dataset full")
        X_tr, y_tr, X_te, y_te = X, y, X, y

    pos_weight = max(1.0, (len(y_tr) - y_tr.sum()) / max(1, y_tr.sum()))
    params = dict(
        n_estimators=120,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=pos_weight,
        eval_metric="logloss",
        random_state=42,
    )

    setup()
    ensure_experiment(EXPERIMENT)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="churn_xgb") as run:
        mlflow.log_params(params)
        mlflow.log_param("n_samples", n)
        mlflow.log_param("n_positive", pos)
        mlflow.log_param("features", json.dumps(FEATURES))

        model = XGBClassifier(**params)
        model.fit(X_tr, y_tr)
        proba_te = model.predict_proba(X_te)[:, 1]
        pred_te = (proba_te >= 0.5).astype(int)

        metrics = {
            "test_accuracy": _safe_metric(accuracy_score, y_te, pred_te),
            "test_precision": _safe_metric(precision_score, y_te, pred_te, zero_division=0),
            "test_recall": _safe_metric(recall_score, y_te, pred_te, zero_division=0),
            "test_f1": _safe_metric(f1_score, y_te, pred_te, zero_division=0),
            "test_roc_auc": (
                _safe_metric(roc_auc_score, y_te, proba_te) if len(set(y_te)) == 2 else float("nan")
            ),
            "train_accuracy": _safe_metric(accuracy_score, y_tr, model.predict(X_tr)),
        }
        for k, v in metrics.items():
            if not np.isnan(v):
                mlflow.log_metric(k, v)

        signature = mlflow.models.infer_signature(X_tr, model.predict(X_tr))
        mlflow.xgboost.log_model(
            xgb_model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
            signature=signature,
            input_example=X_tr[:2],
        )

        from .mlflow_utils import setup as _setup_again  # noqa
        client = setup()
        latest = client.get_latest_versions(MODEL_NAME, stages=["None"])
        if latest:
            v = max(int(mv.version) for mv in latest)
            promote_to_production(client, MODEL_NAME, v)
            logger.info(f"[churn] {MODEL_NAME} v{v} promoted to Production")

    logger.info(f"[churn] metrics={metrics}")
    return {"status": "ok", "metrics": metrics, "n": n}


if __name__ == "__main__":  # pragma: no cover
    print(run())
