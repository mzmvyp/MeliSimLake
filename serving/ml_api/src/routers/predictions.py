"""Endpoints de previsao: churn e payment failure."""
from __future__ import annotations

import time

import numpy as np
from fastapi import APIRouter, HTTPException

from serving.ml_api.src.schemas.requests import PaymentFraudRequest
from serving.ml_api.src.schemas.responses import ChurnResponse, PaymentFraudResponse
from serving.ml_api.src.services import model_registry as reg
from serving.ml_api.src.services import trino_features as feats

router = APIRouter(tags=["predictions"])


CHURN_FEATURES = [
    "recency_days",
    "frequency_per_week",
    "monetary",
    "avg_order_value",
    "tenure_days",
    "payment_fail_rate",
    "payments_total",
    "distinct_products",
]

PAYMENT_METHODS = ["credit_card", "pix", "boleto", "debit_card"]
PAYMENT_FEATURES = [
    "amount",
    "hour",
    "dow",
    "buyer_pay_count",
    "buyer_avg_amount",
    "buyer_fail_rate_hist",
] + [f"method_{m}" for m in PAYMENT_METHODS]


def _band(p: float) -> str:
    if p >= 0.7:
        return "high"
    if p >= 0.4:
        return "medium"
    return "low"


@router.post("/predict/churn/{user_id}", response_model=ChurnResponse)
def predict_churn(user_id: str) -> ChurnResponse:
    model = reg.get(reg.CHURN_MODEL)
    feats_row = feats.user_features_row(user_id)
    if feats_row is None:
        raise HTTPException(status_code=404, detail=f"buyer {user_id} sem features (sem pedidos historicos)")
    if model is None:
        return ChurnResponse(
            user_id=user_id,
            churn_probability=0.5,
            churn_risk="medium",
            features_used=feats_row,
            fallback=True,
            model=reg.CHURN_MODEL,
            model_version=reg._versions.get(reg.CHURN_MODEL, "unloaded"),
        )
    vec = np.asarray([[float(feats_row.get(c, 0.0) or 0.0) for c in CHURN_FEATURES]], dtype=np.float32)
    t0 = time.time()
    try:
        from xgboost import DMatrix
        proba = float(model.predict(DMatrix(vec))[0])
    except Exception:
        proba = float(model.predict_proba(vec)[0, 1])
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return ChurnResponse(
        user_id=user_id,
        churn_probability=round(proba, 4),
        churn_risk=_band(proba),
        features_used={k: float(v) if isinstance(v, (int, float)) else v for k, v in feats_row.items()},
        model=reg.CHURN_MODEL,
        model_version=reg._versions.get(reg.CHURN_MODEL, "unknown"),
        inference_ms=elapsed_ms,
    )


@router.post("/predict/payment_fraud", response_model=PaymentFraudResponse)
def predict_payment_fraud(req: PaymentFraudRequest) -> PaymentFraudResponse:
    model = reg.get(reg.PAYMENT_MODEL)
    method = req.method.lower()
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"metodo invalido. use {PAYMENT_METHODS}")
    history = feats.user_payment_history(req.buyer_id) if req.buyer_id else None
    hist = history or {"buyer_pay_count": 0, "buyer_avg_amount": 0.0, "buyer_fail_rate_hist": 0.0}
    payload = {
        "amount": float(req.amount),
        "hour": int(req.hour) if req.hour is not None else 12,
        "dow": int(req.dow) if req.dow is not None else 3,
        "buyer_pay_count": float(hist.get("buyer_pay_count") or 0.0),
        "buyer_avg_amount": float(hist.get("buyer_avg_amount") or 0.0),
        "buyer_fail_rate_hist": float(hist.get("buyer_fail_rate_hist") or 0.0),
    }
    for m in PAYMENT_METHODS:
        payload[f"method_{m}"] = 1.0 if m == method else 0.0
    if model is None:
        proba = 0.9 if req.amount >= 100_000 else 0.05
        return PaymentFraudResponse(
            failure_probability=proba,
            is_high_risk=proba >= 0.5,
            risk_band=_band(proba),
            features_used=payload,
            fallback=True,
            model=reg.PAYMENT_MODEL,
            model_version=reg._versions.get(reg.PAYMENT_MODEL, "unloaded"),
        )
    vec = np.asarray([[payload[c] for c in PAYMENT_FEATURES]], dtype=np.float32)
    t0 = time.time()
    try:
        from xgboost import DMatrix
        proba = float(model.predict(DMatrix(vec))[0])
    except Exception:
        proba = float(model.predict_proba(vec)[0, 1])
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return PaymentFraudResponse(
        failure_probability=round(proba, 4),
        is_high_risk=proba >= 0.5,
        risk_band=_band(proba),
        features_used=payload,
        model=reg.PAYMENT_MODEL,
        model_version=reg._versions.get(reg.PAYMENT_MODEL, "unknown"),
        inference_ms=elapsed_ms,
    )
