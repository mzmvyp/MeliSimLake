"""API Fetcher — coleta dados de APIs externas e persiste em Bronze."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Final

import boto3
import httpx
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential

MINIO_ENDPOINT: Final[str] = "http://minio:9000"
BRONZE_BUCKET: Final[str] = "bronze"


class FetcherSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    minio_endpoint: str = MINIO_ENDPOINT
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"


settings = FetcherSettings()


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )


def _upload_json(data: dict[str, Any] | list[Any], source: str, date: str) -> None:
    """Persiste dados JSON como objeto no Bronze.

    Args:
        data: Dados a serializar.
        source: Nome da fonte (ex: 'exchange_rates').
        date: Data no formato YYYY-MM-DD.
    """
    key = f"api/{source}/event_date={date}/{source}_{date}.json"
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    _s3_client().put_object(Bucket=BRONZE_BUCKET, Key=key, Body=body)
    logger.info("Dados persistidos no Bronze", extra={"key": key, "bytes": len(body)})


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def fetch_exchange_rates(base: str = "USD") -> dict[str, Any]:
    """Busca cotações de câmbio da API open.er-api.com.

    Args:
        base: Moeda base (padrão: USD).

    Returns:
        Dict com taxas de câmbio.
    """
    url = f"https://open.er-api.com/v6/latest/{base}"
    logger.info("Buscando cotações", extra={"url": url})
    with httpx.Client(timeout=30) as client:
        response = client.get(url)
        response.raise_for_status()
    return response.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def fetch_viacep(cep: str) -> dict[str, Any]:
    """Busca dados de endereço via ViaCEP.

    Args:
        cep: CEP no formato 00000-000 ou 00000000.

    Returns:
        Dict com dados do endereço.
    """
    cep_clean = cep.replace("-", "").replace(".", "")
    url = f"https://viacep.com.br/ws/{cep_clean}/json/"
    logger.info("Buscando CEP", extra={"cep": cep_clean})
    with httpx.Client(timeout=15) as client:
        response = client.get(url)
        response.raise_for_status()
    return response.json()


def run(date: str | None = None) -> None:
    """Executa todos os fetchers e persiste resultados em Bronze.

    Args:
        date: Data alvo YYYY-MM-DD (padrão: hoje).
    """
    today = date or datetime.date.today().isoformat()
    logger.info("API Fetcher iniciado", extra={"date": today})

    exchange = fetch_exchange_rates()
    _upload_json(exchange, "exchange_rates", today)

    sample_ceps = ["01310-100", "20040-020", "30112-000"]
    addresses = [fetch_viacep(cep) for cep in sample_ceps]
    _upload_json(addresses, "viacep", today)

    logger.info("API Fetcher concluído", extra={"date": today})


if __name__ == "__main__":
    run()
