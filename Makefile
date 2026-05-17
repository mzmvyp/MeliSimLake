# =============================================================================
# MeliSimLake — Makefile
# =============================================================================

.PHONY: help up down logs ps clean init-buckets register-connectors \
        init-topics lint test build

COMPOSE := docker compose

help: ## Exibe ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Ciclo de vida da stack
# -----------------------------------------------------------------------------

up: ## Sobe todos os serviços core (sem governance)
	$(COMPOSE) up -d
	@echo "Stack core rodando. Use 'make ps' para verificar."

up-all: ## Sobe TODOS os serviços (incluindo governance, serving, dev)
	$(COMPOSE) --profile governance --profile serving --profile dev up -d

up-serving: ## Sobe os serviços de serving (ml-api + dashboard)
	$(COMPOSE) --profile serving up -d

up-governance: ## Sobe DataHub
	$(COMPOSE) --profile governance up -d

down: ## Para todos os serviços
	$(COMPOSE) --profile governance --profile serving --profile dev down

down-v: ## Para todos os serviços e remove volumes (CUIDADO: apaga dados!)
	$(COMPOSE) --profile governance --profile serving --profile dev down -v

restart: down up ## Reinicia a stack core

# -----------------------------------------------------------------------------
# Observabilidade
# -----------------------------------------------------------------------------

logs: ## Mostra logs em tempo real (todos os serviços)
	$(COMPOSE) logs -f

logs-airflow: ## Logs do Airflow webserver
	$(COMPOSE) logs -f airflow-webserver airflow-scheduler

logs-spark: ## Logs do Spark master
	$(COMPOSE) logs -f spark-master

logs-kafka: ## Logs do Kafka
	$(COMPOSE) logs -f kafka

ps: ## Lista containers e status
	$(COMPOSE) ps

health: ## Verifica health de todos os serviços
	@echo "=== MinIO ==="
	@curl -sf http://localhost:9000/minio/health/live && echo "OK" || echo "FAIL"
	@echo "=== Airflow ==="
	@curl -sf http://localhost:8080/health && echo "OK" || echo "FAIL"
	@echo "=== Spark ==="
	@curl -sf http://localhost:8082 > /dev/null && echo "OK" || echo "FAIL"
	@echo "=== Trino ==="
	@curl -sf http://localhost:8084/v1/info && echo "OK" || echo "FAIL"
	@echo "=== MLflow ==="
	@curl -sf http://localhost:5000/health && echo "OK" || echo "FAIL"
	@echo "=== Grafana ==="
	@curl -sf http://localhost:3000/api/health && echo "OK" || echo "FAIL"
	@echo "=== Schema Registry ==="
	@curl -sf http://localhost:8081/subjects && echo "OK" || echo "FAIL"

# -----------------------------------------------------------------------------
# Inicialização
# -----------------------------------------------------------------------------

init-buckets: ## Cria buckets no MinIO
	$(COMPOSE) run --rm minio-init

init-topics: ## Cria tópicos Kafka
	$(COMPOSE) run --rm kafka-init

init-airflow: ## Inicializa banco e usuário admin do Airflow
	$(COMPOSE) run --rm airflow-init

init: init-buckets init-topics init-airflow ## Inicialização completa

register-connectors: ## Registra conectores Debezium
	@bash infra/debezium/register.sh

up-debezium-melisim-net: ## Recria Debezium ligado à rede Docker do Melisim (CDC)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.melisim-network.yml up -d debezium-connect

# -----------------------------------------------------------------------------
# Desenvolvimento e qualidade
# -----------------------------------------------------------------------------

lint: ## Roda ruff em todo o código Python
	ruff check .
	ruff format --check .

format: ## Formata código com ruff
	ruff format .
	ruff check --fix .

type-check: ## Roda mypy
	mypy ingestion/ transformation/spark_jobs/src/ ml/ serving/ --ignore-missing-imports

test: ## Roda todos os testes
	pytest tests/ ingestion/ transformation/ ml/ serving/ -v --tb=short

test-cov: ## Roda testes com coverage
	pytest tests/ ingestion/ transformation/ ml/ serving/ \
	  --cov=ingestion --cov=transformation --cov=ml --cov=serving \
	  --cov-report=html --cov-report=term-missing

# -----------------------------------------------------------------------------
# Build de imagens
# -----------------------------------------------------------------------------

build: ## Builda imagens locais (ml-api, dashboard)
	$(COMPOSE) --profile serving build

build-api: ## Builda apenas ml-api
	$(COMPOSE) build ml-api

build-dashboard: ## Builda apenas dashboard
	$(COMPOSE) build dashboard

# -----------------------------------------------------------------------------
# dbt
# -----------------------------------------------------------------------------

dbt-run: ## Roda dbt build (Silver → Gold)
	cd transformation/dbt_project && dbt build

dbt-test: ## Roda dbt test
	cd transformation/dbt_project && dbt test

dbt-docs: ## Gera e serve documentação dbt
	cd transformation/dbt_project && dbt docs generate && dbt docs serve

# -----------------------------------------------------------------------------
# Limpeza
# -----------------------------------------------------------------------------

clean: ## Remove containers parados e imagens não usadas
	docker system prune -f

clean-all: down-v clean ## Para tudo, remove volumes e limpa docker (DESTRUTIVO)
	@echo "Stack completamente limpa."

# Portas de acesso rápido
open-minio:       ## Abre MinIO console
	@echo "MinIO Console: http://localhost:9001"

open-airflow:     ## Abre Airflow UI
	@echo "Airflow: http://localhost:8080 (admin/admin123)"

open-spark:       ## Abre Spark UI
	@echo "Spark: http://localhost:8082"

open-trino:       ## Abre Trino UI
	@echo "Trino: http://localhost:8084"

open-mlflow:      ## Abre MLflow UI
	@echo "MLflow: http://localhost:5000"

open-grafana:     ## Abre Grafana
	@echo "Grafana: http://localhost:3000 (admin/grafana123)"

open-jupyter:     ## Abre Jupyter
	@echo "Jupyter: http://localhost:8888"

ports:            ## Lista todas as portas
	@echo ""
	@echo "  Serviço            URL"
	@echo "  ───────────────    ────────────────────────"
	@echo "  MinIO API          http://localhost:9000"
	@echo "  MinIO Console      http://localhost:9001"
	@echo "  Airflow            http://localhost:8080"
	@echo "  Spark Master       http://localhost:8082"
	@echo "  Trino              http://localhost:8084"
	@echo "  MLflow             http://localhost:5000"
	@echo "  Prometheus         http://localhost:9090"
	@echo "  Grafana            http://localhost:3000"
	@echo "  DataHub            http://localhost:9002"
	@echo "  Jupyter            http://localhost:8888"
	@echo "  ML API             http://localhost:8000"
	@echo "  Dashboard          http://localhost:8501"
	@echo "  Kafka              localhost:29092"
	@echo "  Schema Registry    http://localhost:8081"
	@echo "  Debezium           http://localhost:8083"
	@echo "  Zookeeper          localhost:2181"
	@echo "  PostgreSQL Airflow localhost:5433"
	@echo "  PostgreSQL MLflow  localhost:5434"
	@echo "  PostgreSQL Feast   localhost:5435"
	@echo ""
