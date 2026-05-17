"""Testes GRU4Rec."""

from __future__ import annotations

import torch
import pytest

from ml.recommendation_gru4rec.src.model import GRU4Rec
from ml.recommendation_gru4rec.src.data import SessionDataset, build_item_index, collate_fn


def test_model_output_shape() -> None:
    model = GRU4Rec(n_items=100, embedding_dim=32, hidden_dim=64)
    sessions = torch.randint(1, 101, (4, 10))
    lengths = torch.tensor([10, 8, 5, 3])
    logits = model(sessions, lengths)
    assert logits.shape == (4, 101)


def test_model_no_nan() -> None:
    model = GRU4Rec(n_items=50)
    sessions = torch.randint(0, 51, (2, 5))
    lengths = torch.tensor([5, 3])
    logits = model(sessions, lengths)
    assert not torch.isnan(logits).any()


def test_session_dataset_len() -> None:
    seqs = [[1, 2, 3], [4, 5], [1, 2, 3, 4, 5]]
    ds = SessionDataset(seqs)
    assert len(ds) == 3


def test_session_dataset_item_shape() -> None:
    seqs = [[1, 2, 3, 4, 5]]
    ds = SessionDataset(seqs, max_len=10)
    inp, target, length = ds[0]
    assert inp.shape == (10,)
    assert isinstance(target, int)
    assert length == 4


def test_build_item_index_starts_at_one() -> None:
    seqs = [[10, 20, 30], [20, 40]]
    idx = build_item_index(seqs)
    assert min(idx.values()) == 1
    assert len(idx) == 4


def test_mrr_at_k_perfect() -> None:
    from ml.shared.metrics import mrr_at_k
    recommended = [[5, 2, 3]]
    relevant = [[5]]
    assert mrr_at_k(recommended, relevant, k=5) == pytest.approx(1.0)
