"""Helpers MLflow — logging consistente de modelos e métricas."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

import mlflow
from loguru import logger

TRACKING_URI = os.environ.get("MELISIMLAKE_MLFLOW_TRACKING_URI", "http://mlflow:5000")


def setup_mlflow(experiment_name: str) -> str:
    """Configura MLflow e retorna ID do experimento.

    Args:
        experiment_name: Nome do experimento MLflow.

    Returns:
        ID do experimento criado ou encontrado.
    """
    mlflow.set_tracking_uri(TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        exp_id = mlflow.create_experiment(experiment_name)
    else:
        exp_id = experiment.experiment_id
    mlflow.set_experiment(experiment_name)
    return exp_id


@contextmanager
def start_run(
    run_name: str,
    tags: dict[str, str] | None = None,
) -> Generator[mlflow.ActiveRun, None, None]:
    """Context manager para MLflow run com logging automático.

    Args:
        run_name: Nome do run.
        tags: Tags adicionais.

    Yields:
        MLflow ActiveRun.
    """
    default_tags = {"source": "melisimlake", "framework": "mlflow"}
    all_tags = {**default_tags, **(tags or {})}

    with mlflow.start_run(run_name=run_name, tags=all_tags) as run:
        logger.info("MLflow run iniciado", extra={"run_id": run.info.run_id, "name": run_name})
        yield run
        logger.info("MLflow run concluído", extra={"run_id": run.info.run_id})


def register_model(
    model_uri: str,
    name: str,
    stage: str = "Staging",
    description: str = "",
) -> None:
    """Registra modelo no MLflow Registry e promove para stage.

    Args:
        model_uri: URI do artefato (ex: runs:/run_id/model).
        name: Nome do modelo no Registry.
        stage: Stage alvo (Staging | Production | Archived).
        description: Descrição do modelo.
    """
    client = mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)

    mv = mlflow.register_model(model_uri, name)
    logger.info("Modelo registrado", extra={"name": name, "version": mv.version})

    client.update_model_version(name=name, version=mv.version, description=description)
    client.transition_model_version_stage(
        name=name, version=mv.version, stage=stage, archive_existing_versions=True
    )
    logger.info("Modelo promovido", extra={"name": name, "stage": stage})
