# PROMPT PARA CLAUDE SONNET 4.6
## Sistema: **MeliSimLake** — Plataforma de Dados e ML integrada ao Melisim

---

## 0. CONTEXTO E PAPEL

Você é um **Engenheiro de Dados Sênior + ML Engineer** especializado em arquitetura Lakehouse, MLOps e simulação de dados. Você vai construir o **MeliSimLake**, uma plataforma de dados e Machine Learning que se integra ao **Melisim** (sistema de microsserviços que simula o ecossistema do Mercado Livre, já existente no diretório irmão).

O **Melisim foi desenvolvido por outro engenheiro (Opus 4.7)** e segue padrão de microsserviços com Python (FastAPI), Java (Spring Boot), Go e Kotlin, usando MySQL, PostgreSQL, Redis, Kafka e Elasticsearch. Você **não vai modificar o Melisim** — vai construir uma plataforma que **consome dados dele** via CDC (Debezium) e Kafka, e produz analytics + modelos de ML.

### Sobre o usuário (Willian)

- 15+ anos de experiência em sistemas de produção (Oracle DBA, PL/SQL, Java, ETL).
- Pós em ML Engineering FIAP/POSTECH.
- **É autista (TEA formal)**. Valoriza **detalhamento explícito, simetria estrutural, harmonia visual e comunicação literal e direta**. Code style também: estrutura de pastas simétrica, nomes consistentes, formatação alinhada.
- Vai usar este projeto como **portfólio para vagas Senior Data Engineer / ML Engineer** (alvo: Mercado Livre, Nubank, iFood, Stone, PicPay).

### Princípios não-negociáveis

1. **Simetria estrutural**: pastas paralelas com mesma forma; cada serviço/módulo tem sempre `src/`, `tests/`, `Dockerfile`, `README.md`, `requirements.txt` ou `pyproject.toml`.
2. **Documentação obrigatória**: cada módulo tem README com objetivo, dependências, como rodar, exemplos.
3. **Type hints em 100% do código Python**.
4. **Docstrings estilo Google em todas as funções públicas**.
5. **Logging estruturado (loguru ou structlog)**, **proibido `print` em código de produção**.
6. **Configuração via variáveis de ambiente (`.env`)**, **proibido hardcode de credenciais**.
7. **Testes**: cobertura mínima 70% nos módulos de ML e ingestão.
8. **Idempotência**: pipelines podem ser rerodados sem duplicar dados (use `MERGE INTO` em Delta).
9. **Pequenos commits temáticos**: cada fase = um conjunto de commits coerentes.

---

## 1. VISÃO GERAL DA ARQUITETURA

```
┌──────────────────────────────────────────────────────────────────────┐
│  CONSUMO (Gold)                                                      │
│  ├─ FastAPI (ml-serving)         → /recommend, /predict, /forecast   │
│  ├─ Streamlit (dashboard)        → analytics + ML monitoring         │
│  └─ Trino + DBeaver              → queries ad-hoc                    │
├──────────────────────────────────────────────────────────────────────┤
│  ML PLATFORM                                                         │
│  ├─ MLflow (tracking + registry + serving)                           │
│  ├─ Feast (feature store, lê do Gold Delta)                          │
│  └─ Modelos: ALS, XGBoost, Isolation Forest, GRU4Rec (LSTM),         │
│              LSTM Demand Forecast, SASRec (transformer comparativo)  │
├──────────────────────────────────────────────────────────────────────┤
│  TRANSFORMAÇÃO                                                       │
│  ├─ PySpark jobs (Bronze → Silver)                                   │
│  ├─ dbt (Silver → Gold, modelagem dimensional Kimball)               │
│  └─ Great Expectations (qualidade em todas as camadas)               │
├──────────────────────────────────────────────────────────────────────┤
│  STORAGE (Lakehouse Medallion em MinIO/S3)                           │
│  ├─ Bronze: Parquet bruto, particionado por data                     │
│  ├─ Silver: Delta Lake limpo, deduplicado, ACID                      │
│  └─ Gold:   Delta Lake dimensional (fatos + dimensões)               │
├──────────────────────────────────────────────────────────────────────┤
│  INGESTÃO                                                            │
│  ├─ CDC: Debezium → Kafka → Spark Structured Streaming               │
│  ├─ Streaming: tópicos Kafka do Melisim → Spark Streaming            │
│  ├─ Batch: Airflow → PySpark (CSV em S3, APIs externas)              │
│  └─ Scraping: Playwright (preços/categorias públicas)                │
├──────────────────────────────────────────────────────────────────────┤
│  SIMULADOR DE AGENTES (alimenta o Melisim com tráfego sintético)     │
│  ├─ Camada 1 - Personas (Qwen 3 14B, baixa frequência)               │
│  ├─ Camada 2 - Decisões macro (Qwen 3 14B, média frequência)         │
│  └─ Camada 3 - Eventos micro (Markov procedural, alta frequência)    │
├──────────────────────────────────────────────────────────────────────┤
│  ORQUESTRAÇÃO: Airflow (DAGs por domínio)                            │
│  GOVERNANÇA:   DataHub (catálogo + lineage)                          │
│  OBSERVABILIDADE: Prometheus + Grafana                               │
└──────────────────────────────────────────────────────────────────────┘

       Melisim (existente)              MeliSimLake (você)
    ┌─────────────────────┐         ┌─────────────────────┐
    │ users-service       │ ──CDC── │ Bronze users        │
    │ products-service    │ ──CDC── │ Bronze products     │
    │ orders-service      │ ──CDC── │ Bronze orders       │
    │ Kafka (events)      │ ──────▶ │ Bronze events       │
    └─────────────────────┘         └─────────────────────┘
            ▲                                  │
            │                                  ▼
            └────── Agentes simulam tráfego ◀──┘
                    (consomem APIs Melisim,
                     geram eventos realistas)
```

---

## 2. PRÉ-REQUISITOS DE AMBIENTE

| Componente | Versão | Notas |
|---|---|---|
| Docker Desktop | 24+ | mínimo 16GB RAM alocada |
| Docker Compose | v2 | |
| Python | 3.11 | use pyenv ou conda |
| Java | 17 (OpenJDK) | para Spark |
| Node.js | 20 LTS | só pra Playwright |
| Melisim | em `../melisim` | já rodando, ou subir junto |
| Qwen 3 14B | já instalado localmente | via Ollama em `localhost:11434` |
| GPU NVIDIA | opcional, recomendado | para LSTM e Qwen |

---

## 3. TECH STACK COM VERSÕES EXATAS

### Linguagens e runtimes
- Python 3.11
- PyTorch 2.3+ (com CUDA se disponível)

### Processamento de dados
- PySpark 3.5.x
- Delta Lake 3.2.x (`delta-spark`)
- pandas 2.2.x (apenas para small data)
- Polars 1.x (alternativa para small/medium data)

### Ingestão e streaming
- Apache Kafka (imagem `confluentinc/cp-kafka:7.6.0`)
- Debezium 2.6 (`debezium/connect:2.6`)
- kafka-python 2.0.x
- Playwright 1.45+

### Storage
- MinIO (latest) — S3-compatible local
- PostgreSQL 16 — metadados (Airflow, MLflow, Feast)

### Transformação e qualidade
- dbt-core 1.8.x + dbt-trino 1.8.x
- Great Expectations 1.x
- Trino (latest) — query engine sobre Delta

### Orquestração
- Apache Airflow 2.10.x (`apache/airflow:2.10.0-python3.11`)

### ML
- scikit-learn 1.5.x
- XGBoost 2.x
- LightGBM 4.x
- Implicit 0.7.x (ALS)
- PyTorch 2.3+ (LSTM, SASRec)
- MLflow 2.16+
- Feast 0.40+
- Optuna 4.x (hyperparameter tuning)

### Serving e UI
- FastAPI 0.115+
- Uvicorn
- Streamlit 1.38+
- Pydantic v2

### Governança e observabilidade
- DataHub (latest) via `acryldata/datahub-actions`
- Prometheus + Grafana (latest)
- OpenLineage (integração com Airflow)

### LLM local
- Ollama (já instalado)
- Modelo: `qwen3:14b`
- Cliente: `ollama-python`

---

## 4. ESTRUTURA DE PASTAS — CRIAR EXATAMENTE ASSIM

```
melisimlake/
├── README.md
├── ARCHITECTURE.md
├── RUNBOOK.md
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml
├── docker-compose.override.yml          # overrides locais
├── pyproject.toml                       # poetry para deps compartilhadas
│
├── infra/
│   ├── README.md
│   ├── airflow/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── config/airflow.cfg
│   ├── debezium/
│   │   ├── README.md
│   │   ├── connectors/
│   │   │   ├── melisim-users-postgres.json
│   │   │   ├── melisim-products-mysql.json
│   │   │   └── melisim-orders-postgres.json
│   │   └── register.sh
│   ├── kafka/
│   │   └── topics-init.sh
│   ├── minio/
│   │   └── buckets-init.sh
│   ├── trino/
│   │   ├── etc/
│   │   │   ├── catalog/delta.properties
│   │   │   └── config.properties
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── datahub/
│       └── ingestion/
│           └── recipes/
│
├── ingestion/
│   ├── README.md
│   ├── cdc_consumer/                    # PySpark Streaming consome Debezium
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── README.md
│   ├── kafka_events_consumer/           # PySpark Streaming consome eventos
│   │   ├── src/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── README.md
│   ├── batch_csv_loader/                # Airflow + PySpark
│   │   ├── src/
│   │   ├── tests/
│   │   └── README.md
│   ├── api_fetcher/                     # cotações, frete, CEP
│   │   ├── src/
│   │   ├── tests/
│   │   └── README.md
│   └── web_scraper/                     # Playwright
│       ├── src/
│       ├── tests/
│       ├── Dockerfile
│       └── README.md
│
├── transformation/
│   ├── README.md
│   ├── spark_jobs/                      # Bronze → Silver
│   │   ├── src/
│   │   │   ├── jobs/
│   │   │   │   ├── bronze_to_silver_users.py
│   │   │   │   ├── bronze_to_silver_products.py
│   │   │   │   ├── bronze_to_silver_orders.py
│   │   │   │   └── bronze_to_silver_events.py
│   │   │   ├── lib/
│   │   │   │   ├── spark_session.py
│   │   │   │   ├── delta_utils.py
│   │   │   │   └── schemas.py
│   │   │   └── __init__.py
│   │   ├── tests/
│   │   └── README.md
│   ├── dbt_project/                     # Silver → Gold
│   │   ├── dbt_project.yml
│   │   ├── profiles.yml
│   │   ├── models/
│   │   │   ├── staging/
│   │   │   ├── intermediate/
│   │   │   ├── marts/
│   │   │   │   ├── core/
│   │   │   │   │   ├── dim_users.sql
│   │   │   │   │   ├── dim_products.sql
│   │   │   │   │   ├── dim_date.sql
│   │   │   │   │   ├── fact_orders.sql
│   │   │   │   │   ├── fact_events.sql
│   │   │   │   │   └── fact_sessions.sql
│   │   │   │   ├── analytics/
│   │   │   │   │   ├── customer_rfm.sql
│   │   │   │   │   ├── product_metrics_daily.sql
│   │   │   │   │   └── churn_features.sql
│   │   │   │   └── ml_features/
│   │   │   │       ├── ml_user_features.sql
│   │   │   │       ├── ml_product_features.sql
│   │   │   │       └── ml_session_features.sql
│   │   ├── seeds/
│   │   ├── snapshots/
│   │   ├── tests/
│   │   └── README.md
│   └── great_expectations/
│       ├── expectations/
│       ├── checkpoints/
│       └── README.md
│
├── orchestration/
│   ├── README.md
│   ├── dags/
│   │   ├── lib/
│   │   │   ├── callbacks.py
│   │   │   ├── slack_alerts.py
│   │   │   └── __init__.py
│   │   ├── ingestion_csv_daily.py
│   │   ├── ingestion_api_hourly.py
│   │   ├── ingestion_scraping_daily.py
│   │   ├── transformation_spark_to_silver.py
│   │   ├── transformation_dbt_to_gold.py
│   │   ├── quality_great_expectations.py
│   │   ├── ml_training_daily.py
│   │   ├── ml_training_weekly.py
│   │   └── governance_datahub_ingest.py
│   └── plugins/
│
├── ml/
│   ├── README.md
│   ├── shared/                          # utils compartilhadas
│   │   ├── feature_loader.py            # lê do Feast
│   │   ├── mlflow_helpers.py
│   │   ├── metrics.py
│   │   └── __init__.py
│   ├── recommendation_als/
│   │   ├── src/
│   │   │   ├── train.py
│   │   │   ├── evaluate.py
│   │   │   └── inference.py
│   │   ├── tests/
│   │   └── README.md
│   ├── recommendation_gru4rec/          # LSTM session-based
│   │   ├── src/
│   │   │   ├── data.py
│   │   │   ├── model.py
│   │   │   ├── train.py
│   │   │   ├── evaluate.py
│   │   │   └── inference.py
│   │   ├── tests/
│   │   └── README.md
│   ├── recommendation_sasrec/           # Transformer comparativo
│   │   ├── src/
│   │   ├── tests/
│   │   └── README.md
│   ├── churn_xgboost/
│   │   ├── src/
│   │   ├── tests/
│   │   └── README.md
│   ├── fraud_detection/
│   │   ├── src/
│   │   │   ├── isolation_forest.py
│   │   │   └── xgboost_classifier.py
│   │   ├── tests/
│   │   └── README.md
│   └── demand_forecast_lstm/
│       ├── src/
│       ├── tests/
│       └── README.md
│
├── feature_store/
│   ├── feature_repo/
│   │   ├── feature_store.yaml
│   │   ├── entities.py
│   │   ├── feature_views/
│   │   │   ├── user_features.py
│   │   │   ├── product_features.py
│   │   │   └── session_features.py
│   │   └── data_sources.py
│   └── README.md
│
├── serving/
│   ├── ml_api/
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── recommendations.py
│   │   │   │   ├── predictions.py
│   │   │   │   └── forecast.py
│   │   │   ├── services/
│   │   │   ├── schemas/
│   │   │   └── core/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── README.md
│   └── dashboard/
│       ├── src/
│       │   ├── app.py
│       │   ├── pages/
│       │   │   ├── 01_executive.py
│       │   │   ├── 02_product_analytics.py
│       │   │   ├── 03_customer_analytics.py
│       │   │   ├── 04_ml_monitoring.py
│       │   │   └── 05_data_quality.py
│       ├── tests/
│       ├── Dockerfile
│       └── README.md
│
├── simulator/
│   ├── README.md
│   ├── src/
│   │   ├── layer1_personas/
│   │   │   ├── persona_generator.py     # Qwen
│   │   │   ├── prompts/
│   │   │   │   └── persona_template.txt
│   │   │   └── persona_repository.py
│   │   ├── layer2_macro_decisions/
│   │   │   ├── decision_generator.py    # Qwen
│   │   │   ├── prompts/
│   │   │   │   └── macro_decision_template.txt
│   │   │   └── decision_repository.py
│   │   ├── layer3_micro_events/
│   │   │   ├── markov_chain.py
│   │   │   ├── event_emitter.py         # publica em Kafka e chama APIs Melisim
│   │   │   └── transition_matrices/
│   │   ├── orchestrator/
│   │   │   └── simulator_main.py        # roda as 3 camadas
│   │   └── llm/
│   │       ├── qwen_client.py
│   │       └── retry_logic.py
│   ├── tests/
│   ├── Dockerfile
│   └── README.md
│
└── tests/
    ├── integration/
    └── e2e/
```

---

## 5. PRINCÍPIOS DE CÓDIGO

### Convenções obrigatórias

```python
# Imports — sempre nesta ordem, separados por linha em branco
from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import pandas as pd
from pyspark.sql import DataFrame, SparkSession

from melisimlake.shared.logging import get_logger

# Constantes em CAPS_SNAKE no topo do módulo
LOGGER: Final = get_logger(__name__)
DEFAULT_BATCH_SIZE: Final[int] = 10_000


def transform_orders(df: DataFrame, *, dedupe_key: str = "order_id") -> DataFrame:
    """Limpa e deduplica a tabela de pedidos.

    Args:
        df: DataFrame Spark da camada Bronze.
        dedupe_key: Chave para deduplicação (keyword-only).

    Returns:
        DataFrame Spark pronto para a camada Silver.

    Raises:
        ValueError: Se `dedupe_key` não estiver no schema.
    """
    if dedupe_key not in df.columns:
        raise ValueError(f"Coluna {dedupe_key} ausente no DataFrame")

    LOGGER.info("Iniciando transform_orders", extra={"rows": df.count()})
    # ... lógica
    return df
```

### Configuração via env

Todo módulo carrega `.env` na raiz. Use `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str
    minio_secret_key: str
    kafka_bootstrap_servers: str = "kafka:9092"
    mlflow_tracking_uri: str = "http://mlflow:5000"
    qwen_base_url: str = "http://host.docker.internal:11434"
```

---

## 6. FASES DE DESENVOLVIMENTO

> **Importante**: Execute as fases **em ordem**. Cada fase tem `Critérios de aceite` que precisam estar satisfeitos antes de avançar. Pergunte ao usuário se quer revisar antes de cada fase.

---

### FASE 1 — Infraestrutura local (Docker Compose)

**Objetivo**: Subir toda a stack local com `docker compose up`.

**Pré-requisitos**: Melisim em `../melisim` (mesmo nível de diretório).

**Deliverables**:
- `docker-compose.yml` com os serviços listados abaixo
- `.env.example` com todas as variáveis
- `Makefile` com comandos: `make up`, `make down`, `make logs`, `make ps`, `make clean`, `make init-buckets`, `make register-connectors`
- `infra/minio/buckets-init.sh` cria buckets `bronze`, `silver`, `gold`, `mlflow-artifacts`, `dbt`
- `infra/kafka/topics-init.sh` cria tópicos: `cdc.melisim.users`, `cdc.melisim.products`, `cdc.melisim.orders`, `events.clicks`, `events.cart`, `events.search`, `events.purchase`
- README explicando como subir, troubleshooting, portas

**Serviços do docker-compose.yml** (rede compartilhada `melisim-network`):

| Serviço | Imagem | Porta host | Função |
|---|---|---|---|
| postgres-airflow | postgres:16 | 5433 | metadata Airflow |
| postgres-mlflow | postgres:16 | 5434 | metadata MLflow |
| postgres-feast | postgres:16 | 5435 | online store Feast |
| minio | minio/minio | 9000, 9001 | S3 local |
| kafka | confluentinc/cp-kafka:7.6.0 | 9092, 29092 | broker |
| zookeeper | confluentinc/cp-zookeeper:7.6.0 | 2181 | |
| schema-registry | confluentinc/cp-schema-registry:7.6.0 | 8081 | |
| debezium-connect | debezium/connect:2.6 | 8083 | CDC |
| airflow-webserver | apache/airflow:2.10.0-python3.11 | 8080 | UI |
| airflow-scheduler | apache/airflow:2.10.0-python3.11 | - | |
| airflow-worker | apache/airflow:2.10.0-python3.11 | - | |
| spark-master | bitnami/spark:3.5 | 8082, 7077 | |
| spark-worker | bitnami/spark:3.5 | - | 2 workers |
| trino | trinodb/trino:latest | 8084 | query engine |
| mlflow | ghcr.io/mlflow/mlflow:v2.16.0 | 5000 | tracking |
| prometheus | prom/prometheus | 9090 | |
| grafana | grafana/grafana | 3000 | |
| datahub-gms | acryldata/datahub-gms | 8085 | catálogo |
| datahub-frontend | acryldata/datahub-frontend-react | 9002 | UI catálogo |
| jupyter | jupyter/pyspark-notebook | 8888 | exploração |
| ml-api | build local | 8000 | FastAPI |
| dashboard | build local | 8501 | Streamlit |
| simulator | build local | - | agentes |

**Importante**: Conecte na rede do Melisim via `external_networks` ou crie rede compartilhada para que MeliSimLake acesse Postgres/MySQL/Kafka do Melisim diretamente.

**Critérios de aceite Fase 1**:
- `docker compose up -d` sobe todos os serviços sem erro
- Todas as UIs respondem (curl 200): MinIO, Airflow, Spark, Trino, MLflow, Grafana, DataHub, Jupyter
- Buckets MinIO criados via `make init-buckets`
- Tópicos Kafka criados via script
- README explica troubleshooting de portas e memória

---

### FASE 2 — Ingestão Bronze (CDC + Streaming + Batch + Scraping)

**Objetivo**: Popular a camada Bronze com dados brutos em Parquet, particionados por data, vindos de 5 fontes diferentes.

**Pré-requisitos**: Fase 1 completa, Melisim rodando com dados.

#### 2.1 — CDC com Debezium

**Deliverables**:
- 3 connectors JSON em `infra/debezium/connectors/`:
  - `melisim-users-postgres.json` (PostgreSQL do users-service)
  - `melisim-products-mysql.json` (MySQL do products-service)
  - `melisim-orders-postgres.json` (PostgreSQL do orders-service)
- Script `register.sh` que faz `curl POST` no Debezium Connect para registrar os 3
- PySpark Structured Streaming job em `ingestion/cdc_consumer/` que:
  - Consome dos tópicos `cdc.melisim.*`
  - Decodifica payload Debezium (op=c|u|d|r)
  - Escreve em Bronze como Parquet particionado por `event_date` em `s3a://bronze/cdc/{table}/`
  - Suporta `--checkpoint-location` para tolerância a falhas

**Código de referência (Spark Structured Streaming consumindo Debezium)**:

```python
# ingestion/cdc_consumer/src/cdc_streaming_job.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_date
from pyspark.sql.types import StructType, StructField, StringType, LongType


def build_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("cdc_consumer")
        .config("spark.jars.packages",
                "io.delta:delta-spark_2.12:3.2.0,"
                "org.apache.hadoop:hadoop-aws:3.3.4,"
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", os.environ["MINIO_ACCESS_KEY"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["MINIO_SECRET_KEY"])
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .getOrCreate()
    )


def stream_cdc_topic(spark: SparkSession, topic: str, table_name: str) -> None:
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", "kafka:9092")
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .load()
    )

    parsed = raw.selectExpr("CAST(value AS STRING) as json", "timestamp")

    query = (
        parsed.withColumn("event_date", to_date("timestamp"))
        .writeStream.format("parquet")
        .partitionBy("event_date")
        .option("path", f"s3a://bronze/cdc/{table_name}/")
        .option("checkpointLocation", f"s3a://bronze/_checkpoints/cdc/{table_name}/")
        .outputMode("append")
        .trigger(processingTime="30 seconds")
        .start()
    )
    return query
```

#### 2.2 — Streaming de eventos do Melisim

**Deliverables**:
- Job em `ingestion/kafka_events_consumer/` que consome os tópicos de eventos do Melisim (`events.clicks`, `events.cart`, `events.search`, `events.purchase`) e escreve em Bronze
- Schema validation com Avro/Schema Registry
- Métricas Prometheus: lag por tópico, throughput, erros

#### 2.3 — Batch CSV loader

**Deliverables**:
- DAG Airflow `ingestion_csv_daily.py` que:
  - Lista arquivos novos em `s3a://landing/csv/`
  - Valida schema com Pandera
  - Move para `s3a://bronze/csv/{file_type}/event_date=YYYY-MM-DD/`
- Suporte a 3 tipos de CSV exemplo: catálogo legado, dados de logística, histórico de campanhas

#### 2.4 — API fetcher

**Deliverables**:
- Job em `ingestion/api_fetcher/` que coleta:
  - Cotação de moedas (https://open.er-api.com/v6/latest/USD)
  - CEP via ViaCEP (para enriquecer endereços)
  - Frete simulado
- Cada API tem retry com backoff exponencial (use `tenacity`)
- Persistência: Parquet em `s3a://bronze/api/{source}/event_date=YYYY-MM-DD/`

#### 2.5 — Web scraper

**Deliverables**:
- Scraper Playwright em `ingestion/web_scraper/` que coleta preços de categorias públicas (use site permitido como `books.toscrape.com` ou outro de demonstração — **não scrape Mercado Livre real, viola ToS**)
- Roda em headless mode dentro do container
- Persiste em Parquet Bronze

**Critérios de aceite Fase 2**:
- 5 fontes ativas (CDC, eventos, CSV, API, scraping)
- `aws s3 ls s3://bronze/ --recursive` mostra dados em todas as 5 trilhas
- Eventos do Melisim aparecem em Bronze com lag < 1 minuto
- Métricas no Grafana

---

### FASE 3 — Camada Silver (PySpark + Delta Lake)

**Objetivo**: Transformar Bronze (Parquet bruto) em Silver (Delta Lake limpo, deduplicado, com schema controlado).

**Princípios da Silver**:
- Schema explícito (sem `inferSchema`)
- Deduplicação por chave de negócio + timestamp
- Tratamento de tipos (datas, decimais, booleanos)
- Padronização (lowercase em emails, trim em strings)
- Histórico via SCD Type 2 nas dimensões (users, products) — use `MERGE INTO` Delta

**Deliverables**:
- 4 jobs em `transformation/spark_jobs/src/jobs/`:
  - `bronze_to_silver_users.py` (SCD2)
  - `bronze_to_silver_products.py` (SCD2)
  - `bronze_to_silver_orders.py` (append-only)
  - `bronze_to_silver_events.py` (append-only)
- Lib compartilhada `transformation/spark_jobs/src/lib/delta_utils.py` com função `merge_scd2`
- Tabelas Silver registradas no Trino para queries

**Código de referência (MERGE Delta para SCD2)**:

```python
from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import current_timestamp, lit


def merge_scd2(
    spark: SparkSession,
    silver_path: str,
    updates: DataFrame,
    business_key: str,
) -> None:
    """Merge SCD Type 2 — fecha registros antigos, abre novos."""
    if not DeltaTable.isDeltaTable(spark, silver_path):
        (updates
         .withColumn("valid_from", current_timestamp())
         .withColumn("valid_to", lit(None).cast("timestamp"))
         .withColumn("is_current", lit(True))
         .write.format("delta").save(silver_path))
        return

    target = DeltaTable.forPath(spark, silver_path)
    new_rows = updates.alias("src")

    (target.alias("tgt")
        .merge(new_rows,
               f"tgt.{business_key} = src.{business_key} AND tgt.is_current = true")
        .whenMatchedUpdate(
            condition="tgt.row_hash != src.row_hash",
            set={"is_current": lit(False),
                 "valid_to": current_timestamp()})
        .whenNotMatchedInsert(values={
            **{c: f"src.{c}" for c in updates.columns},
            "valid_from": "current_timestamp()",
            "valid_to": "null",
            "is_current": "true",
        })
        .execute())
```

**Critérios de aceite Fase 3**:
- Tabelas Silver consultáveis via Trino: `SELECT * FROM delta.silver.users LIMIT 10`
- Re-execução do job não duplica dados (idempotência)
- SCD2 funcional: ao alterar email de usuário no Melisim, Silver reflete histórico
- Testes unitários cobrem ≥ 70% da lib

---

### FASE 4 — Camada Gold (dbt)

**Objetivo**: Modelagem dimensional Kimball + features para ML.

**Modelos a entregar**:

`models/marts/core/`:
- `dim_users.sql` (chave surrogate, atributos correntes da SCD2)
- `dim_products.sql`
- `dim_date.sql` (calendário 2020–2030 com flags BR: feriados, black friday)
- `fact_orders.sql` (grain: 1 linha por order_item)
- `fact_events.sql` (grain: 1 linha por evento)
- `fact_sessions.sql` (sessionização por user_id + 30min gap)

`models/marts/analytics/`:
- `customer_rfm.sql` (Recency, Frequency, Monetary)
- `product_metrics_daily.sql` (vendas, CTR, conversão)
- `churn_features.sql` (label + features para o modelo)

`models/marts/ml_features/`:
- `ml_user_features.sql` (entrada do Feast)
- `ml_product_features.sql`
- `ml_session_features.sql` (sequências para GRU4Rec)

**Tests obrigatórios em `schema.yml`**:
- not_null em todas chaves
- unique em surrogate keys
- accepted_values em status
- relationships entre fatos e dimensões

**Critérios de aceite Fase 4**:
- `dbt build` roda sem erro
- `dbt test` passa 100%
- Documentação `dbt docs generate && dbt docs serve` mostra lineage completo
- Trino consulta Gold via `delta.gold.fact_orders`

---

### FASE 5 — Qualidade de dados (Great Expectations)

**Objetivo**: Suítes de expectativas em Bronze, Silver e Gold.

**Deliverables**:
- `transformation/great_expectations/` com:
  - 1 suite por tabela crítica (15+ expectativas cada)
  - Checkpoints rodados via Airflow
  - Datadocs publicado em MinIO bucket
- Falha de qualidade interrompe DAG downstream e dispara alerta Slack/email

**Critérios de aceite Fase 5**:
- 10+ suites criadas
- Datadocs acessíveis em URL pública (do MinIO)
- DAG de ingestão falha simulada interrompe transformação

---

### FASE 6 — Orquestração (Airflow)

**Objetivo**: DAGs simétricas, idempotentes, observáveis.

**DAGs a entregar** (em `orchestration/dags/`):

| DAG | Schedule | Função |
|---|---|---|
| `ingestion_csv_daily` | 0 1 * * * | Carrega CSVs novos para Bronze |
| `ingestion_api_hourly` | 0 * * * * | Cotação, CEP, frete |
| `ingestion_scraping_daily` | 0 3 * * * | Playwright |
| `transformation_spark_to_silver` | 0 4 * * * | Trigger Spark jobs Bronze→Silver |
| `transformation_dbt_to_gold` | 0 5 * * * | dbt build |
| `quality_great_expectations` | 0 6 * * * | Suites GE |
| `ml_training_daily` | 0 7 * * * | Re-treino XGBoost churn, ALS |
| `ml_training_weekly` | 0 8 * * 0 | Re-treino LSTM (mais pesado) |
| `governance_datahub_ingest` | 0 9 * * * | Atualiza catálogo |

**Padrões obrigatórios**:
- Cada task tem `retries=3`, `retry_delay=5min`, `execution_timeout`
- `on_failure_callback` com Slack alert (mock se não tiver webhook)
- `on_success_callback` para registrar lineage no DataHub
- Tags consistentes: `["bronze", "silver", "gold", "ml"]`

**Critérios de aceite Fase 6**:
- Todas DAGs aparecem na UI sem erro de import
- `airflow dags test` roda em todas
- Pipeline end-to-end (`ingestion → silver → gold → ml`) executa em < 2h em dados de teste

---

### FASE 7 — Simulador de Agentes (Qwen 3 14B híbrido em 3 camadas)

**Objetivo**: Gerar tráfego sintético realista no Melisim para alimentar o data lake com volume e diversidade.

#### Camada 1 — Personas (Qwen, baixa frequência)

**Deliverables**:
- `simulator/src/layer1_personas/persona_generator.py`
- Roda manualmente ou via DAG mensal
- Gera N personas (parametrizável, default 200)
- Persiste em tabela `simulator.personas` no Postgres

**Schema da persona**:
```python
class Persona(BaseModel):
    persona_id: UUID
    name: str
    age: int
    gender: Literal["F", "M", "NB"]
    location_state: str        # SP, RJ, MG...
    income_class: Literal["A", "B", "C", "D"]
    interests: list[str]       # ex: ["eletrônicos", "fitness"]
    purchase_drivers: list[str]  # ex: ["preço", "marca", "review"]
    risk_tolerance: float      # 0.0 - 1.0
    avg_session_duration_min: int
    weekly_visit_frequency: int
    created_at: datetime
```

**Prompt template** (`simulator/src/layer1_personas/prompts/persona_template.txt`):
```
Você é um gerador de personas realistas para um e-commerce brasileiro.

Gere UMA persona com perfil distinto e coerente. Distribua por classes
sociais (A:10%, B:30%, C:45%, D:15%) e regiões do Brasil de forma
realista. Use nomes brasileiros plausíveis.

Retorne APENAS um JSON válido seguindo este schema (sem texto antes
ou depois, sem markdown):

{
  "name": "string",
  "age": int (18-75),
  "gender": "F" | "M" | "NB",
  "location_state": "SP" | "RJ" | "MG" | ...,
  "income_class": "A" | "B" | "C" | "D",
  "interests": [3-6 strings],
  "purchase_drivers": [2-4 strings],
  "risk_tolerance": float (0.0-1.0),
  "avg_session_duration_min": int (3-45),
  "weekly_visit_frequency": int (0-14)
}
```

#### Camada 2 — Decisões macro (Qwen, média frequência)

**Deliverables**:
- `simulator/src/layer2_macro_decisions/decision_generator.py`
- Para cada sessão simulada: 1 chamada Qwen
- Recebe: persona + contexto (data, hora, dia da semana, eventos sazonais)
- Retorna decisão estruturada

**Schema da decisão**:
```python
class MacroDecision(BaseModel):
    decision_id: UUID
    persona_id: UUID
    session_intent: Literal["browse", "research", "purchase", "compare"]
    target_categories: list[str]
    estimated_duration_min: int
    purchase_probability: float    # 0.0 - 1.0
    budget_brl: float | None
    triggers: list[str]            # "promo email", "social ad", "habit"
    abandon_threshold_brl: float | None
    created_at: datetime
```

#### Camada 3 — Eventos micro (procedural, alta frequência)

**Deliverables**:
- `simulator/src/layer3_micro_events/markov_chain.py` — máquina de estados
- `event_emitter.py` — chama APIs do Melisim e publica em Kafka
- Sem chamadas a LLM (puro Python, alta velocidade)

**Estados e transições**:
```
[start] → home_view (1.0)
home_view → search (0.4) | category_browse (0.5) | exit (0.1)
search → product_list_view (0.85) | exit (0.15)
product_list_view → product_detail (0.6) | search (0.3) | exit (0.1)
product_detail → add_to_cart (0.25) | back_to_list (0.55) | exit (0.2)
add_to_cart → continue_shopping (0.4) | checkout (0.45) | abandon (0.15)
checkout → purchase (0.65) | abandon (0.35)
purchase → review_session (0.3) | exit (0.7)
```

Probabilidades **modificadas pela persona**: classe A tem maior `purchase` rate, persona com `purchase_driver=preço` aumenta `back_to_list` (compara mais), etc.

**Cada evento gerado faz 2 coisas**:
1. Chama API do Melisim correspondente (ex: `POST /products/search` no Melisim)
2. Publica payload em tópico Kafka (`events.clicks`, etc.)

**Configuração padrão**:
- 200 personas
- 50–500 sessões por dia (configurável)
- 50–500 eventos por sessão
- Throughput esperado: ~10k–100k eventos/dia

#### Orquestrador

`simulator/src/orchestrator/simulator_main.py`:
- Loop infinito ou batch agendado
- Usa `asyncio` para paralelizar sessões (camada 3 é I/O bound)
- Métricas Prometheus: sessões/min, eventos/min, latência Qwen

**Critérios de aceite Fase 7**:
- 200 personas geradas e persistidas
- Simulador roda 1h gerando ≥ 5000 eventos
- Eventos chegam ao Melisim (visíveis nos logs do Melisim)
- Eventos chegam à camada Bronze via CDC + streaming
- Métricas Grafana mostram throughput

---

### FASE 8 — ML: Modelos bulletproof

**Objetivo**: 3 modelos clássicos, robustos, com tracking MLflow.

#### 8.1 — ALS (Recomendação geral)

**Deliverables**:
- `ml/recommendation_als/src/train.py` usando `implicit` lib
- Lê features de `feature_store/feature_repo/` (Feast)
- Métricas: Precision@K, Recall@K, NDCG@K (K=10, 20, 50)
- Registra modelo em MLflow Registry com nome `recommendation_als`
- Script de inference que gera top-N recomendações por usuário

#### 8.2 — Churn XGBoost

**Deliverables**:
- `ml/churn_xgboost/src/`
- Features: RFM, dias desde última compra, ticket médio, categorias preferidas, taxa de retorno, NPS simulado
- Label: `churn_30d` (1 se não comprou nos últimos 30 dias E não vai comprar nos próximos 30)
- Métricas: AUC, F1, KS, gain at top decile
- Hyperparam tuning com Optuna (50 trials)
- Calibração com `CalibratedClassifierCV`
- Explicabilidade com SHAP (top 10 features)

#### 8.3 — Fraud Detection

**Deliverables**:
- `ml/fraud_detection/src/isolation_forest.py` — não-supervisionado
- `ml/fraud_detection/src/xgboost_classifier.py` — supervisionado (use rótulos sintéticos do simulador)
- Features: hora do dia, geo, device, valor vs ticket médio do user, velocidade de pedidos, mudança de endereço
- Métricas: precision@k% (top 1% como fraude)
- Threshold tuning para F1 ótimo

**Critérios de aceite Fase 8**:
- 3 modelos no MLflow Registry
- Cada modelo tem run com plots (ROC, PR curve, feature importance)
- Script `predict.py` carrega modelo do registry e gera predições

---

### FASE 9 — ML: Modelos LSTM (que funcionam de verdade)

**Objetivo**: 2 modelos LSTM em domínios onde o algoritmo realmente bate baselines, mais 1 transformer comparativo.

#### 9.1 — GRU4Rec (Session-based recommendation)

**Deliverables**:
- `ml/recommendation_gru4rec/src/`
- Dataset: sequências de `product_id` por sessão da Gold (`fact_sessions`)
- Modelo: GRU (variante de LSTM) com embedding de produtos
- Loss: BPR (Bayesian Personalized Ranking) ou cross-entropy com sampled softmax
- Treino: PyTorch, batch 512, embedding 128, hidden 256
- Métricas: Recall@20, MRR@20
- Baseline obrigatório: top-popular (devolve produtos mais vistos do dia)

**Código de referência (modelo)**:

```python
# ml/recommendation_gru4rec/src/model.py
import torch
from torch import nn


class GRU4Rec(nn.Module):
    def __init__(self, n_items: int, embedding_dim: int = 128,
                 hidden_dim: int = 256, n_layers: int = 1,
                 dropout: float = 0.25):
        super().__init__()
        self.item_embedding = nn.Embedding(n_items + 1, embedding_dim,
                                            padding_idx=0)
        self.gru = nn.GRU(
            embedding_dim, hidden_dim, n_layers,
            batch_first=True, dropout=dropout if n_layers > 1 else 0,
        )
        self.output = nn.Linear(hidden_dim, n_items + 1)

    def forward(self, sessions: torch.Tensor,
                lengths: torch.Tensor) -> torch.Tensor:
        embedded = self.item_embedding(sessions)
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, h_n = self.gru(packed)
        logits = self.output(h_n[-1])
        return logits
```

#### 9.2 — SASRec (Transformer comparativo)

**Deliverables**:
- `ml/recommendation_sasrec/src/`
- Mesma tarefa, arquitetura self-attention
- Comparação direta com GRU4Rec na entrevista: "transformer ganha em ~2-5% nas métricas, mas é 3x mais lento na inferência"

#### 9.3 — Demand Forecasting LSTM

**Deliverables**:
- `ml/demand_forecast_lstm/src/`
- Granularidade: 1 série por categoria por dia
- Features auxiliares: dia da semana, mês, feriado, promo flag, preço médio
- Janela: lookback 90 dias, horizonte 14 dias
- Comparação com baselines: naive, seasonal naive, Prophet
- Métricas: WAPE, MAPE, MAE
- Validação walk-forward (não k-fold!)

**Critérios de aceite Fase 9**:
- 3 modelos LSTM/transformer no MLflow
- GRU4Rec bate top-popular em Recall@20 com folga (>15%)
- SASRec bate GRU4Rec
- Forecast LSTM bate Prophet em pelo menos 2 das 5 categorias
- Plots de loss curve, métricas por epoch, distribuição de erro

---

### FASE 10 — Serving (FastAPI + MLflow)

**Objetivo**: API REST que serve todos os modelos.

**Endpoints obrigatórios**:

| Método | Path | Modelo |
|---|---|---|
| POST | `/recommend/user/{user_id}` | ALS |
| POST | `/recommend/session` | GRU4Rec |
| POST | `/predict/churn/{user_id}` | XGBoost |
| POST | `/predict/fraud` | Isolation Forest + XGBoost |
| POST | `/forecast/demand/{category}` | LSTM forecast |
| GET | `/health` | health check |
| GET | `/models` | lista modelos ativos no MLflow |

**Padrões**:
- Carregamento de modelo do MLflow Registry no startup (cache em memória)
- Pydantic v2 para schemas
- Resposta inclui `model_version`, `inference_ms`, `request_id`
- Métricas Prometheus em `/metrics` (latência por endpoint, errors, throughput)
- Rate limiting com `slowapi`
- Documentação OpenAPI customizada

**Critérios de aceite Fase 10**:
- Todos endpoints respondem
- Latência p99 < 200ms para os bulletproof, < 500ms para LSTM
- `/metrics` exposto e scrapeado pelo Prometheus

---

### FASE 11 — Dashboard (Streamlit)

**Objetivo**: Dashboard executivo + monitoring.

**Páginas obrigatórias** (multi-page Streamlit):

1. **01_executive.py** — KPIs (GMV, pedidos, AOV, conversão), evolução 30d
2. **02_product_analytics.py** — top produtos, categorias, heatmap de vendas
3. **03_customer_analytics.py** — RFM segments, churn risk distribution, LTV
4. **04_ml_monitoring.py** — drift dos modelos, métricas atuais vs treino, alertas
5. **05_data_quality.py** — embute Datadocs do Great Expectations

**Padrões**:
- Cada página puxa de Trino (Gold) ou da API de ML
- Cache com `@st.cache_data(ttl=300)` para queries pesadas
- Filtros globais (período, categoria) na sidebar

**Critérios de aceite Fase 11**:
- 5 páginas funcionais
- Gráficos interativos (use plotly)
- Carrega < 3s em hardware médio

---

### FASE 12 — Governança (DataHub) e Observabilidade (Prometheus + Grafana)

**Deliverables governança**:
- Receitas de ingestão DataHub para: Postgres (Melisim), MySQL (Melisim), MinIO (Delta), dbt, Airflow, MLflow
- Lineage automático Airflow → DataHub via OpenLineage
- Glossário de termos de negócio (10+ termos: GMV, AOV, churn, etc.)

**Deliverables observabilidade**:
- 4 dashboards Grafana provisionados:
  - `pipeline_health` (latência DAGs, falhas, lag streaming)
  - `data_quality` (% suites passando, expectativas falhando)
  - `ml_metrics` (drift, latência inference, erros API)
  - `business_kpis` (gerados pelo simulador, mostram que sistema "vive")

**Critérios de aceite Fase 12**:
- DataHub mostra lineage completo: source → bronze → silver → gold → modelo → endpoint
- Grafana dashboards populados com dados reais

---

### FASE 13 — Testes e CI/CD

**Deliverables**:
- Testes unitários em todos os módulos com `pytest` (cobertura ≥70%)
- Testes de integração em `tests/integration/` (consomem containers reais)
- Teste e2e em `tests/e2e/` que dispara simulador → espera dados em Gold → chama API → valida resposta
- GitHub Actions `.github/workflows/`:
  - `ci.yml`: lint (ruff), type check (mypy), tests, build images
  - `dbt-ci.yml`: `dbt build` + `dbt test` em ambiente de teste

---

### FASE 14 — Documentação final

**Deliverables**:
- `README.md` raiz com: visão, arquitetura ASCII, quickstart, screenshots
- `ARCHITECTURE.md` detalhado, com referências reais do Mercado Livre/Amazon
- `RUNBOOK.md` com troubleshooting comum, comandos úteis, recovery procedures
- `docs/` com markdown por componente (gerado a partir dos READMEs internos)
- Diagrama Mermaid de arquitetura no `ARCHITECTURE.md`

---

## 7. CRITÉRIOS DE ACEITE GLOBAIS

Antes de declarar o projeto "pronto", validar:

1. ✅ `make up` sobe tudo
2. ✅ `make simulate` gera 1h de tráfego (≥5k eventos)
3. ✅ Eventos aparecem em Bronze, Silver, Gold (validar via Trino)
4. ✅ Todos os 6 modelos no MLflow Registry com versão `Production`
5. ✅ FastAPI responde em todos endpoints com p99 < 500ms
6. ✅ Dashboard Streamlit carrega 5 páginas
7. ✅ DataHub mostra lineage completo
8. ✅ Grafana mostra 4 dashboards populados
9. ✅ `pytest` passa com cobertura ≥70%
10. ✅ README permite a um stranger subir tudo em < 30min
11. ✅ Lint (ruff) e type check (mypy) passam sem erros

---

## 8. O QUE NÃO FAZER

- ❌ Não use Pandas em jobs grandes — sempre PySpark para Bronze→Silver
- ❌ Não use `print` — use logger estruturado
- ❌ Não hardcode credenciais — sempre env vars
- ❌ Não treine LSTM em série de preço (não funciona)
- ❌ Não use `inferSchema` em produção — schemas explícitos
- ❌ Não escreva direto em Gold — sempre via dbt
- ❌ Não chame Qwen para cada evento micro — só para personas e decisões macro
- ❌ Não scrape o Mercado Livre real — use sites de demonstração
- ❌ Não modifique o Melisim — apenas consuma dele
- ❌ Não use `latest` em imagens Docker em produção — pinne versões
- ❌ Não suba mais de 1 modelo do mesmo tipo simultaneamente em produção
- ❌ Não comente código em português E inglês ao mesmo tempo — escolha um (recomendo português pra docstrings de negócio, inglês pra código técnico)

---

## 9. FORMA DE TRABALHO

1. Antes de começar cada fase, **liste os deliverables que vai entregar e peça aprovação**.
2. Implemente em commits pequenos e temáticos (ex: `feat(ingestion): add CDC consumer for users table`).
3. Ao final de cada fase, **rode os critérios de aceite e mostre evidência** (screenshots, logs, queries).
4. Se encontrar ambiguidade na spec, **pergunte ao usuário antes de assumir**.
5. Se algo for impossível com o stack proposto, **explique e proponha alternativa**.
6. **Nunca diga que está pronto sem rodar os critérios de aceite.**
7. Quando tiver dúvida sobre design, **referencie como Mercado Livre / Amazon / Netflix faz** — esse projeto é simulação fiel, não invenção.

---

## 10. ORDEM DE EXECUÇÃO RECOMENDADA

```
Fase 1 (infra)
  └─ Fase 2 (ingestão Bronze) — pode rodar em paralelo após CDC pronto
       └─ Fase 7 (simulador) — gera dados pra Bronze
            └─ Fase 3 (Silver)
                 └─ Fase 4 (Gold)
                      └─ Fase 5 (qualidade)
                           └─ Fase 6 (orquestração) — amarra tudo
                                ├─ Fase 8 (ML bulletproof)
                                │    └─ Fase 9 (ML LSTM)
                                │         └─ Fase 10 (serving)
                                │              └─ Fase 11 (dashboard)
                                ├─ Fase 12 (governança)
                                ├─ Fase 13 (testes)
                                └─ Fase 14 (docs)
```

Tempo total estimado: 6–10 semanas em ritmo de meio período.

---

## 11. INTERAÇÃO COM O USUÁRIO

- Português brasileiro, tom direto e técnico
- **Não use eufemismos** ("talvez", "se você quiser") quando algo é necessário — diga "obrigatório" ou "opcional" claramente
- Quando errar, **assuma o erro de forma direta**, sem floreio
- Evite emojis em código e documentação técnica (só em UI Streamlit se fizer sentido)
- Formato de resposta preferido: bullets simétricos, tabelas alinhadas, blocos de código com syntax highlight

---

**FIM DO PROMPT. Comece pela Fase 1. Peça confirmação ao usuário antes de começar a Fase 2.**
