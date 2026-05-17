"""Testes do módulo ALS."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import pytest

from ml.recommendation_als.src.train import _build_sparse_matrix
import pandas as pd


def test_build_sparse_matrix_dimensions() -> None:
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u3"],
            "product_id": ["p1", "p2", "p1", "p3"],
            "interaction_count": [5, 3, 2, 7],
        }
    )
    matrix, users, items = _build_sparse_matrix(df)
    assert matrix.shape == (3, 3)
    assert len(users) == 3
    assert len(items) == 3


def test_build_sparse_matrix_values() -> None:
    df = pd.DataFrame(
        {"user_id": ["u1"], "product_id": ["p1"], "interaction_count": [10]}
    )
    matrix, users, items = _build_sparse_matrix(df)
    u_idx = users["u1"]
    p_idx = items["p1"]
    assert matrix[u_idx, p_idx] == 10.0


def test_precision_at_k_perfect() -> None:
    from ml.shared.metrics import precision_at_k
    recommended = [[1, 2, 3, 4, 5]]
    relevant = [[1, 2, 3]]
    assert precision_at_k(recommended, relevant, k=3) == pytest.approx(1.0)


def test_recall_at_k_partial() -> None:
    from ml.shared.metrics import recall_at_k
    recommended = [[1, 2, 99, 100, 101]]
    relevant = [[1, 2, 3, 4, 5]]
    result = recall_at_k(recommended, relevant, k=5)
    assert 0.0 < result < 1.0
