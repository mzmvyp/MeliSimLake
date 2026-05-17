from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class CDCConsumerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    kafka_bootstrap_servers: str = "melisimlake-kafka:9092"
    schema_registry_url: str = "http://schema-registry:8081"
    bronze_bucket: str = "bronze"
    checkpoint_bucket: str = "checkpoints"
    streaming_trigger_seconds: int = 30


settings = CDCConsumerSettings()
