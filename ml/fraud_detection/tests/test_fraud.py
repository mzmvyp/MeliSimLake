"""Testes detecção de fraude."""

from __future__ import annotations

from ml.fraud_detection.src.xgboost_classifier import FEATURE_COLS, _generate_labeled_data


def test_generate_labeled_data_has_fraud() -> None:
    df = _generate_labeled_data(500)
    assert df["is_fraud"].sum() > 0


def test_generate_labeled_data_binary_label() -> None:
    df = _generate_labeled_data(100)
    assert set(df["is_fraud"].unique()).issubset({0, 1})


def test_feature_cols_all_present() -> None:
    df = _generate_labeled_data(100)
    for col in FEATURE_COLS:
        assert col in df.columns, f"Coluna ausente: {col}"
