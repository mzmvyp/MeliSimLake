"""Endpoint de recomendacao (ALS implicit)."""
from __future__ import annotations

import time

import numpy as np
from fastapi import APIRouter, HTTPException

from serving.ml_api.src.schemas.responses import (
    RecommendationItem,
    RecommendationResponse,
)
from serving.ml_api.src.services import model_registry as reg
from serving.ml_api.src.services import trino_features as feats

router = APIRouter(tags=["recommendations"])


def _als_topk(bundle: dict, user_id: str, k: int) -> tuple[list[tuple[str, float]], bool]:
    user_ids = bundle.get("user_ids", [])
    item_ids = bundle.get("item_ids", [])
    user_factors = bundle.get("user_factors")
    item_factors = bundle.get("item_factors")
    if user_factors is None or item_factors is None:
        return [], True
    user_id_str = str(user_id)
    if user_id_str not in [str(u) for u in user_ids]:
        # Cold-start: usa media dos item_factors com user-mean para top-K populares
        scores = item_factors.mean(axis=1) if hasattr(item_factors, "mean") else None
        if scores is None:
            return [], True
        top_idx = np.argsort(-scores)[:k]
        return [(str(item_ids[int(i)]), float(scores[int(i)])) for i in top_idx], True
    idx = [str(u) for u in user_ids].index(user_id_str)
    uf = np.asarray(user_factors[idx])
    if_ = np.asarray(item_factors)
    scores = if_ @ uf
    top_idx = np.argsort(-scores)[:k]
    return [(str(item_ids[int(i)]), float(scores[int(i)])) for i in top_idx], False


@router.post("/recommend/{user_id}", response_model=RecommendationResponse)
def recommend(user_id: str, k: int = 5) -> RecommendationResponse:
    bundle = reg.get(reg.ALS_MODEL)
    if bundle is None:
        raise HTTPException(
            status_code=503, detail="modelo recommender indisponivel (treino pendente)"
        )
    if k < 1 or k > 20:
        raise HTTPException(status_code=400, detail="k deve estar entre 1 e 20")
    t0 = time.time()
    pairs, cold = _als_topk(bundle, user_id, k)
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    if not pairs:
        raise HTTPException(status_code=503, detail="bundle invalido")
    products_meta = feats.product_lookup([p for p, _ in pairs])
    meta_index = (
        products_meta.set_index(products_meta["product_id"].astype(str)).to_dict("index")
        if not products_meta.empty
        else {}
    )
    items: list[RecommendationItem] = []
    for pid, score in pairs:
        meta = meta_index.get(str(pid), {})
        items.append(
            RecommendationItem(
                product_id=str(pid),
                score=round(score, 6),
                title=str(meta.get("title")) if meta.get("title") is not None else None,
                category=str(meta.get("category")) if meta.get("category") is not None else None,
                price=float(meta.get("price")) if meta.get("price") is not None else None,
            )
        )
    return RecommendationResponse(
        user_id=str(user_id),
        recommendations=items,
        cold_start=cold,
        model=reg.ALS_MODEL,
        model_version=reg._versions.get(reg.ALS_MODEL, "unknown"),
        inference_ms=elapsed_ms,
    )
