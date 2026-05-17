"""Testes unitários de delta_utils."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from transformation.spark_jobs.src.lib.delta_utils import compute_row_hash


def test_compute_row_hash_adds_column() -> None:
    """compute_row_hash deve adicionar coluna row_hash."""
    mock_df = MagicMock()
    mock_df.columns = ["user_id", "email", "name"]
    mock_df.withColumn.return_value = mock_df

    result = compute_row_hash(mock_df, ["email", "name"])
    mock_df.withColumn.assert_called_once()
    call_args = mock_df.withColumn.call_args[0]
    assert call_args[0] == "row_hash"


def test_merge_scd2_raises_on_missing_key() -> None:
    """merge_scd2 deve levantar ValueError se business_key ausente."""
    from transformation.spark_jobs.src.lib.delta_utils import merge_scd2

    mock_spark = MagicMock()
    mock_df = MagicMock()
    mock_df.columns = ["other_col"]

    with pytest.raises(ValueError, match="ausente"):
        merge_scd2(mock_spark, "s3a://silver/test/", mock_df, "user_id")


def test_upsert_append_raises_on_missing_key() -> None:
    """upsert_append deve levantar ValueError se business_key ausente."""
    from transformation.spark_jobs.src.lib.delta_utils import upsert_append

    mock_spark = MagicMock()
    mock_df = MagicMock()
    mock_df.columns = ["other_col"]

    with pytest.raises(ValueError, match="ausente"):
        upsert_append(mock_spark, "s3a://silver/test/", mock_df, "order_id")


def test_schemas_silver_users_has_scd2_fields() -> None:
    """Schema de users Silver deve ter campos SCD2."""
    from transformation.spark_jobs.src.lib.schemas import SILVER_USERS_SCHEMA

    field_names = {f.name for f in SILVER_USERS_SCHEMA.fields}
    assert "valid_from" in field_names
    assert "valid_to" in field_names
    assert "is_current" in field_names
    assert "row_hash" in field_names


def test_schemas_silver_orders_has_business_key() -> None:
    """Schema de orders deve ter order_id como campo não-nulo."""
    from transformation.spark_jobs.src.lib.schemas import SILVER_ORDERS_SCHEMA

    field_map = {f.name: f for f in SILVER_ORDERS_SCHEMA.fields}
    assert "order_id" in field_map
    assert field_map["order_id"].nullable is False
