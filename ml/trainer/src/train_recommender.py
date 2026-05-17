"""Treina recommender ALS implicit sobre delta.gold_ml.user_item_matrix."""
from __future__ import annotations

import json
import pickle
import tempfile
from pathlib import Path
from typing import Final

import implicit
import mlflow
import numpy as np
import pandas as pd
from loguru import logger
from scipy.sparse import csr_matrix

from .mlflow_utils import ensure_experiment, promote_to_production, setup
from .trino_client import query

EXPERIMENT: Final = "melisimlake/recommender"
MODEL_NAME: Final = "melisimlake_als_recommender"
FACTORS: Final = 24
ITERATIONS: Final = 30
REGULARIZATION: Final = 0.05
ALPHA: Final = 30.0


def run() -> dict:
    df = query(
        "SELECT buyer_id, product_id, units, orders, gmv "
        "FROM delta.gold_ml.user_item_matrix"
    )
    if df.empty:
        logger.warning("[recommender] user_item_matrix vazio, skip")
        return {"status": "skipped", "reason": "empty_dataset"}

    df = df.dropna(subset=["buyer_id", "product_id"]).copy()
    if df["buyer_id"].nunique() < 2 or df["product_id"].nunique() < 2:
        logger.warning("[recommender] dataset insuficiente (<2 users ou <2 products), skip")
        return {"status": "skipped", "reason": "too_few_entities"}

    df["weight"] = df["units"].astype(float) + df["orders"].astype(float)
    user_ids = sorted(df["buyer_id"].unique().tolist())
    item_ids = sorted(df["product_id"].unique().tolist())
    user_to_idx = {u: i for i, u in enumerate(user_ids)}
    item_to_idx = {it: i for i, it in enumerate(item_ids)}
    rows = df["buyer_id"].map(user_to_idx).to_numpy()
    cols = df["product_id"].map(item_to_idx).to_numpy()
    data = df["weight"].to_numpy(dtype=np.float32)
    matrix = csr_matrix((data, (rows, cols)), shape=(len(user_ids), len(item_ids)))

    model = implicit.als.AlternatingLeastSquares(
        factors=FACTORS,
        iterations=ITERATIONS,
        regularization=REGULARIZATION,
        alpha=ALPHA,
        use_gpu=False,
        random_state=42,
    )
    model.fit(matrix)

    sample_recs: dict[str, list[dict]] = {}
    for u in user_ids[: min(3, len(user_ids))]:
        idx = user_to_idx[u]
        ids, scores = model.recommend(idx, matrix[idx], N=min(5, len(item_ids)), filter_already_liked_items=False)
        sample_recs[u] = [
            {"product_id": item_ids[int(i)], "score": float(s)} for i, s in zip(ids, scores)
        ]

    setup()
    ensure_experiment(EXPERIMENT)
    mlflow.set_experiment(EXPERIMENT)

    with tempfile.TemporaryDirectory() as tmp:
        artifact_root = Path(tmp)
        bundle_path = artifact_root / "model.pkl"
        with bundle_path.open("wb") as fh:
            pickle.dump(
                {
                    "user_factors": model.user_factors,
                    "item_factors": model.item_factors,
                    "user_ids": user_ids,
                    "item_ids": item_ids,
                    "params": {
                        "factors": FACTORS,
                        "iterations": ITERATIONS,
                        "regularization": REGULARIZATION,
                        "alpha": ALPHA,
                    },
                },
                fh,
            )
        with mlflow.start_run(run_name="als_recommender"):
            mlflow.log_params(
                {
                    "factors": FACTORS,
                    "iterations": ITERATIONS,
                    "regularization": REGULARIZATION,
                    "alpha": ALPHA,
                    "n_users": len(user_ids),
                    "n_items": len(item_ids),
                    "n_interactions": int(matrix.nnz),
                }
            )
            density = float(matrix.nnz) / float(max(1, matrix.shape[0] * matrix.shape[1]))
            mlflow.log_metric("matrix_density", density)
            mlflow.log_metric("avg_interactions_per_user", float(matrix.nnz) / float(len(user_ids)))
            mlflow.log_artifact(str(bundle_path), artifact_path="model")
            mlflow.log_dict(sample_recs, "sample_recommendations.json")

            client = setup()
            run_id = mlflow.active_run().info.run_id
            model_uri = f"runs:/{run_id}/model"
            mv = mlflow.register_model(model_uri=model_uri, name=MODEL_NAME)
            promote_to_production(client, MODEL_NAME, int(mv.version))
            logger.info(f"[recommender] {MODEL_NAME} v{mv.version} promoted to Production")

    logger.info(
        f"[recommender] users={len(user_ids)} items={len(item_ids)} interactions={matrix.nnz}"
    )
    return {
        "status": "ok",
        "metrics": {
            "n_users": len(user_ids),
            "n_items": len(item_ids),
            "n_interactions": int(matrix.nnz),
        },
        "sample": sample_recs,
    }


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run(), indent=2, default=str))
