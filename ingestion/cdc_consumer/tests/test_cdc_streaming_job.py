"""Testes unitários do CDC streaming job."""

from __future__ import annotations

import pytest

from ingestion.cdc_consumer.src.cdc_streaming_job import CDC_TOPICS, _parse_debezium_envelope


def test_cdc_topics_contains_required_tables() -> None:
    """Verifica que todos os tópicos obrigatórios estão mapeados."""
    required = {"products", "payments", "notifications"}
    assert required.issubset(set(CDC_TOPICS.keys()))


def test_cdc_topics_prefix() -> None:
    """Verifica que os tópicos seguem o prefixo correto."""
    for topic in CDC_TOPICS.values():
        assert topic.startswith("cdc.melisim."), f"Tópico inválido: {topic}"


def test_stream_table_raises_on_invalid_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que tabela inválida levanta ValueError."""
    from unittest.mock import MagicMock

    from ingestion.cdc_consumer.src import cdc_streaming_job

    mock_spark = MagicMock()
    with pytest.raises(ValueError, match="inválida"):
        cdc_streaming_job.stream_table(mock_spark, "invalid_table")
