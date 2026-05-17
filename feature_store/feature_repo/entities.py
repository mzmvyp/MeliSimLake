"""Entidades Feast do MeliSimLake."""

from __future__ import annotations

from feast import Entity, ValueType

user = Entity(
    name="user_id",
    value_type=ValueType.STRING,
    description="Identificador único do usuário",
    tags={"owner": "data-science", "domain": "user"},
)

product = Entity(
    name="product_id",
    value_type=ValueType.STRING,
    description="Identificador único do produto",
    tags={"owner": "data-science", "domain": "product"},
)

session = Entity(
    name="session_id",
    value_type=ValueType.STRING,
    description="Identificador único da sessão de navegação",
    tags={"owner": "data-science", "domain": "session"},
)
