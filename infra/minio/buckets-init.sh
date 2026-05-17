#!/bin/bash
# =============================================================================
# infra/minio/buckets-init.sh
# Cria buckets MinIO necessários para o MeliSimLake.
# Executado automaticamente pelo serviço minio-init no docker-compose.
# =============================================================================

set -euo pipefail

MINIO_ALIAS="local"
MINIO_ENDPOINT="http://minio:9000"
MINIO_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-minioadmin123}"

echo "[minio-init] Aguardando MinIO ficar disponível..."
until mc alias set "${MINIO_ALIAS}" "${MINIO_ENDPOINT}" "${MINIO_USER}" "${MINIO_PASS}" 2>/dev/null; do
    echo "[minio-init] MinIO ainda não pronto, aguardando 5s..."
    sleep 5
done

echo "[minio-init] MinIO disponível. Criando buckets..."

BUCKETS=(
    "bronze"
    "silver"
    "gold"
    "mlflow-artifacts"
    "dbt"
    "landing"
    "great-expectations"
    "checkpoints"
)

for bucket in "${BUCKETS[@]}"; do
    if mc ls "${MINIO_ALIAS}/${bucket}" > /dev/null 2>&1; then
        echo "[minio-init] Bucket '${bucket}' já existe — skipping."
    else
        mc mb "${MINIO_ALIAS}/${bucket}"
        echo "[minio-init] Bucket '${bucket}' criado."
    fi
done

# Política pública para great-expectations (datadocs)
mc anonymous set download "${MINIO_ALIAS}/great-expectations" || true

echo "[minio-init] Todos os buckets prontos:"
mc ls "${MINIO_ALIAS}"
