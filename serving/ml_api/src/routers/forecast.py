"""Endpoint de forecast de demanda."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import numpy as np
import torch
from fastapi import APIRouter, HTTPException

from serving.ml_api.src.schemas.requests import DemandForecastRequest
from serving.ml_api.src.schemas.responses import ForecastPoint, ForecastResponse
from serving.ml_api.src.services import model_registry as reg
from serving.ml_api.src.services import trino_features as feats

router = APIRouter(tags=["forecast"])

SEQ_LEN = 7


@router.post("/forecast/demand", response_model=ForecastResponse)
def forecast_demand(req: DemandForecastRequest) -> ForecastResponse:
    model = reg.get(reg.FORECAST_MODEL)
    extras = reg.get_extra(reg.FORECAST_MODEL) or {}
    scaler = extras.get("scaler") or {}
    if model is None or not scaler:
        raise HTTPException(
            status_code=503, detail="modelo demand_forecast indisponivel (treino pendente)"
        )

    df = feats.latest_demand_window(seq_len=SEQ_LEN)
    if df.empty or len(df) < 1:
        raise HTTPException(status_code=503, detail="sem dados em gold_ml.daily_demand")

    feature_order = scaler.get("feature_order", ["orders", "gmv"])
    mu = np.asarray(scaler.get("mu", [0, 0]), dtype=np.float32)
    sigma = np.asarray(scaler.get("sigma", [1, 1]), dtype=np.float32)
    sigma = np.where(sigma == 0, 1.0, sigma)

    history = df[["orders", "gmv"]].astype(float).to_numpy(dtype=np.float32)
    if len(history) < SEQ_LEN:
        last = history[-1] if len(history) else mu
        pad = np.tile(last, (SEQ_LEN - len(history), 1))
        history_padded = np.vstack([pad, history])
    else:
        history_padded = history[-SEQ_LEN:]

    norm = (history_padded - mu) / sigma
    last_seq = norm.copy()
    horizon = int(req.horizon_days)
    forecast: list[np.ndarray] = []

    t0 = time.time()
    model.eval()
    with torch.no_grad():
        for _ in range(horizon):
            tensor = torch.from_numpy(last_seq.astype(np.float32)).unsqueeze(0)
            nxt = model(tensor).cpu().numpy().flatten()
            forecast.append(nxt)
            last_seq = np.vstack([last_seq[1:], nxt])
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    forecast_arr = np.asarray(forecast) * sigma + mu
    forecast_arr = np.clip(forecast_arr, a_min=0, a_max=None)

    last_date = datetime.fromisoformat(str(df["ds"].iloc[-1]))
    points = [
        ForecastPoint(
            horizon_day=i + 1,
            date=(last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
            orders=float(forecast_arr[i, 0]),
            gmv=float(forecast_arr[i, 1]),
        )
        for i in range(horizon)
    ]
    history_dicts = [
        {"date": str(r.ds), "orders": float(r.orders), "gmv": float(r.gmv)}
        for r in df.itertuples()
    ]
    return ForecastResponse(
        horizon_days=horizon,
        history_used=history_dicts,
        forecast=points,
        model=reg.FORECAST_MODEL,
        model_version=reg._versions.get(reg.FORECAST_MODEL, "unknown"),
        inference_ms=elapsed_ms,
    )
