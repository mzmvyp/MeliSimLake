"""Testes E2E — ML API rodando via TestClient com mocks de modelos."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    _als = MagicMock()
    _als.recommend.return_value = (np.array([10, 20, 30, 40, 50]), np.array([0.9, 0.8, 0.7, 0.6, 0.5]))

    _churn = MagicMock()
    _churn.predict_proba.return_value = np.array([[0.3, 0.7]])

    _fraud = MagicMock()
    _fraud.predict_proba.return_value = np.array([[0.95, 0.05]])

    _gru = MagicMock()
    _gru.return_value = MagicMock()

    _lstm = MagicMock()
    _lstm.return_value = MagicMock()

    mock_models = {
        "als_recommender": _als,
        "churn_xgboost": _churn,
        "fraud_xgboost": _fraud,
        "gru4rec": _gru,
        "demand_lstm": _lstm,
    }

    with (
        patch("serving.ml_api.src.services.model_registry.load_all_models"),
        patch("serving.ml_api.src.services.model_registry._models", mock_models),
        patch("serving.ml_api.src.services.model_registry._model_versions", {k: "1" for k in mock_models}),
    ):
        from serving.ml_api.src.main import app
        return TestClient(app)


class TestHealthAndSystem:
    def test_health_ok(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "models_loaded" in body

    def test_models_list(self, client: TestClient) -> None:
        r = client.get("/models")
        assert r.status_code == 200
        assert "models" in r.json()

    def test_docs_accessible(self, client: TestClient) -> None:
        r = client.get("/docs")
        assert r.status_code == 200

    def test_metrics_endpoint(self, client: TestClient) -> None:
        r = client.get("/metrics")
        assert r.status_code == 200


class TestRecommendations:
    def test_user_recommendations_default_n(self, client: TestClient) -> None:
        r = client.post("/recommend/user/user_abc", json={"n": 10})
        assert r.status_code == 200
        body = r.json()
        assert "recommendations" in body
        assert "request_id" in body

    def test_user_recommendations_n_5(self, client: TestClient) -> None:
        r = client.post("/recommend/user/user_abc", json={"n": 5})
        assert r.status_code == 200
        assert len(r.json()["recommendations"]) == 5

    def test_session_recommendations(self, client: TestClient) -> None:
        r = client.post(
            "/recommend/session",
            json={"session_items": ["item1", "item2", "item3"], "n": 5},
        )
        assert r.status_code == 200
        assert "recommendations" in r.json()

    def test_session_single_item(self, client: TestClient) -> None:
        r = client.post(
            "/recommend/session",
            json={"session_items": ["item1"], "n": 3},
        )
        assert r.status_code == 200

    def test_session_empty_items_rejected(self, client: TestClient) -> None:
        r = client.post("/recommend/session", json={"session_items": [], "n": 5})
        assert r.status_code == 422


class TestPredictions:
    def test_churn_prediction(self, client: TestClient) -> None:
        r = client.post("/predict/churn/user123")
        assert r.status_code == 200
        body = r.json()
        assert "churn_probability" in body
        assert 0.0 <= body["churn_probability"] <= 1.0

    def test_fraud_prediction_low_risk(self, client: TestClient) -> None:
        r = client.post(
            "/predict/fraud",
            json={
                "total_amount": 100.0,
                "items_count": 1,
                "hour_of_day": 10,
                "days_since_account_creation": 730,
                "orders_in_last_hour": 0,
                "avg_order_value_deviation": 0.05,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert "fraud_probability" in body
        assert 0.0 <= body["fraud_probability"] <= 1.0

    def test_fraud_prediction_missing_field(self, client: TestClient) -> None:
        r = client.post(
            "/predict/fraud",
            json={"total_amount": 100.0},
        )
        assert r.status_code == 422


class TestForecast:
    def test_demand_forecast_7d(self, client: TestClient) -> None:
        r = client.post("/forecast/demand/eletronicos", json={"horizon_days": 7})
        assert r.status_code == 200
        body = r.json()
        assert len(body["forecast"]) == 7
        assert len(body["dates"]) == 7

    def test_demand_forecast_14d(self, client: TestClient) -> None:
        r = client.post("/forecast/demand/moda", json={"horizon_days": 14})
        assert r.status_code == 200
        assert len(r.json()["forecast"]) == 14

    def test_demand_forecast_invalid_horizon(self, client: TestClient) -> None:
        r = client.post("/forecast/demand/eletronicos", json={"horizon_days": 0})
        assert r.status_code == 422
