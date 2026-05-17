"""Configuracao do servidor ML API."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    mlflow_tracking_uri: str = "http://mlflow:5000"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    trino_host: str = "trino"
    trino_port: int = 8080
    trino_user: str = "ml-api"
    api_title: str = "MeliSimLake ML API"
    api_version: str = "2.0.0"


settings = APISettings()
