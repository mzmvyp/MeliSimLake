#!/bin/bash
# =============================================================================
# infra/kafka/topics-init.sh
# Cria tópicos Kafka necessários para o MeliSimLake.
# Executado automaticamente pelo serviço kafka-init no docker-compose.
# =============================================================================

set -euo pipefail

KAFKA_BOOTSTRAP="melisimlake-kafka:9092"
PARTITIONS=3
REPLICATION=1
DEBEZIUM_PARTITIONS=1

echo "[kafka-init] Aguardando Kafka ficar disponível em ${KAFKA_BOOTSTRAP}..."
until kafka-broker-api-versions --bootstrap-server "${KAFKA_BOOTSTRAP}" > /dev/null 2>&1; do
    echo "[kafka-init] Kafka ainda não pronto, aguardando 5s..."
    sleep 5
done

echo "[kafka-init] Kafka disponível. Criando tópicos..."

TOPICS=(
    # CDC — Debezium 2.x: <topic.prefix>.<schema>.<table> (topic.prefix=cdc.melisim no conector)
    "cdc.melisim.public.products"
    "cdc.melisim.public.payments"
    "cdc.melisim.public.notifications"
    # Compat: tópicos legados (podem ficar vazios se o Melisim não expuser essas tabelas)
    "cdc.melisim.public.users"
    "cdc.melisim.public.orders"

    # Eventos de comportamento do usuário
    "events.clicks"
    "events.cart"
    "events.search"
    "events.purchase"
    "events.sessions"
    "events.reviews"

    # Dead-letter queue para mensagens com falha
    "dlq.cdc"
    "dlq.events"
)

DEBEZIUM_COMPACT_TOPICS=(
    "debezium.configs"
    "debezium.offsets"
    "debezium.status"
)

for topic in "${TOPICS[@]}"; do
    if kafka-topics \
        --bootstrap-server "${KAFKA_BOOTSTRAP}" \
        --describe \
        --topic "${topic}" > /dev/null 2>&1; then
        echo "[kafka-init] Tópico '${topic}' já existe — skipping."
    else
        kafka-topics \
            --bootstrap-server "${KAFKA_BOOTSTRAP}" \
            --create \
            --topic "${topic}" \
            --partitions "${PARTITIONS}" \
            --replication-factor "${REPLICATION}"
        echo "[kafka-init] Tópico '${topic}' criado."
    fi
done

echo ""
echo "[kafka-init] Garantindo tópicos internos do Debezium com 1 partição..."
for topic in "${DEBEZIUM_COMPACT_TOPICS[@]}"; do
    if kafka-topics \
        --bootstrap-server "${KAFKA_BOOTSTRAP}" \
        --describe \
        --topic "${topic}" > /dev/null 2>&1; then
        echo "[kafka-init] Tópico '${topic}' já existe — skipping create."
    else
        kafka-topics \
            --bootstrap-server "${KAFKA_BOOTSTRAP}" \
            --create \
            --topic "${topic}" \
            --partitions "${DEBEZIUM_PARTITIONS}" \
            --replication-factor "${REPLICATION}" \
            --config cleanup.policy=compact
        echo "[kafka-init] Tópico '${topic}' criado com partição única e compact."
    fi
done

echo ""
echo "[kafka-init] Aplicando cleanup.policy=compact nos tópicos internos do Debezium..."
for topic in "${DEBEZIUM_COMPACT_TOPICS[@]}"; do
    kafka-configs \
        --bootstrap-server "${KAFKA_BOOTSTRAP}" \
        --alter \
        --entity-type topics \
        --entity-name "${topic}" \
        --add-config cleanup.policy=compact
    echo "[kafka-init] Tópico '${topic}' configurado como compact."
done

echo ""
echo "[kafka-init] Tópicos disponíveis:"
kafka-topics --bootstrap-server "${KAFKA_BOOTSTRAP}" --list
