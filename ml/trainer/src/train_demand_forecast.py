"""Treina LSTM de previsao de demanda diaria (orders + GMV) sobre delta.gold_ml.daily_demand."""
from __future__ import annotations

import json
import math
from typing import Final

import mlflow
import numpy as np
import pandas as pd
import torch
from loguru import logger
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

import tempfile
from pathlib import Path

from .mlflow_utils import ensure_experiment, promote_to_production, setup
from .trino_client import query

EXPERIMENT: Final = "melisimlake/demand_forecast"
MODEL_NAME: Final = "melisimlake_demand_forecast_lstm"
SEQ_LEN: Final = 7
HORIZON: Final = 7
HIDDEN: Final = 32
EPOCHS: Final = 200
BATCH_SIZE: Final = 16
N_FEATURES: Final = 2


class DemandLSTM(nn.Module):
    """LSTM simples para forecast multi-step. Arquitetura espelhada no ml-api
    para permitir load via state_dict (portabilidade)."""

    def __init__(self, n_features: int = N_FEATURES, hidden: int = HIDDEN) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden, batch_first=True)
        self.head = nn.Linear(hidden, n_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def _build_sequences(values: np.ndarray, seq_len: int) -> tuple[np.ndarray, np.ndarray]:
    if len(values) <= seq_len:
        return np.empty((0, seq_len, values.shape[1]), dtype=np.float32), np.empty(
            (0, values.shape[1]), dtype=np.float32
        )
    X, y = [], []
    for i in range(len(values) - seq_len):
        X.append(values[i : i + seq_len])
        y.append(values[i + seq_len])
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)


def _expand_short_series(df: pd.DataFrame, target_len: int = 60) -> pd.DataFrame:
    """Quando a serie real for curta, espelha/aleatoriza ao redor da media para
    sustentar treino. Mantem ultimos pontos reais ao final da serie."""
    if len(df) >= target_len:
        return df
    rng = np.random.default_rng(42)
    base = df[["orders", "gmv"]].astype(float).to_numpy()
    mean = base.mean(axis=0)
    std = base.std(axis=0) if base.shape[0] > 1 else mean * 0.2 + 1.0
    noise_size = target_len - len(df)
    noise = rng.normal(loc=mean, scale=np.maximum(std, mean * 0.1 + 1.0), size=(noise_size, 2))
    noise = np.clip(noise, a_min=0, a_max=None)
    synth = pd.DataFrame(noise, columns=["orders", "gmv"])
    end_date = pd.to_datetime(df["ds"].min()) - pd.Timedelta(days=1)
    synth["ds"] = pd.date_range(end=end_date, periods=noise_size).strftime("%Y-%m-%d")
    return pd.concat([synth[["ds", "orders", "gmv"]], df[["ds", "orders", "gmv"]]], ignore_index=True)


def run() -> dict:
    df = query("SELECT ds, orders, gmv FROM delta.gold_ml.daily_demand ORDER BY ds")
    if df.empty:
        logger.warning("[forecast] daily_demand vazio, skip")
        return {"status": "skipped", "reason": "empty_dataset"}

    df["ds"] = df["ds"].astype(str)
    df["orders"] = df["orders"].astype(float)
    df["gmv"] = df["gmv"].astype(float)
    real_len = len(df)
    df_aug = _expand_short_series(df, target_len=max(60, SEQ_LEN * 4))
    values = df_aug[["orders", "gmv"]].to_numpy(dtype=np.float32)

    mu = values.mean(axis=0)
    sigma = values.std(axis=0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    norm = (values - mu) / sigma
    X, y = _build_sequences(norm, SEQ_LEN)
    if len(X) < 10:
        logger.warning(f"[forecast] sequences insuficientes ({len(X)}), skip")
        return {"status": "skipped", "reason": "too_few_sequences", "n": len(X)}

    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]
    train_ds = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr))
    train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)

    model = DemandLSTM(n_features=2)
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = nn.MSELoss()
    losses = []
    for epoch in range(EPOCHS):
        model.train()
        epoch_loss = 0.0
        for xb, yb in train_dl:
            opt.zero_grad()
            out = model(xb)
            loss = loss_fn(out, yb)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * xb.size(0)
        losses.append(epoch_loss / max(1, len(train_ds)))

    model.eval()
    with torch.no_grad():
        if len(X_te):
            pred_te = model(torch.from_numpy(X_te)).numpy()
            mae = float(np.mean(np.abs(pred_te - y_te)))
            rmse = float(math.sqrt(np.mean((pred_te - y_te) ** 2)))
        else:
            mae = float("nan")
            rmse = float("nan")

        forecast = []
        last_seq = norm[-SEQ_LEN:].copy()
        for _ in range(HORIZON):
            tensor = torch.from_numpy(last_seq.astype(np.float32)).unsqueeze(0)
            nxt = model(tensor).numpy().flatten()
            forecast.append(nxt)
            last_seq = np.vstack([last_seq[1:], nxt])
        forecast_arr = np.asarray(forecast) * sigma + mu
        forecast_arr = np.clip(forecast_arr, a_min=0, a_max=None)

    setup()
    ensure_experiment(EXPERIMENT)
    mlflow.set_experiment(EXPERIMENT)
    with tempfile.TemporaryDirectory() as tmp:
        artroot = Path(tmp)
        sd_path = artroot / "state_dict.pt"
        torch.save(model.state_dict(), sd_path)
        with mlflow.start_run(run_name="demand_lstm"):
            mlflow.log_params(
                {
                    "seq_len": SEQ_LEN,
                    "hidden": HIDDEN,
                    "epochs": EPOCHS,
                    "batch_size": BATCH_SIZE,
                    "horizon": HORIZON,
                    "n_features": N_FEATURES,
                    "real_days": real_len,
                    "augmented_len": len(df_aug),
                }
            )
            mlflow.log_metric("train_loss_final", losses[-1])
            if not math.isnan(mae):
                mlflow.log_metric("val_mae", mae)
                mlflow.log_metric("val_rmse", rmse)
            mlflow.log_dict(
                {
                    "mu": mu.tolist(),
                    "sigma": sigma.tolist(),
                    "feature_order": ["orders", "gmv"],
                    "hidden": HIDDEN,
                    "n_features": N_FEATURES,
                },
                "scaler.json",
            )
            mlflow.log_artifact(str(sd_path), artifact_path="model")
            run_id = mlflow.active_run().info.run_id
            mv = mlflow.register_model(
                model_uri=f"runs:/{run_id}/model", name=MODEL_NAME
            )
            client = setup()
            promote_to_production(client, MODEL_NAME, int(mv.version))
            logger.info(f"[forecast] {MODEL_NAME} v{mv.version} promoted to Production")

    forecast_payload = [
        {"horizon_day": i + 1, "orders": float(v[0]), "gmv": float(v[1])}
        for i, v in enumerate(forecast_arr)
    ]
    logger.info(f"[forecast] mae={mae:.3f} rmse={rmse:.3f} preview={forecast_payload[:3]}")
    return {
        "status": "ok",
        "metrics": {"val_mae": mae, "val_rmse": rmse, "train_loss": losses[-1]},
        "forecast": forecast_payload,
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run(), indent=2, default=str))
