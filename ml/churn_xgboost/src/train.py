"""XGBoost Churn — treino com Optuna + SHAP + calibração."""

from __future__ import annotations

import os
from typing import Final

import mlflow
import numpy as np
import optuna
import pandas as pd
import shap
import xgboost as xgb
from loguru import logger
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

MODEL_NAME: Final[str] = "churn_xgboost"
EXPERIMENT_NAME: Final[str] = "melisimlake/churn_xgboost"
OPTUNA_TRIALS: Final[int] = 50

FEATURE_COLS: Final[list[str]] = [
    "total_orders",
    "total_revenue",
    "avg_order_value",
    "days_since_last_order",
    "orders_last_30d",
    "orders_last_90d",
    "avg_items_per_order",
    "customer_tenure_days",
    "recency_ratio",
    "r_score",
    "f_score",
    "m_score",
    "rfm_total",
]
TARGET_COL: Final[str] = "churn_label"


def _load_data(run_date: str) -> pd.DataFrame:
    """Carrega features de churn do Gold."""
    try:
        import trino

        conn = trino.dbapi.connect(
            host=os.environ.get("TRINO_HOST", "trino"),
            port=int(os.environ.get("TRINO_PORT", "8084")),
            user="admin",
            catalog="delta",
            schema="gold",
        )
        return pd.read_sql(
            f"SELECT * FROM churn_features WHERE first_order_date <= DATE '{run_date}'",
            conn,
        )
    except Exception as exc:
        logger.warning("Trino indisponível — dados sintéticos", extra={"error": str(exc)})
        rng = np.random.default_rng(42)
        n = 3000
        df = pd.DataFrame(rng.random((n, len(FEATURE_COLS))), columns=FEATURE_COLS)
        df[TARGET_COL] = rng.integers(0, 2, n)
        return df


def _objective(
    trial: optuna.Trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> float:
    """Função objetivo Optuna para XGBoost.

    Args:
        trial: Trial Optuna.
        X_train: Features de treino.
        y_train: Labels de treino.
        X_val: Features de validação.
        y_val: Labels de validação.

    Returns:
        AUC-ROC de validação.
    """
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 500),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.01, 10.0, log=True),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 10.0),
        "use_label_encoder": False,
        "eval_metric": "auc",
        "random_state": 42,
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    preds = model.predict_proba(X_val)[:, 1]
    return roc_auc_score(y_val, preds)


def run(run_date: str = "2026-01-01") -> str:
    """Treina XGBoost churn com Optuna e registra no MLflow.

    Args:
        run_date: Data de referência.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    df = _load_data(run_date)
    logger.info("Dados carregados", extra={"rows": len(df), "churn_rate": df[TARGET_COL].mean()})

    available_features = [c for c in FEATURE_COLS if c in df.columns]
    X = df[available_features].fillna(0).values
    y = df[TARGET_COL].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_tr, X_val, y_tr, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=42)

    logger.info("Iniciando Optuna", extra={"trials": OPTUNA_TRIALS})
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize")
    study.optimize(
        lambda trial: _objective(trial, X_tr, y_tr, X_val, y_val),
        n_trials=OPTUNA_TRIALS,
    )

    best_params = study.best_params
    best_params.update({"use_label_encoder": False, "eval_metric": "auc", "random_state": 42})
    logger.info("Melhor AUC Optuna", extra={"auc": study.best_value, "params": best_params})

    base_model = xgb.XGBClassifier(**best_params)
    base_model.fit(X_tr, y_tr, verbose=False)
    calibrated = CalibratedClassifierCV(base_model, cv="prefit")
    calibrated.fit(X_val, y_val)

    preds_proba = calibrated.predict_proba(X_test)[:, 1]
    preds_class = (preds_proba > 0.5).astype(int)
    auc = roc_auc_score(y_test, preds_proba)
    f1 = f1_score(y_test, preds_class)

    explainer = shap.TreeExplainer(base_model)
    shap_values = explainer.shap_values(X_test[:200])

    with start_run(f"churn_{run_date}", tags={"model": "XGBoost", "date": run_date}) as run:
        mlflow.log_params(best_params)
        mlflow.log_metrics({"test_auc": auc, "test_f1": f1, "optuna_best_val_auc": study.best_value})
        mlflow.log_metric("churn_rate", float(y.mean()))

        shap.summary_plot(shap_values, X_test[:200], feature_names=available_features, show=False)
        import matplotlib.pyplot as plt
        plt.tight_layout()
        mlflow.log_figure(plt.gcf(), "shap_summary.png")
        plt.close()

        mlflow.sklearn.log_model(calibrated, "model")
        run_id = run.info.run_id

    register_model(
        f"runs:/{run_id}/model",
        MODEL_NAME,
        stage="Staging",
        description=f"XGBoost Churn calibrado — AUC={auc:.4f} — run {run_date}",
    )

    logger.info("Churn XGBoost treinado", extra={"auc": auc, "f1": f1})
    return run_id


if __name__ == "__main__":
    run()
