# Debezium CDC — MeliSimLake

CDC (Change Data Capture) lê o **Postgres do MeliSim** (`melisim-postgres`, base `melisim`) e publica no **Kafka do lake** (`melisimlake-kafka`).

## Conector unificado

| Ficheiro | Nome REST | Tópicos (prefix `topic.prefix=cdc.melisim`) |
|----------|-----------|-----------------------------------------------|
| `connectors/melisim-postgres.json` | `melisim-postgres` | `cdc.melisim.public.products`, `cdc.melisim.public.payments`, `cdc.melisim.public.notifications`, … conforme `MELISIM_POSTGRES_TABLES` no `.env` |

Pré-requisitos no **MeliSim**: `wal_level=logical`, utilizador com `REPLICATION`, e o container `melisimlake-debezium` na rede `melisim_melisim` para resolver `melisim-postgres`. Ver **RUNBOOK.md** § Debezium.

## Registo

```bash
make register-connectors
# ou: bash infra/debezium/register.sh
```

## Verificar

```bash
curl -s http://localhost:8083/connectors
curl -s http://localhost:8083/connectors/melisim-postgres/status
curl -s -X POST http://localhost:8083/connectors/melisim-postgres/restart
```

## DLQ

- `dlq.cdc` — falhas downstream dos jobs de ingestão
- `dlq.events` — falhas em tópicos de eventos de simulação (cluster diferente do CDC)
