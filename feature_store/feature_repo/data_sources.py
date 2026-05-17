"""Fontes de dados Feast — apontam para tabelas Gold no Trino/Delta."""

from __future__ import annotations

from datetime import timedelta

from feast.infra.offline_stores.contrib.trino_offline_store.trino_source import TrinoSource

user_features_source = TrinoSource(
    name="user_features_source",
    table="delta.gold.churn_features",
    event_timestamp_column="label_date",
    created_timestamp_column="created_at",
    description="Features de usuário para modelos de churn e recomendação",
    tags={"layer": "gold", "domain": "user"},
)

product_features_source = TrinoSource(
    name="product_features_source",
    table="delta.gold.dim_products",
    event_timestamp_column="updated_at",
    created_timestamp_column="created_at",
    description="Atributos de produtos da dimensão Gold",
    tags={"layer": "gold", "domain": "product"},
)

session_features_source = TrinoSource(
    name="session_features_source",
    table="delta.gold.ml_session_features",
    event_timestamp_column="session_end",
    created_timestamp_column="session_end",
    description="Features de sessão para modelos sequenciais (GRU4Rec, SASRec)",
    tags={"layer": "gold", "domain": "session"},
)

rfm_source = TrinoSource(
    name="rfm_source",
    table="delta.gold.customer_rfm",
    event_timestamp_column="snapshot_date",
    created_timestamp_column="snapshot_date",
    description="Scores RFM e segmentos de clientes",
    tags={"layer": "gold", "domain": "user"},
)
