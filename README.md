# MeliSimLake

Plataforma Lakehouse e Machine Learning integrada ao **Melisim** — simulação do ecossistema Mercado Livre em microsserviços. Consome dados via CDC (Debezium) e Kafka, processa em camadas Bronze/Silver/Gold com Delta Lake, e serve modelos de ML via FastAPI.

**Repositórios:** este projeto ([MeliSimLake](https://github.com/mzmvyp/MeliSimLake)) + a fonte de dados ([MeliSim](https://github.com/mzmvyp/MeliSim)). Clone os dois lado a lado e use a rede Docker externa `melisim_melisim` conforme `docker-compose.override.yml`.

## Arquitetura em resumo

```
Melisim (microsserviços)
  ├── users-service (PostgreSQL)   ──CDC──▶ Bronze users
  ├── products-service (MySQL)     ──CDC──▶ Bronze products
  ├── orders-service (PostgreSQL)  ──CDC──▶ Bronze orders
  └── Kafka (eventos)              ────────▶ Bronze events
                                                │
                                     PySpark (Bronze → Silver)
                                                │
                                      dbt (Silver → Gold)
                                                │
                               ┌────────────────┼─────────────────┐
                           MLflow          Feature Store        Trino
                           (modelos)       (Feast)          (queries ad-hoc)
                               │
                           FastAPI (serving) + Streamlit (dashboard)
```

## Pré-requisitos

| Componente       | Versão  | Obrigatório |
|------------------|---------|-------------|
| Docker Desktop   | 24+     | sim         |
| Docker Compose   | v2      | sim         |
| RAM alocada      | 16 GB+  | sim         |
| Python           | 3.11    | sim         |
| Java             | 17      | sim (Spark) |
| Melisim          | qualquer| sim         |

## Quickstart

```bash
# 1. Clone e configure variáveis
cp .env.example .env
# Edite .env com as credenciais reais do Melisim

# 2. Suba a stack core
make up

# 3. Inicialize buckets e tópicos
make init

# 4. Verifique saúde
make health

# 5. Verifique portas
make ports
```

## Portas

| Serviço           | URL                       | Credencial padrão  |
|-------------------|---------------------------|--------------------|
| MinIO Console     | http://localhost:9001     | minioadmin/minioadmin123 |
| Airflow           | http://localhost:8080     | admin/admin123     |
| Spark Master      | http://localhost:8082     | —                  |
| Trino             | http://localhost:8084     | admin              |
| MLflow            | http://localhost:5000     | —                  |
| Prometheus        | http://localhost:9090     | —                  |
| Grafana           | http://localhost:3000     | admin/grafana123   |
| DataHub           | http://localhost:9002     | datahub/datahub    |
| Jupyter           | http://localhost:8888     | sem senha          |
| ML API            | http://localhost:8000     | —                  |
| Dashboard         | http://localhost:8501     | —                  |
| Schema Registry   | http://localhost:8081     | —                  |
| Debezium          | http://localhost:8083     | —                  |

## Comandos úteis

```bash
make up                  # sobe stack core
make up-all              # sobe tudo (incluindo governance, serving, dev)
make down                # para tudo
make ps                  # lista containers
make logs                # logs em tempo real
make health              # verifica todos os endpoints
make init-buckets        # (re)cria buckets MinIO
make init-topics         # (re)cria tópicos Kafka
make register-connectors # registra CDC Debezium
make lint                # ruff
make type-check          # mypy
make test                # pytest
make dbt-run             # dbt build (Silver → Gold)
make dbt-docs            # documentação dbt com lineage
```

## Profiles Docker Compose

| Profile      | O que inclui                   | Comando                          |
|--------------|--------------------------------|----------------------------------|
| (padrão)     | Infra core + Airflow + Spark   | `make up`                        |
| `dev`        | + Jupyter                      | `make up-all`                    |
| `serving`    | + ml-api + dashboard           | `make up-serving`                |
| `governance` | + DataHub                      | `make up-governance`             |

## Estrutura de pastas

```
melisimlake/
├── infra/               # Docker, configs de infraestrutura
├── ingestion/           # Ingestão Bronze (CDC, Kafka, Batch, API, Scraper)
├── transformation/      # Bronze→Silver (Spark) e Silver→Gold (dbt)
├── orchestration/       # DAGs Airflow
├── ml/                  # Modelos ML (ALS, XGBoost, LSTM, SASRec)
├── feature_store/       # Feast feature repo
├── serving/             # FastAPI (ml-api) + Streamlit (dashboard)
└── tests/               # Testes de integração e e2e

> **Nota:** O simulador de agentes que ficava em `simulator/` foi movido
> para o projeto vizinho **MeliCrowd** (`../MeliCrowd/`), que oferece
> arquitetura mais robusta (LangGraph, pool de 50 agentes paralelos,
> control plane FastAPI, replay de sessão).
```

Veja `ARCHITECTURE.md` para detalhes completos da arquitetura.
Veja `RUNBOOK.md` para troubleshooting e recovery.
