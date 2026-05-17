"""Testes LSTM Demand Forecast."""

from __future__ import annotations

import numpy as np
import torch
import pytest

from ml.demand_forecast_lstm.src.model import DemandForecastLSTM
from ml.demand_forecast_lstm.src.train import (
    HORIZON,
    LOOKBACK,
    _build_windows,
    _generate_synthetic_series,
    _wape,
)


def test_model_output_shape() -> None:
    model = DemandForecastLSTM(input_size=3, hidden_size=32, output_size=14)
    x = torch.randn(4, 90, 3)
    out = model(x)
    assert out.shape == (4, 14)


def test_model_no_nan() -> None:
    model = DemandForecastLSTM(input_size=3, hidden_size=32, output_size=14)
    x = torch.randn(2, 90, 3)
    out = model(x)
    assert not torch.isnan(out).any()


def test_generate_synthetic_series_shape() -> None:
    series = _generate_synthetic_series(n_days=100, n_categories=3)
    assert series.shape == (100, 3)
    assert (series >= 0).all()


def test_build_windows_count() -> None:
    series = _generate_synthetic_series(n_days=100, n_categories=2)
    X, y = _build_windows(series, lookback=10, horizon=5)
    expected = 100 - 10 - 5 + 1
    assert len(X) == expected
    assert len(y) == expected


def test_wape_perfect() -> None:
    actual = np.array([10.0, 20.0, 30.0])
    assert _wape(actual, actual) == pytest.approx(0.0)


def test_wape_zero_actual() -> None:
    actual = np.array([0.0, 0.0])
    predicted = np.array([1.0, 2.0])
    assert _wape(actual, predicted) == 0.0
