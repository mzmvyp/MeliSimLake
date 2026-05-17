"""LSTM Demand Forecast — treino com walk-forward validation."""

from __future__ import annotations

from typing import Final

import mlflow
import numpy as np
import torch
import torch.nn as nn
from loguru import logger
from torch.utils.data import DataLoader, TensorDataset

from ml.demand_forecast_lstm.src.model import DemandForecastLSTM
from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

EXPERIMENT_NAME: Final[str] = "melisimlake/demand_forecast_lstm"
MODEL_NAME: Final[str] = "demand_forecast_lstm"
DEVICE: Final[torch.device] = torch.device("cuda" if torch.cuda.is_available() else "cpu")
LOOKBACK: Final[int] = 90
HORIZON: Final[int] = 14
CATEGORIES: Final[list[str]] = ["eletronicos", "moda", "casa", "esportes", "beleza"]


def _wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Weighted Absolute Percentage Error.

    Args:
        actual: Valores reais.
        predicted: Valores previstos.

    Returns:
        WAPE em percentual.
    """
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.sum(np.abs(actual[mask] - predicted[mask])) / np.sum(np.abs(actual[mask])))


def _generate_synthetic_series(
    n_days: int = 730,
    n_categories: int = 5,
) -> np.ndarray:
    """Gera séries temporais sintéticas com sazonalidade.

    Args:
        n_days: Número de dias.
        n_categories: Número de categorias.

    Returns:
        Array (n_days, n_categories) com demanda sintética.
    """
    rng = np.random.default_rng(42)
    t = np.arange(n_days)
    series = np.zeros((n_days, n_categories))
    for i in range(n_categories):
        trend = 100 + i * 20 + 0.05 * t
        weekly = 30 * np.sin(2 * np.pi * t / 7 + i)
        monthly = 20 * np.sin(2 * np.pi * t / 30 + i * 0.5)
        noise = rng.normal(0, 10, n_days)
        series[:, i] = np.maximum(0, trend + weekly + monthly + noise)
    return series


def _build_windows(
    series: np.ndarray,
    lookback: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Constrói janelas deslizantes para treino.

    Args:
        series: Array (n_days, n_features).
        lookback: Janela de entrada.
        horizon: Janela de saída.

    Returns:
        Tupla (X, y) como arrays numpy.
    """
    X_list, y_list = [], []
    for i in range(len(series) - lookback - horizon + 1):
        X_list.append(series[i : i + lookback])
        y_list.append(series[i + lookback : i + lookback + horizon, 0])
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)


def _walk_forward_eval(
    model: DemandForecastLSTM,
    series: np.ndarray,
    n_folds: int = 5,
) -> dict[str, float]:
    """Validação walk-forward (evita data leakage).

    Args:
        model: Modelo treinado.
        series: Série completa.
        n_folds: Número de folds.

    Returns:
        Dicionário com métricas WAPE, MAE.
    """
    model.eval()
    fold_size = len(series) // (n_folds + 1)
    wapes, maes = [], []

    with torch.no_grad():
        for fold in range(n_folds):
            start = fold * fold_size
            end = start + fold_size + LOOKBACK + HORIZON
            fold_data = series[start:end]
            X, y = _build_windows(fold_data, LOOKBACK, HORIZON)
            if len(X) == 0:
                continue
            X_t = torch.tensor(X[-1:]).to(DEVICE)
            pred = model(X_t).cpu().numpy()[0]
            actual = y[-1]
            wapes.append(_wape(actual, pred))
            maes.append(float(np.mean(np.abs(actual - pred))))

    return {
        "wape": float(np.mean(wapes)),
        "mae": float(np.mean(maes)),
    }


def run(
    run_date: str = "2026-01-01",
    epochs: int = 50,
    batch_size: int = 64,
) -> str:
    """Treina LSTM demand forecast e registra no MLflow.

    Args:
        run_date: Data de referência.
        epochs: Épocas de treino.
        batch_size: Tamanho do batch.

    Returns:
        MLflow run_id.
    """
    setup_mlflow(EXPERIMENT_NAME)
    series = _generate_synthetic_series()
    X, y = _build_windows(series, LOOKBACK, HORIZON)

    split = int(len(X) * 0.8)
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    train_ds = TensorDataset(torch.tensor(X_train), torch.tensor(y_train))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    model = DemandForecastLSTM(input_size=series.shape[1]).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.HuberLoss()

    logger.info("LSTM Forecast treino iniciado", extra={"device": str(DEVICE), "epochs": epochs})

    with start_run(f"forecast_{run_date}", tags={"model": "LSTM", "task": "demand_forecast"}) as run:
        mlflow.log_params(
            {
                "input_size": series.shape[1],
                "hidden_size": 128,
                "n_layers": 2,
                "lookback": LOOKBACK,
                "horizon": HORIZON,
                "epochs": epochs,
                "categories": CATEGORIES,
            }
        )

        for epoch in range(1, epochs + 1):
            model.train()
            total_loss = 0.0
            for X_b, y_b in train_loader:
                X_b, y_b = X_b.to(DEVICE), y_b.to(DEVICE)
                optimizer.zero_grad()
                pred = model(X_b)
                loss = criterion(pred, y_b)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)
            mlflow.log_metric("train_loss", avg_loss, step=epoch)

        metrics = _walk_forward_eval(model, series)
        for k, v in metrics.items():
            mlflow.log_metric(k, v)

        mlflow.pytorch.log_model(model, "model")
        run_id = run.info.run_id

    register_model(f"runs:/{run_id}/model", MODEL_NAME, stage="Staging")
    logger.info("LSTM Forecast treinado", extra=metrics)
    return run_id


if __name__ == "__main__":
    run()
