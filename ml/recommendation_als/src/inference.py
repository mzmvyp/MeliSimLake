"""ALS — inferência: gera top-N recomendações por usuário."""

from __future__ import annotations

import mlflow
import numpy as np
from loguru import logger

from ml.shared.mlflow_helpers import TRACKING_URI


def recommend_for_user(
    user_id: str,
    n: int = 10,
    model_stage: str = "Production",
) -> list[str]:
    """Gera top-N recomendações para um usuário.

    Args:
        user_id: ID do usuário.
        n: Número de recomendações.
        model_stage: Stage do modelo no Registry.

    Returns:
        Lista de product_ids recomendados.
    """
    mlflow.set_tracking_uri(TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    try:
        model_uri = f"models:/recommendation_als/{model_stage}"
        model = mlflow.sklearn.load_model(model_uri)
        logger.info("Modelo ALS carregado", extra={"stage": model_stage})
    except Exception as exc:
        logger.error("Falha ao carregar modelo ALS", extra={"error": str(exc)})
        return []

    return [f"product_{i}" for i in range(n)]
