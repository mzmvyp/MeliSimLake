"""Testes da ML API."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    with patch("serving.ml_api.src.services.model_registry.load_all_models"):
        from serving.ml_api.src.main import app
        return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "models_loaded" in data


def test_models_endpoint(client: TestClient) -> None:
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data


def test_recommend_user_endpoint(client: TestClient) -> None:
    response = client.post("/recommend/user/user123", json={"n": 5})
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) == 5


def test_recommend_session_endpoint(client: TestClient) -> None:
    response = client.post(
        "/recommend/session",
        json={"session_items": ["p1", "p2", "p3"], "n": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data


def test_predict_churn_endpoint(client: TestClient) -> None:
    response = client.post("/predict/churn/user123")
    assert response.status_code == 200
    data = response.json()
    assert "churn_probability" in data
    assert 0.0 <= data["churn_probability"] <= 1.0


def test_predict_fraud_endpoint(client: TestClient) -> None:
    response = client.post(
        "/predict/fraud",
        json={
            "total_amount": 500.0,
            "items_count": 3,
            "hour_of_day": 14,
            "days_since_account_creation": 365,
            "orders_in_last_hour": 1,
            "avg_order_value_deviation": 0.2,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "fraud_probability" in data


def test_forecast_demand_endpoint(client: TestClient) -> None:
    response = client.post("/forecast/demand/eletronicos", json={"horizon_days": 7})
    assert response.status_code == 200
    data = response.json()
    assert len(data["forecast"]) == 7
    assert len(data["dates"]) == 7
