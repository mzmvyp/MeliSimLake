FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY src /app/src

ENV PYTHONPATH=/app

ENTRYPOINT ["/bin/sh","-c","while true; do echo \"[ml-trainer] $(date -u +%FT%TZ) running all trainers\"; python -m src.run_all || echo \"[ml-trainer] FAILED\"; echo \"[ml-trainer] sleep ${TRAINER_SLEEP_SECONDS:-300}s\"; sleep ${TRAINER_SLEEP_SECONDS:-300}; done"]
