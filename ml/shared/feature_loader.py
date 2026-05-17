"""Feature Loader — lê features do Feast para treino e inferência."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
from loguru import logger


def load_user_features(user_ids: list[str]) -> pd.DataFrame:
    """Carrega features de usuário do Feast online store.

    Args:
        user_ids: Lista de IDs de usuário.

    Returns:
        DataFrame com features de usuário.
    """
    try:
        from feast import FeatureStore

        store = FeatureStore(repo_path="feature_store/feature_repo")
        entity_df = pd.DataFrame({"user_id": user_ids})
        features = store.get_online_features(
            features=[
                "user_features:total_orders",
                "user_features:days_since_last_order",
                "user_features:avg_order_value",
                "user_features:rfm_segment",
                "user_features:r_score",
                "user_features:f_score",
                "user_features:m_score",
            ],
            entity_rows=[{"user_id": uid} for uid in user_ids],
        ).to_df()
        return features
    except ImportError:
        logger.warning("Feast não disponível — retornando DataFrame vazio")
        return pd.DataFrame({"user_id": user_ids})
    except Exception as exc:
        logger.error("Erro ao carregar features do Feast", extra={"error": str(exc)})
        return pd.DataFrame({"user_id": user_ids})


def load_session_sequences(
    source: str = "trino",
    min_sequence_length: int = 2,
    limit: int = 100_000,
) -> pd.DataFrame:
    """Carrega sequências de produtos por sessão para GRU4Rec.

    Args:
        source: Origem dos dados (trino | parquet).
        min_sequence_length: Tamanho mínimo da sequência.
        limit: Máximo de sessões.

    Returns:
        DataFrame com colunas session_id, product_sequence, user_id.
    """
    if source == "trino":
        try:
            import trino

            conn = trino.dbapi.connect(
                host=os.environ.get("TRINO_HOST", "trino"),
                port=int(os.environ.get("TRINO_PORT", "8084")),
                user="admin",
                catalog="delta",
                schema="gold_ml",
            )
            query = f"""
            SELECT session_id, user_id, product_sequence, sequence_length
            FROM ml_session_features
            WHERE sequence_length >= {min_sequence_length}
            LIMIT {limit}
            """
            return pd.read_sql(query, conn)
        except Exception as exc:
            logger.warning("Trino indisponível", extra={"error": str(exc)})

    return pd.DataFrame(columns=["session_id", "user_id", "product_sequence", "sequence_length"])
