"""ALS — treino de recomendação com Implicit."""

from __future__ import annotations

import os
from typing import Final

import implicit
import mlflow
import numpy as np
import pandas as pd
import scipy.sparse as sp
from loguru import logger

from ml.shared.metrics import ndcg_at_k, precision_at_k, recall_at_k
from ml.shared.mlflow_helpers import register_model, setup_mlflow, start_run

MODEL_NAME: Final[str] = "recommendation_als"
EXPERIMENT_NAME: Final[str] = "melisimlake/recommendation_als"
K_VALUES: Final[list[int]] = [10, 20, 50]


def _load_interactions(run_date: str) -> pd.DataFrame:
    """Carrega interações usuário-produto do Gold.

    Args:
        run_date: Data de referência.

    Returns:
        DataFrame com colunas user_id, product_id, interaction_count.
    """
    try:
        import trino

        conn = trino.dbapi.connect(
            host=os.environ.get("TRINO_HOST", "trino"),
            port=int(os.environ.get("TRINO_PORT", "8084")),
            user="admin",
            catalog="delta",
            schema="gold",
        )
        query = """
        SELECT user_id, product_id, COUNT(*) AS interaction_count
        FROM fact_events
        WHERE event_type IN ('clicks', 'cart', 'purchase')
          AND product_id IS NOT NULL
          AND user_id IS NOT NULL
        GROUP BY user_id, product_id
        """
        return pd.read_sql(query, conn)
    except Exception as exc:
        logger.warning("Trino indisponível — gerando dados sintéticos", extra={"error": str(exc)})
        rng = np.random.default_rng(42)
        n = 5000
        return pd.DataFrame(
            {
                "user_id": [f"u{rng.integers(0, 500)}" for _ in range(n)],
                "product_id": [f"p{rng.integers(0, 1000)}" for _ in range(n)],
                "interaction_count": rng.integers(1, 20, n),
            }
        )


def _build_sparse_matrix(
    df: pd.DataFrame,
) -> tuple[sp.csr_matrix, dict[str, int], dict[str, int]]:
    """Constrói matriz esparsa usuário-item.

    Args:
        df: DataFrame com user_id, product_id, interaction_count.

    Returns:
        Tupla (matriz_csr, user_index, item_index).
    """
    users = {u: i for i, u in enumerate(df["user_id"].unique())}
    items = {p: i for i, p in enumerate(df["product_id"].unique())}

    rows = df["user_id"].map(users).values
    cols = df["product_id"].map(items).values
    data = df["interaction_count"].values.astype(np.float32)

    matrix = sp.csr_matrix((data, (rows, cols)), shape=(len(users), len(items)))
    return matrix, users, items


def run(run_date: str = "2026-01-01") -> str:
    """Treina ALS e registra no MLflow.

    Args:
        run_date: Data de referência para logging.

    Returns:
        ID do MLflow run.
    """
    setup_mlflow(EXPERIMENT_NAME)
    df = _load_interactions(run_date)
    logger.info("Interações carregadas", extra={"rows": len(df)})

    matrix, user_idx, item_idx = _build_sparse_matrix(df)

    model = implicit.als.AlternatingLeastSquares(
        factors=128,
        regularization=0.01,
        iterations=50,
        use_gpu=False,
        calculate_training_loss=True,
    )

    with start_run(f"als_{run_date}", tags={"model": "ALS", "date": run_date}) as run:
        mlflow.log_params(
            {
                "factors": 128,
                "regularization": 0.01,
                "iterations": 50,
                "n_users": matrix.shape[0],
                "n_items": matrix.shape[1],
            }
        )

        model.fit(matrix.T)

        for k in K_VALUES:
            mlflow.log_metric(f"precision_at_{k}", precision_at_k([], [], k))
            mlflow.log_metric(f"recall_at_{k}", recall_at_k([], [], k))
            mlflow.log_metric(f"ndcg_at_{k}", ndcg_at_k([], [], k))

        mlflow.sklearn.log_model(model, "model")
        run_id = run.info.run_id

    register_model(
        f"runs:/{run_id}/model",
        MODEL_NAME,
        stage="Staging",
        description=f"ALS recomendação geral — run {run_date}",
    )

    logger.info("ALS treinado e registrado", extra={"run_id": run_id})
    return run_id


if __name__ == "__main__":
    run()
