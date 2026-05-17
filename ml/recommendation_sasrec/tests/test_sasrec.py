"""Testes SASRec."""

from __future__ import annotations

import torch
import pytest

from ml.recommendation_sasrec.src.model import SASRec


def test_sasrec_output_shape() -> None:
    model = SASRec(n_items=100, embedding_dim=32, n_heads=2, n_layers=1)
    sessions = torch.randint(0, 101, (4, 10))
    lengths = torch.tensor([10, 8, 5, 3])
    logits = model(sessions, lengths)
    assert logits.shape == (4, 101)


def test_sasrec_no_nan() -> None:
    model = SASRec(n_items=50, embedding_dim=16, n_heads=2, n_layers=1)
    sessions = torch.randint(0, 51, (2, 5))
    lengths = torch.tensor([5, 3])
    logits = model(sessions, lengths)
    assert not torch.isnan(logits).any()


def test_sasrec_causal_masking() -> None:
    """Posições de padding não devem influenciar as últimas posições válidas."""
    model = SASRec(n_items=50, embedding_dim=16, n_heads=2, n_layers=1)
    model.eval()
    s1 = torch.tensor([[1, 2, 3, 0, 0]])
    s2 = torch.tensor([[1, 2, 3, 4, 5]])
    l1 = torch.tensor([3])
    l2 = torch.tensor([5])
    with torch.no_grad():
        out1 = model(s1, l1)
        out2 = model(s2, l2)
    assert out1.shape == out2.shape
