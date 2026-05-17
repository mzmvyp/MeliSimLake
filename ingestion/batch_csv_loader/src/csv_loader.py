"""Batch CSV Loader — processa CSVs da landing zone e move para Bronze."""

from __future__ import annotations

import argparse
import datetime
import io
import sys
from typing import Any, Final

import boto3
import pandas as pd
import pandera as pa
import pandera.pandas as ppa
from loguru import logger
from pandera.typing import DataFrame as PaDataFrame
from pydantic_settings import BaseSettings, SettingsConfigDict

BRONZE_BUCKET: Final[str] = "bronze"
LANDING_BUCKET: Final[str] = "landing"


class CSVLoaderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"


settings = CSVLoaderSettings()


class LegacyCatalogSchema(ppa.DataFrameModel):
    """Schema de validação para catálogo legado."""

    product_id: pa.typing.Series[str]
    title: pa.typing.Series[str]
    category: pa.typing.Series[str]
    price: pa.typing.Series[float] = pa.Field(gt=0)
    available: pa.typing.Series[bool]

    class Config:
        coerce = True
        strict = "filter"


class LogisticsSchema(ppa.DataFrameModel):
    """Schema para dados de logística."""

    order_id: pa.typing.Series[str]
    carrier: pa.typing.Series[str]
    status: pa.typing.Series[str]
    estimated_delivery: pa.typing.Series[str]
    weight_kg: pa.typing.Series[float] = pa.Field(ge=0)

    class Config:
        coerce = True
        strict = "filter"


FILE_TYPE_SCHEMAS: dict[str, type[ppa.DataFrameModel]] = {
    "catalog": LegacyCatalogSchema,
    "logistics": LogisticsSchema,
}


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )


def _list_new_csvs(file_type: str) -> list[str]:
    """Lista arquivos CSV na landing zone.

    Args:
        file_type: Tipo de arquivo (ex: catalog, logistics).

    Returns:
        Lista de chaves S3.
    """
    s3 = _s3_client()
    prefix = f"csv/{file_type}/"
    response = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix=prefix)
    return [
        obj["Key"]
        for obj in response.get("Contents", [])
        if obj["Key"].endswith(".csv")
    ]


def _read_csv_from_s3(key: str) -> pd.DataFrame:
    s3 = _s3_client()
    response = s3.get_object(Bucket=LANDING_BUCKET, Key=key)
    return pd.read_csv(io.BytesIO(response["Body"].read()))


def _upload_parquet(df: pd.DataFrame, file_type: str, date: str, filename: str) -> None:
    key = f"csv/{file_type}/event_date={date}/{filename}.parquet"
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    _s3_client().put_object(
        Bucket=BRONZE_BUCKET, Key=key, Body=buffer.getvalue()
    )
    logger.info("Parquet salvo no Bronze", extra={"key": key, "rows": len(df)})


def process_file_type(file_type: str, date: str) -> int:
    """Processa todos os CSVs de um tipo na landing zone.

    Args:
        file_type: Tipo (catalog, logistics, etc.).
        date: Data de partição YYYY-MM-DD.

    Returns:
        Número de arquivos processados com sucesso.
    """
    schema_cls = FILE_TYPE_SCHEMAS.get(file_type)
    if schema_cls is None:
        logger.warning("Tipo sem schema de validação", extra={"file_type": file_type})

    keys = _list_new_csvs(file_type)
    logger.info("CSVs encontrados", extra={"file_type": file_type, "count": len(keys)})

    processed = 0
    for key in keys:
        filename = key.split("/")[-1].replace(".csv", "")
        try:
            df = _read_csv_from_s3(key)
            if schema_cls is not None:
                df = schema_cls.validate(df)  # type: ignore[assignment]
            _upload_parquet(df, file_type, date, filename)
            processed += 1
        except pa.errors.SchemaError as exc:
            logger.error("Falha de validação Pandera", extra={"key": key, "error": str(exc)})
        except Exception as exc:
            logger.error("Erro ao processar CSV", extra={"key": key, "error": str(exc)})

    return processed


def main(argv: list[str] | None = None) -> None:
    """Entry point do batch CSV loader.

    Args:
        argv: Argumentos CLI.
    """
    parser = argparse.ArgumentParser(description="MeliSimLake Batch CSV Loader")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument(
        "--file-types",
        nargs="+",
        default=list(FILE_TYPE_SCHEMAS.keys()),
    )
    args = parser.parse_args(argv)

    logger.info("Batch CSV Loader iniciado", extra={"date": args.date})
    total = 0
    for ft in args.file_types:
        total += process_file_type(ft, args.date)
    logger.info("Batch CSV Loader concluído", extra={"total_files": total})


if __name__ == "__main__":
    main(sys.argv[1:])
