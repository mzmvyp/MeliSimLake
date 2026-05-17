# Pipeline Guide — MeliSimLake

## Fluxo Completo de Dados

```
Melisim API/DB ──► Debezium ──► Kafka ──► Spark Streaming ──► Bronze (S3/MinIO)
                                  ▲                                    │
MeliCrowd (events.simulator.*) ───┘                                    │
                                                                        ▼
                                                         Spark Batch ──► Silver (Delta)
                                                                        │
                                                                        ▼
                                                             dbt + Trino ──► Gold (Delta)
                                                                        │
                                                                 ┌──────┼──────┐
                                                                 ▼      ▼      ▼
                                                               Feast  MLflow  Dashboard
                                                            (Features) (Models) (Streamlit)
```

> **Nota:** o simulador de tráfego sintético foi extraído para o projeto vizinho **MeliCrowd** (`../MeliCrowd/`). Ele publica eventos no broker Kafka deste lake (`events.simulator.*`).

---

## DAGs Airflow

### Ordem de Execução Recomendada (primeira vez)

1. `ingestion_cdc_streaming` (contínuo — não precisa disparar manualmente)
2. `ingestion_events_streaming` (contínuo)
3. `transformation_spark_to_silver` (schedule: `0 2 * * *`)
4. `transformation_dbt_to_gold` (schedule: `0 4 * * *`)
5. `data_quality_validation` (schedule: `0 5 * * *`)
6. `ml_training_daily` (schedule: `0 6 * * *`)
7. `ml_training_weekly` (schedule: `0 6 * * 0`)
8. `feast_materialize` (schedule: `0 7 * * *`)
9. `governance_datahub_ingest` (schedule: `0 9 * * *`)

### DAG: `transformation_spark_to_silver`

```
bronze_to_silver_users ─┐
                         ├─► bronze_to_silver_orders ─► bronze_to_silver_events
bronze_to_silver_products┘
```

**SLA**: completar em < 60 minutos

### DAG: `transformation_dbt_to_gold`

```
dbt_deps → staging_models → core_models → analytics_models ─┐
                                                               ├─► ml_features_models
                                                               └─► (paralelo)
```

### DAG: `ml_training_daily`

```
train_als ──────┐
train_churn ────┼──► (paralelo, independentes)
train_fraud ────┘
```

### DAG: `ml_training_weekly`

```
train_gru4rec ──┐
train_sasrec ───┼──► (paralelo)
train_lstm ─────┘
```

---

## Comandos Make

### Setup inicial

```bash
# Subir infraestrutura base
make up

# Inicializar buckets MinIO e tópicos Kafka
make init

# Registrar conectores Debezium
make register-connectors

# Verificar saúde dos serviços
make health
```

### Desenvolvimento

```bash
# Subir tudo incluindo serviços de governance
make up-all

# Subir apenas serving (API + Dashboard)
make up-serving

# Ver logs do Airflow
make logs-airflow

# Ver logs do Spark
make logs-spark
```

### Qualidade e Testes

```bash
# Lint + format check
make lint

# Auto-formatação
make format

# Type checking
make type-check

# Testes unitários
make test

# Testes com cobertura
make test-cov
```

### dbt

```bash
# Executar todos os modelos
make dbt-run

# Executar testes de schema
make dbt-test

# Gerar documentação
make dbt-docs
```

---

## Troubleshooting

### Kafka consumer lag alto

```bash
# Ver lag atual
docker exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --all-groups

# Reiniciar consumer (Spark Streaming)
make restart service=spark-worker-1
```

### Delta Lake corrompido

```bash
# Verificar histórico de operações
# Via PySpark:
from delta.tables import DeltaTable
dt = DeltaTable.forPath(spark, "s3a://silver/users/")
dt.history().show()

# Restaurar versão anterior
dt.restoreToVersion(N)
```

### MLflow indisponível no startup da API

A API tenta carregar modelos do MLflow Registry. Se falhar:
1. Verifica `MLFLOW_TRACKING_URI` no `.env`
2. `docker logs mlflow` para erros de conexão com PostgreSQL
3. API continua funcionando com `models_loaded=[]` — endpoints retornam 503

### Airflow tasks em `zombie` state

```bash
# Limpar estados zumbis
docker exec airflow-scheduler airflow tasks clear --dag-id <dag_id> --start-date <date>
```

Ver RUNBOOK.md para 10 cenários completos de troubleshooting.
