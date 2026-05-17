# Infraestrutura — MeliSimLake

Configurações de infraestrutura para todos os serviços da stack.

## Estrutura

```
infra/
├── airflow/          # Dockerfile customizado + config
├── debezium/         # Conectores CDC (Postgres + MySQL)
├── grafana/          # Datasources + 4 dashboards provisionados
├── kafka/            # Script de criação de tópicos
├── minio/            # Script de criação de buckets
├── prometheus/       # Configuração de scraping
├── trino/            # Configuração do cluster (coordinator only)
└── datahub/          # Receitas de ingestão + glossário de negócio
```

## Serviços e Portas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| Airflow UI | 8080 | Orquestração de DAGs |
| Spark Master UI | 8082 | Status do cluster Spark |
| Trino UI | 8084 | Query engine over Delta Lake |
| MLflow | 5000 | Experiment tracking + Registry |
| MinIO Console | 9001 | Object storage S3-compatible |
| Kafka | 9092 | Message broker |
| Schema Registry | 8081 | Avro schema management |
| Debezium Connect | 8083 | CDC connectors REST API |
| Prometheus | 9090 | Métricas |
| Grafana | 3000 | Dashboards |
| DataHub GMS | 8085 | Data catalog API (`--profile governance`) |
| DataHub Frontend | 9002 | Data catalog UI (`--profile governance`) |

## Inicialização

```bash
# 1. Criar buckets no MinIO
bash infra/minio/buckets-init.sh

# 2. Criar tópicos no Kafka
bash infra/kafka/topics-init.sh

# 3. Registrar conectores Debezium
bash infra/debezium/register.sh
```

## Trino

Configurado como coordinator-only (sem workers separados) para ambiente local.
Catálogo `delta` aponta para MinIO via conector Hive com suporte a Delta Lake.

Credenciais default: sem autenticação (ambiente de desenvolvimento).

## Grafana

4 dashboards pré-provisionados:
- **Pipeline Health** — Kafka lag, Airflow DAG status, Spark, MinIO disk
- **Data Quality** — Great Expectations validation rates por camada
- **ML Metrics** — Inference latency, model metrics, drift
- **Business KPIs** — Simulador events, sessões, macro decisions

Datasource Prometheus configurado automaticamente via `datasources.yml`.
