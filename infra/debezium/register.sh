#!/usr/bin/env bash
# =============================================================================
# infra/debezium/register.sh
# Registra conectores Debezium via REST API (substitui $VAR do .env com envsubst).
# Pré-requisito: Debezium em localhost:8083 e Postgres do Melisim alcançável a partir
# do container (rede compartilhada — ver docker-compose.melisim-network.yml).
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${MELISIM_POSTGRES_HOST:=melisim-postgres}"
: "${MELISIM_POSTGRES_PORT:=5432}"
: "${MELISIM_POSTGRES_USER:=melisim}"
: "${MELISIM_POSTGRES_PASSWORD:=melisim123}"
: "${MELISIM_POSTGRES_DB:=melisim}"
: "${MELISIM_POSTGRES_TABLES:=public.products,public.payments,public.notifications}"

export MELISIM_POSTGRES_HOST MELISIM_POSTGRES_PORT MELISIM_POSTGRES_USER
export MELISIM_POSTGRES_PASSWORD MELISIM_POSTGRES_DB MELISIM_POSTGRES_TABLES

if ! command -v envsubst >/dev/null 2>&1; then
  echo "[debezium] ERRO: envsubst não encontrado (instale gettext / Git Bash completo)." >&2
  exit 1
fi

DEBEZIUM_URL="${DEBEZIUM_URL:-http://localhost:8083}"
CONNECTORS_DIR="$(dirname "$0")/connectors"

echo "[debezium] Aguardando Debezium Connect em ${DEBEZIUM_URL}..."
until curl -sf "${DEBEZIUM_URL}/connectors" > /dev/null; do
  echo "[debezium] Debezium ainda não pronto, aguardando 5s..."
  sleep 5
done

echo "[debezium] Debezium disponível. Registrando conectores..."
echo "[debezium] Alvo Postgres: ${MELISIM_POSTGRES_HOST}:${MELISIM_POSTGRES_PORT} db=${MELISIM_POSTGRES_DB} tables=${MELISIM_POSTGRES_TABLES}"

for connector_file in "${CONNECTORS_DIR}"/*.json; do
  [[ -e "${connector_file}" ]] || continue
  connector_name=$(basename "${connector_file}" .json)
  echo "[debezium] Registrando conector: ${connector_name}"

  payload="$(envsubst < "${connector_file}")"

  http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    "${DEBEZIUM_URL}/connectors/${connector_name}")

  if [[ "${http_code}" == "200" ]]; then
    echo "[debezium] Conector '${connector_name}' já existe. Atualizando config..."
    config_only="$(echo "${payload}" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['config']))")"
    curl -sf \
      -X PUT \
      -H "Content-Type: application/json" \
      --data-binary "${config_only}" \
      "${DEBEZIUM_URL}/connectors/${connector_name}/config" | python3 -m json.tool
  else
    echo "[debezium] Criando conector '${connector_name}'..."
    curl -sf \
      -X POST \
      -H "Content-Type: application/json" \
      --data-binary "${payload}" \
      "${DEBEZIUM_URL}/connectors" | python3 -m json.tool
  fi

  echo ""
done

echo "[debezium] Conectores registrados:"
curl -sf "${DEBEZIUM_URL}/connectors" | python3 -m json.tool
