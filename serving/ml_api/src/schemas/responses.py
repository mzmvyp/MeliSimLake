"""Schemas Pydantic v2 de response da ML API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


def _new_id() -> str:
    return str(uuid.uuid4())


class BaseResponse(BaseModel):
    request_id: str = Field(default_factory=_new_id)
    model: str = ""
    model_version: str = "unknown"
    inference_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


class ChurnResponse(BaseResponse):
    user_id: str
    churn_probability: float
    churn_risk: str
    features_used: dict = Field(default_factory=dict)
    fallback: bool = False


class PaymentFraudResponse(BaseResponse):
    failure_probability: float
    is_high_risk: bool
    risk_band: str
    features_used: dict = Field(default_factory=dict)
    fallback: bool = False


class ForecastPoint(BaseModel):
    horizon_day: int
    date: str
    orders: float
    gmv: float


class ForecastResponse(BaseResponse):
    horizon_days: int
    history_used: list[dict]
    forecast: list[ForecastPoint]


class RecommendationItem(BaseModel):
    product_id: str
    score: float
    title: str | None = None
    category: str | None = None
    price: float | None = None


class RecommendationResponse(BaseResponse):
    user_id: str
    recommendations: list[RecommendationItem]
    cold_start: bool = False


class HealthResponse(BaseModel):
    status: str
    models_loaded: list[str]
    timestamp: datetime = Field(default_factory=datetime.now)


class ModelInfo(BaseModel):
    name: str
    version: str
    stage: str
    run_id: str
    metrics: dict
    params: dict
    loaded: bool


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
