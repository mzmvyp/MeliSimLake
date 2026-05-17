"""Treina classificador de risco de falha de pagamento (XGBoost) sobre delta.gold_ml.payment_dataset."""
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

EXPERIMENT: Final = "melisimlake/payment_failure"
MODEL_NAME: Final = "melisimlake_payment_failure_xgb"
PAYMENT_METHODS: Final[list[str]] = ["credit_card", "pix", "boleto", "debit_card"]


def run() -> dict:
    df = query(
        "SELECT amount, method, hour, dow, buyer_pay_count, buyer_avg_amount, "
        "buyer_fail_rate_hist, failed_label "
        "FROM delta.gold_ml.payment_dataset"
    )
    if df.empty:
        logger.warning("[payment] dataset vazio, skip")
        return {"status": "skipped", "reason": "empty_dataset"}

    df = df.dropna(subset=["failed_label"]).copy()
    df["failed_label"] = df["failed_label"].astype(int)
    df["method"] = df["method"].astype(str).str.lower()
    for m in PAYMENT_METHODS:
        df[f"method_{m}"] = (df["method"] == m).astype(int)
    df = df.drop(columns=["method"])
    n = len(df)
    pos = int(df["failed_label"].sum())
    if df["failed_label"].nunique() < 2 or n < 6:
        logger.warning(f"[payment] dataset insuficiente n={n} pos={pos}, skip")
        return {"status": "skipped", "reason": "single_class_or_too_small", "n": n, "pos": pos}

    feature_cols = [c for c in df.columns if c != "failed_label"]
    df[feature_cols] = df[feature_cols].astype(float).fillna(0.0)
    X = df[feature_cols].values
    y = df["failed_label"].values
    test_size = 0.25 if n >= 16 else 0.34
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    pos_weight = max(1.0, (len(y_tr) - y_tr.sum()) / max(1, y_tr.sum()))

    params = dict(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=pos_weight,
        eval_metric="logloss",
        random_state=42,
    )

    setup()
    ensure_experiment(EXPERIMENT)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="payment_failure_xgb"):
        mlflow.log_params(params)
        mlflow.log_param("n_samples", n)
        mlflow.log_param("n_failed", pos)
        mlflow.log_param("features", json.dumps(feature_cols))
        model = XGBClassifier(**params)
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_te)[:, 1]
        pred = (proba >= 0.5).astype(int)
        metrics = {
            "test_accuracy": float(accuracy_score(y_te, pred)),
            "test_precision": float(precision_score(y_te, pred, zero_division=0)),
            "test_recall": float(recall_score(y_te, pred, zero_division=0)),
            "test_f1": float(f1_score(y_te, pred, zero_division=0)),
            "test_roc_auc": (
                float(roc_auc_score(y_te, proba)) if len(set(y_te)) == 2 else float("nan")
            ),
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
        client = setup()
        latest = client.get_latest_versions(MODEL_NAME, stages=["None"])
        if latest:
            v = max(int(mv.version) for mv in latest)
            promote_to_production(client, MODEL_NAME, v)
            logger.info(f"[payment] {MODEL_NAME} v{v} promoted to Production")

    logger.info(f"[payment] metrics={metrics}")
    return {"status": "ok", "metrics": metrics, "feature_cols": feature_cols, "n": n}


if __name__ == "__main__":  # pragma: no cover
    print(run())
