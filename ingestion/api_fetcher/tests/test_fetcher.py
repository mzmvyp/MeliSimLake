"""Testes do API fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ingestion.api_fetcher.src.fetcher_main import fetch_exchange_rates, fetch_viacep


def test_fetch_exchange_rates_returns_dict(respx_mock: None) -> None:
    """fetch_exchange_rates retorna dict com campo 'rates'."""
    import respx
    import httpx

    with respx.mock:
        respx.get("https://open.er-api.com/v6/latest/USD").mock(
            return_value=httpx.Response(200, json={"result": "success", "rates": {"BRL": 5.0}})
        )
        result = fetch_exchange_rates("USD")
    assert "rates" in result


def test_fetch_viacep_strips_dash() -> None:
    """fetch_viacep remove o traço do CEP antes de chamar a API."""
    with patch("ingestion.api_fetcher.src.fetcher_main.httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {"cep": "01310-100", "logradouro": "Av. Paulista"}
        mock_response.raise_for_status.return_value = None
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        result = fetch_viacep("01310-100")
        assert result["cep"] == "01310-100"
