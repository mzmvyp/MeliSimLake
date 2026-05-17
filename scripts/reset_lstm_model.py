"""Apaga registered model 'melisimlake_demand_forecast_lstm' do MLflow registry."""
from __future__ import annotations

import os

from mlflow.tracking import MlflowClient

NAME = os.environ.get("MODEL_NAME", "melisimlake_demand_forecast_lstm")
URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")


def main() -> int:
    client = MlflowClient(tracking_uri=URI)
    try:
        for mv in client.search_model_versions(f"name='{NAME}'"):
            print(f"deleting version {NAME} v{mv.version} stage={mv.current_stage}")
            try:
                client.delete_model_version(NAME, mv.version)
            except Exception as exc:
                print(f"  warn: {exc}")
        client.delete_registered_model(NAME)
        print(f"deleted registered model {NAME}")
    except Exception as exc:
        print(f"warn: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
