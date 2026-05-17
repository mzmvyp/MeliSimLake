"""Utils MLflow: setup tracking, registrar e promover model versions."""
from __future__ import annotations

import os
from typing import Optional

import mlflow
from mlflow.tracking import MlflowClient


def setup() -> MlflowClient:
    uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(uri)
    s3 = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
    os.environ.setdefault("MLFLOW_S3_ENDPOINT_URL", s3)
    os.environ.setdefault("AWS_ACCESS_KEY_ID", os.getenv("MINIO_ACCESS_KEY", "minioadmin"))
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", os.getenv("MINIO_SECRET_KEY", "minioadmin"))
    return MlflowClient(tracking_uri=uri)


def ensure_experiment(name: str) -> str:
    exp = mlflow.get_experiment_by_name(name)
    if exp is None:
        return mlflow.create_experiment(name)
    return exp.experiment_id


def promote_to_production(client: MlflowClient, name: str, version: int) -> None:
    """Move a versao para Production e arquiva versoes antigas."""
    try:
        for mv in client.get_latest_versions(name, stages=["Production"]):
            if int(mv.version) != int(version):
                client.transition_model_version_stage(
                    name=name, version=mv.version, stage="Archived"
                )
        client.transition_model_version_stage(
            name=name, version=str(version), stage="Production"
        )
    except Exception as exc:  # pragma: no cover
        print(f"[mlflow] promote skipped ({name} v{version}): {exc}")
