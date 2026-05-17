"""Feature views de produto."""

from __future__ import annotations

from datetime import timedelta

from feast import Feature, FeatureView, ValueType

from feature_store.feature_repo.data_sources import product_features_source
from feature_store.feature_repo.entities import product

product_features = FeatureView(
    name="product_features",
    entities=[product],
    ttl=timedelta(days=1),
    features=[
        Feature(name="product_name", dtype=ValueType.STRING),
        Feature(name="category", dtype=ValueType.STRING),
        Feature(name="price", dtype=ValueType.FLOAT),
        Feature(name="stock_quantity", dtype=ValueType.INT32),
        Feature(name="avg_rating", dtype=ValueType.FLOAT),
        Feature(name="review_count", dtype=ValueType.INT32),
        Feature(name="days_since_launch", dtype=ValueType.INT32),
        Feature(name="is_active", dtype=ValueType.BOOL),
    ],
    source=product_features_source,
    tags={"domain": "product", "owner": "data-science"},
    description="Atributos de produto para enriquecimento de modelos",
)
