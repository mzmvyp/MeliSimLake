"""Feature views de sessão — para GRU4Rec e SASRec."""

from __future__ import annotations

from datetime import timedelta

from feast import Feature, FeatureView, ValueType

from feature_store.feature_repo.data_sources import session_features_source
from feature_store.feature_repo.entities import session, user

session_features = FeatureView(
    name="session_features",
    entities=[user, session],
    ttl=timedelta(hours=2),
    features=[
        Feature(name="product_sequence", dtype=ValueType.STRING),
        Feature(name="sequence_length", dtype=ValueType.INT32),
        Feature(name="session_duration_seconds", dtype=ValueType.INT32),
        Feature(name="device_type", dtype=ValueType.STRING),
        Feature(name="entry_source", dtype=ValueType.STRING),
        Feature(name="converted", dtype=ValueType.BOOL),
        Feature(name="total_value", dtype=ValueType.FLOAT),
    ],
    source=session_features_source,
    tags={"model": "gru4rec", "owner": "data-science"},
    description="Features de sessão para recomendação sequencial",
)
