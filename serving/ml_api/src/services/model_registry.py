"""Carrega modelos do MLflow Registry e mantem cache em memoria.

Modelos servidos (todos treinados pelo servico ml-trainer):
  - melisimlake_churn_xgb               (xgboost classifier)
  - melisimlake_payment_failure_xgb     (xgboost classifier)
  - melisimlake_demand_forecast_lstm    (pytorch LSTM)
  - melisimlake_als_recommender         (implicit ALS bundle)
"""
from __future__ import annotations

import json
import os
import pickle
import tempfile
import time
from typing import Any

import mlflow
import numpy as np
from loguru import logger
from mlflow.tracking import MlflowClient

from serving.ml_api.src.core.config import settings


CHURN_MODEL = "melisimlake_churn_xgb"
PAYMENT_MODEL = "melisimlake_payment_failure_xgb"
FORECAST_MODEL = "melisimlake_demand_forecast_lstm"
ALS_MODEL = "melisimlake_als_recommender"

MODEL_NAMES: list[str] = [CHURN_MODEL, PAYMENT_MODEL, FORECAST_MODEL, ALS_MODEL]

_cache: dict[str, Any] = {}
_versions: dict[str, str] = {}
_metadata: dict[str, dict[str, Any]] = {}
_extras: dict[str, Any] = {}


def _ensure_minio_env() -> None:
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", settings.minio_endpoint)
    os.environ.setdefault("AWS_ACCESS_KEY_ID", settings.minio_access_key)
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", settings.minio_secret_key)


def _client() -> MlflowClient:
    _ensure_minio_env()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    return MlflowClient(tracking_uri=settings.mlflow_tracking_uri)


def _load_xgb(uri: str):
    return mlflow.xgboost.load_model(uri)


def _load_forecast_state_dict(client: MlflowClient, run_id: str, hidden: int, n_features: int):
    """Reconstroi DemandLSTM a partir de state_dict + scaler."""
    import torch

    from serving.ml_api.src.services.torch_models import DemandLSTM

    with tempfile.TemporaryDirectory() as tmp:
        local = client.download_artifacts(run_id, "model/state_dict.pt", tmp)
        sd = torch.load(local, map_location="cpu")
    model = DemandLSTM(n_features=n_features, hidden=hidden)
    model.load_state_dict(sd)
    model.eval()
    return model


def _load_als_bundle(client: MlflowClient, run_id: str) -> dict | None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = client.download_artifacts(run_id, "model/model.pkl", tmp)
            with open(local, "rb") as fh:
                bundle = pickle.load(fh)
            return bundle
    except Exception as exc:
        logger.warning(f"als bundle download falhou: {exc}")
        return None


def _load_forecast_scaler(client: MlflowClient, run_id: str) -> dict | None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = client.download_artifacts(run_id, "scaler.json", tmp)
            with open(local) as fh:
                return json.load(fh)
    except Exception as exc:
        logger.warning(f"scaler download falhou: {exc}")
        return None


def load_all_models() -> None:
    """Carrega todos os modelos do MLflow Registry no startup."""
    client = _client()
    for name in MODEL_NAMES:
        try:
            versions = client.get_latest_versions(name, stages=["Production", "Staging", "None"])
            if not versions:
                logger.warning(f"[registry] {name} sem versao no registry")
                continue
            versions.sort(key=lambda v: int(v.version), reverse=True)
            mv = versions[0]
            stage = mv.current_stage if mv.current_stage != "None" else "None"
            uri = (
                f"models:/{name}/{stage}"
                if stage in ("Production", "Staging")
                else f"models:/{name}/{mv.version}"
            )
            t0 = time.time()
            if name == CHURN_MODEL or name == PAYMENT_MODEL:
                model = _load_xgb(uri)
            elif name == FORECAST_MODEL:
                scaler = _load_forecast_scaler(client, mv.run_id) or {}
                hidden = int(scaler.get("hidden", 32))
                n_features = int(scaler.get("n_features", 2))
                model = _load_forecast_state_dict(client, mv.run_id, hidden, n_features)
                _extras[name] = {"scaler": scaler}
            elif name == ALS_MODEL:
                bundle = _load_als_bundle(client, mv.run_id)
                model = bundle  # bundle is the model
            else:
                continue
            _cache[name] = model
            _versions[name] = mv.version
            run = client.get_run(mv.run_id)
            _metadata[name] = {
                "stage": stage,
                "version": mv.version,
                "run_id": mv.run_id,
                "metrics": dict(run.data.metrics),
                "params": dict(run.data.params),
            }
            elapsed = round((time.time() - t0) * 1000, 1)
            logger.info(f"[registry] {name} v{mv.version} stage={stage} loaded in {elapsed}ms")
        except Exception as exc:
            logger.warning(f"[registry] {name} load FAIL: {exc}")


def reload() -> dict[str, str]:
    _cache.clear()
    _versions.clear()
    _metadata.clear()
    _extras.clear()
    load_all_models()
    return dict(_versions)


def get(name: str) -> Any:
    return _cache.get(name)


def get_extra(name: str) -> Any:
    return _extras.get(name)


def loaded() -> list[str]:
    return list(_cache.keys())


def metadata() -> dict[str, dict[str, Any]]:
    return _metadata


def list_registry_models() -> list[dict[str, Any]]:
    """Consulta MLflow Registry e retorna info de cada modelo + ultima versao."""
    client = _client()
    out: list[dict[str, Any]] = []
    try:
        for rm in client.search_registered_models():
            try:
                latest = sorted(
                    client.get_latest_versions(rm.name, stages=["Production", "Staging", "None"]),
                    key=lambda v: int(v.version),
                    reverse=True,
                )
                if not latest:
                    continue
                mv = latest[0]
                run = client.get_run(mv.run_id)
                out.append(
                    {
                        "name": rm.name,
                        "version": mv.version,
                        "stage": mv.current_stage,
                        "run_id": mv.run_id,
                        "metrics": dict(run.data.metrics),
                        "params": dict(run.data.params),
                        "loaded": rm.name in _cache,
                    }
                )
            except Exception as exc:
                logger.warning(f"meta {rm.name} fail: {exc}")
    except Exception as exc:
        logger.warning(f"search_registered_models fail: {exc}")
    return out
