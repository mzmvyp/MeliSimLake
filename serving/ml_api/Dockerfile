FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 libpq-dev gcc curl ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.30.0" \
    pydantic==2.8.0 \
    pydantic-settings==2.4.0 \
    mlflow==2.16.0 \
    boto3==1.35.36 \
    prometheus-client==0.21.0 \
    loguru==0.7.2 \
    httpx==0.27.0 \
    xgboost==2.1.1 \
    scikit-learn==1.5.2 \
    numpy==1.26.4 \
    pandas==2.2.2 \
    scipy==1.13.1 \
    torch==2.4.1 \
    implicit==0.7.2 \
    trino==0.331.0

WORKDIR /app
COPY . /app/serving/ml_api/
RUN touch /app/serving/__init__.py /app/serving/ml_api/__init__.py /app/serving/ml_api/src/__init__.py

ENV PYTHONPATH=/app

CMD ["uvicorn", "serving.ml_api.src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
