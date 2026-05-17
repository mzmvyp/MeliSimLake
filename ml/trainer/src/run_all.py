"""Roda todos os trainers em sequencia, tolerando falhas individuais."""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone

from loguru import logger

from . import train_churn, train_demand_forecast, train_payment_failure, train_recommender


def main() -> int:
    started = time.time()
    results = {}
    for name, mod in [
        ("churn", train_churn),
        ("payment_failure", train_payment_failure),
        ("demand_forecast", train_demand_forecast),
        ("recommender", train_recommender),
    ]:
        t0 = time.time()
        try:
            logger.info(f"=== running {name} ===")
            results[name] = {"result": mod.run(), "elapsed_s": round(time.time() - t0, 2)}
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            results[name] = {
                "status": "error",
                "error": str(exc),
                "elapsed_s": round(time.time() - t0, 2),
            }
            logger.exception(f"{name} failed: {exc}")
    summary = {
        "ran_at": datetime.now(tz=timezone.utc).isoformat(),
        "elapsed_s_total": round(time.time() - started, 2),
        "results": results,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
