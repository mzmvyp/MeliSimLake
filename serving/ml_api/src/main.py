"""MeliSimLake ML API - FastAPI app servindo modelos do MLflow Registry."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import mlflow
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import Counter, Histogram, make_asgi_app

from serving.ml_api.src.core.config import settings
from serving.ml_api.src.routers import forecast, predictions, recommendations
from serving.ml_api.src.schemas.responses import (
    HealthResponse,
    ModelInfo,
    ModelListResponse,
)
from serving.ml_api.src.services import model_registry as reg

REQUEST_COUNT = Counter(
    "melisimlake_api_requests_total", "Requisicoes totais", ["endpoint", "method"]
)
REQUEST_LATENCY = Histogram(
    "melisimlake_api_latency_seconds", "Latencia de requisicao (s)", ["endpoint"]
)
ERROR_COUNT = Counter("melisimlake_api_errors_total", "Erros totais", ["endpoint"])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("ML API starting - loading models from MLflow registry...")
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    reg.load_all_models()
    logger.info(f"ML API ready: models loaded={reg.loaded()}")
    yield
    logger.info("ML API shutdown.")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Serving REST de modelos ML do MeliSimLake (XGBoost churn, XGBoost payment fraud, LSTM forecast, ALS recommender).",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    start = time.time()
    try:
        response = await call_next(request)
        REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start)
        return response
    except Exception:
        ERROR_COUNT.labels(endpoint=endpoint).inc()
        raise


app.include_router(predictions.router)
app.include_router(forecast.router)
app.include_router(recommendations.router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", models_loaded=reg.loaded())


@app.get("/models", response_model=ModelListResponse, tags=["system"])
def list_models() -> ModelListResponse:
    raw = reg.list_registry_models()
    return ModelListResponse(
        models=[
            ModelInfo(
                name=m["name"],
                version=str(m["version"]),
                stage=str(m.get("stage", "None")),
                run_id=str(m.get("run_id", "")),
                metrics={k: float(v) for k, v in (m.get("metrics") or {}).items()},
                params={k: str(v) for k, v in (m.get("params") or {}).items()},
                loaded=bool(m.get("loaded", False)),
            )
            for m in raw
        ]
    )


@app.post("/models/reload", tags=["system"])
def reload_models() -> dict:
    versions = reg.reload()
    return {"reloaded": versions, "loaded": reg.loaded()}
