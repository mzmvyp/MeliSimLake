"""Testes do XGBoost churn."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.churn_xgboost.src.train import FEATURE_COLS, TARGET_COL, _load_data


def test_load_data_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    """_load_data deve retornar DataFrame com colunas esperadas."""
    result = _load_data("2026-01-01")
    assert isinstance(result, pd.DataFrame)
    assert TARGET_COL in result.columns


def test_feature_cols_defined() -> None:
    assert len(FEATURE_COLS) >= 5


def test_load_data_no_nulls_in_label(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _load_data("2026-01-01")
    assert result[TARGET_COL].isna().sum() == 0


def test_load_data_binary_label(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _load_data("2026-01-01")
    assert set(result[TARGET_COL].unique()).issubset({0, 1})
