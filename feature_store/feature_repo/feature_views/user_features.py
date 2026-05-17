"""Feature views de usuário — churn features + RFM."""

from __future__ import annotations

from datetime import timedelta

from feast import Feature, FeatureView, ValueType

from feature_store.feature_repo.data_sources import rfm_source, user_features_source
from feature_store.feature_repo.entities import user

user_churn_features = FeatureView(
    name="user_churn_features",
    entities=[user],
    ttl=timedelta(days=7),
    features=[
        Feature(name="recency_days", dtype=ValueType.INT32),
        Feature(name="frequency_30d", dtype=ValueType.INT32),
        Feature(name="frequency_90d", dtype=ValueType.INT32),
        Feature(name="monetary_30d", dtype=ValueType.FLOAT),
        Feature(name="monetary_90d", dtype=ValueType.FLOAT),
        Feature(name="avg_order_value", dtype=ValueType.FLOAT),
        Feature(name="days_since_account_creation", dtype=ValueType.INT32),
        Feature(name="support_tickets_last_90d", dtype=ValueType.INT32),
        Feature(name="return_rate", dtype=ValueType.FLOAT),
        Feature(name="favorite_category", dtype=ValueType.STRING),
        Feature(name="recency_ratio", dtype=ValueType.FLOAT),
        Feature(name="churn_label", dtype=ValueType.INT32),
    ],
    source=user_features_source,
    tags={"model": "churn_xgboost", "owner": "data-science"},
    description="Features de comportamento para predição de churn",
)

user_rfm_features = FeatureView(
    name="user_rfm_features",
    entities=[user],
    ttl=timedelta(days=1),
    features=[
        Feature(name="recency", dtype=ValueType.FLOAT),
        Feature(name="frequency", dtype=ValueType.FLOAT),
        Feature(name="monetary", dtype=ValueType.FLOAT),
        Feature(name="r_score", dtype=ValueType.INT32),
        Feature(name="f_score", dtype=ValueType.INT32),
        Feature(name="m_score", dtype=ValueType.INT32),
        Feature(name="rfm_segment", dtype=ValueType.STRING),
        Feature(name="ltv", dtype=ValueType.FLOAT),
    ],
    source=rfm_source,
    tags={"model": "segmentation", "owner": "data-science"},
    description="Scores RFM e segmento de cliente",
)
