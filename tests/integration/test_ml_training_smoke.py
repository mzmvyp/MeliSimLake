"""Smoke tests de treinamento ML — verificam que os jobs terminam sem exceção."""

from __future__ import annotations

import os

import pytest

# These tests require no external services — they use synthetic fallback data.
# They do require torch, xgboost, implicit to be installed.


def _has_package(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


@pytest.mark.skipif(not _has_package("implicit"), reason="implicit not installed")
def test_als_training_smoke() -> None:
    from ml.recommendation_als.src.train import train

    run_id = train(n_factors=8, n_iterations=2, use_synthetic=True)
    assert run_id is not None


@pytest.mark.skipif(not _has_package("xgboost"), reason="xgboost not installed")
def test_churn_training_smoke() -> None:
    from ml.churn_xgboost.src.train import train

    run_id = train(n_trials=1, use_synthetic=True)
    assert run_id is not None


@pytest.mark.skipif(not _has_package("xgboost"), reason="xgboost not installed")
def test_fraud_training_smoke() -> None:
    from ml.fraud_detection.src.train import train

    run_id = train(use_synthetic=True)
    assert run_id is not None


@pytest.mark.skipif(not _has_package("torch"), reason="torch not installed")
def test_gru4rec_training_smoke() -> None:
    from ml.recommendation_gru4rec.src.train import train

    run_id = train(epochs=1, use_synthetic=True)
    assert run_id is not None


@pytest.mark.skipif(not _has_package("torch"), reason="torch not installed")
def test_demand_forecast_training_smoke() -> None:
    from ml.demand_forecast_lstm.src.train import train

    run_id = train(epochs=2, use_synthetic=True)
    assert run_id is not None
