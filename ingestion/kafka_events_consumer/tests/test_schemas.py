"""Testes dos schemas de eventos."""

from __future__ import annotations

from ingestion.kafka_events_consumer.src.schemas import TOPIC_SCHEMAS


def test_all_topics_have_schemas() -> None:
    required = {"events.clicks", "events.cart", "events.search", "events.purchase"}
    assert required.issubset(set(TOPIC_SCHEMAS.keys()))


def test_click_schema_has_required_fields() -> None:
    schema = TOPIC_SCHEMAS["events.clicks"]
    field_names = {f.name for f in schema.fields}
    assert "event_id" in field_names
    assert "user_id" in field_names
    assert "product_id" in field_names
    assert "ts" in field_names


def test_purchase_schema_mandatory_fields_not_nullable() -> None:
    schema = TOPIC_SCHEMAS["events.purchase"]
    mandatory = {f.name: f.nullable for f in schema.fields}
    assert mandatory["event_id"] is False
    assert mandatory["user_id"] is False
    assert mandatory["order_id"] is False
