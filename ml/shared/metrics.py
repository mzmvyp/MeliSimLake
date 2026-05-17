"""Métricas de avaliação de modelos ML."""

from __future__ import annotations

import numpy as np


def precision_at_k(
    recommended: list[list[int]],
    relevant: list[list[int]],
    k: int = 10,
) -> float:
    """Calcula Precision@K para um conjunto de usuários.

    Args:
        recommended: Lista de listas com itens recomendados por usuário.
        relevant: Lista de listas com itens relevantes por usuário.
        k: Top-K.

    Returns:
        Precision@K médio.
    """
    scores = []
    for rec, rel in zip(recommended, relevant):
        top_k = set(rec[:k])
        rel_set = set(rel)
        if not rel_set:
            continue
        scores.append(len(top_k & rel_set) / k)
    return float(np.mean(scores)) if scores else 0.0


def recall_at_k(
    recommended: list[list[int]],
    relevant: list[list[int]],
    k: int = 10,
) -> float:
    """Calcula Recall@K.

    Args:
        recommended: Recomendações por usuário.
        relevant: Itens relevantes por usuário.
        k: Top-K.

    Returns:
        Recall@K médio.
    """
    scores = []
    for rec, rel in zip(recommended, relevant):
        top_k = set(rec[:k])
        rel_set = set(rel)
        if not rel_set:
            continue
        scores.append(len(top_k & rel_set) / len(rel_set))
    return float(np.mean(scores)) if scores else 0.0


def ndcg_at_k(
    recommended: list[list[int]],
    relevant: list[list[int]],
    k: int = 10,
) -> float:
    """Calcula NDCG@K.

    Args:
        recommended: Recomendações por usuário.
        relevant: Itens relevantes por usuário.
        k: Top-K.

    Returns:
        NDCG@K médio.
    """

    def dcg(recs: list[int], rel_set: set[int], k: int) -> float:
        return sum(
            1.0 / np.log2(i + 2)
            for i, item in enumerate(recs[:k])
            if item in rel_set
        )

    scores = []
    for rec, rel in zip(recommended, relevant):
        rel_set = set(rel)
        if not rel_set:
            continue
        ideal = dcg(list(rel_set), rel_set, k)
        actual = dcg(rec, rel_set, k)
        scores.append(actual / ideal if ideal > 0 else 0.0)

    return float(np.mean(scores)) if scores else 0.0


def mrr_at_k(
    recommended: list[list[int]],
    relevant: list[list[int]],
    k: int = 20,
) -> float:
    """Calcula MRR@K (Mean Reciprocal Rank).

    Args:
        recommended: Recomendações por usuário.
        relevant: Itens relevantes por usuário.
        k: Top-K.

    Returns:
        MRR@K médio.
    """
    scores = []
    for rec, rel in zip(recommended, relevant):
        rel_set = set(rel)
        for i, item in enumerate(rec[:k]):
            if item in rel_set:
                scores.append(1.0 / (i + 1))
                break
        else:
            scores.append(0.0)
    return float(np.mean(scores)) if scores else 0.0
