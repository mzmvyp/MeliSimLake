"""Schemas Pydantic v2 de request da ML API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PaymentFraudRequest(BaseModel):
    buyer_id: str | None = Field(default=None, description="ID do comprador (opcional, para enriquecimento)")
    amount: float = Field(gt=0, description="Valor do pagamento")
    method: str = Field(description="Metodo (credit_card | pix | boleto | debit_card)")
    hour: int | None = Field(default=None, ge=0, le=23)
    dow: int | None = Field(default=None, ge=1, le=7)


class DemandForecastRequest(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=30)


class RecommendUserRequest(BaseModel):
    k: int = Field(default=5, ge=1, le=20)
    filter_seen: bool = Field(default=False)
