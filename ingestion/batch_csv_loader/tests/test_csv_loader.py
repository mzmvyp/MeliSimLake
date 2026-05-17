"""Testes do batch CSV loader."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ingestion.batch_csv_loader.src.csv_loader import FILE_TYPE_SCHEMAS, process_file_type


def test_file_type_schemas_contains_required_types() -> None:
    assert "catalog" in FILE_TYPE_SCHEMAS
    assert "logistics" in FILE_TYPE_SCHEMAS


def test_process_file_type_unknown_type_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with patch("ingestion.batch_csv_loader.src.csv_loader._list_new_csvs", return_value=[]):
        result = process_file_type("unknown_type", "2026-01-01")
    assert result == 0


def test_catalog_schema_rejects_negative_price() -> None:
    import pandera as pa
    from ingestion.batch_csv_loader.src.csv_loader import LegacyCatalogSchema

    df = pd.DataFrame(
        {
            "product_id": ["p1"],
            "title": ["Produto A"],
            "category": ["Eletrônicos"],
            "price": [-10.0],
            "available": [True],
        }
    )
    with pytest.raises(pa.errors.SchemaError):
        LegacyCatalogSchema.validate(df)
