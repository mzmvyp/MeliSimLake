# MeliSimLake — Runbook de Operações

## Subindo a stack

```bash
# Primeira vez
cp .env.example .env
# Edite .env com credenciais reais do Melisim
make up
make init
make health
```

## Windows (PowerShell)

- **`curl` não é o curl da GNU** — no PowerShell, `curl` chama `Invoke-WebRequest` e quebra com `-s` ou URLs. Use **`curl.exe`** (Windows 10+) ou **`Invoke-RestMethod` / `irm`**:

```powershell
# Lista de conectores (JSON)
irm http://localhost:8083/connectors

# Estado do conector melisim-postgres
irm http://localhost:8083/connectors/melisim-postgres/status | ConvertTo-Json -Depth 10
```

- **Dois repositórios / pastas**: comandos `kafka`, `debezium-connect`, `schema-registry` são do **MeliSimLake**. Tem de estar na pasta do lake, por exemplo:

```powershell
Set-Location C:\Users\Willian\python_projects\melisimlake
docker compose up -d kafka schema-registry debezium-connect
```

Em `MeliSim\` esse `docker compose` **não** tem esses serviços (`no such service` é esperado).

- **`make`**: se não tiver GNU Make, use `docker compose` direto:

```powershell
Set-Location C:\Users\Willian\python_projects\melisimlake
docker compose run --rm kafka-init                    # equivalente a make init-topics
docker compose -f docker-compose.yml -f docker-compose.melisim-network.yml up -d debezium-connect
bash infra/debezium/register.sh                     # Git Bash / WSL; ou registe manualmente pela REST API
```

- **`.env`**: copie a partir do repositório **melisimlake** (`Copy-Item .env.example .env`), não da pasta MeliSim.

## Troubleshooting comum

### 1. Serviço não sobe — porta em uso

```bash
make ps                          # lista containers
docker ps -a | grep -v melisim   # identifica conflito externo
# Altere a porta no docker-compose.override.yml
```

### 2. Airflow — DAGs não aparecem

```bash
make logs-airflow
# Verifique se há erro de import nas DAGs
docker exec melisimlake-airflow-scheduler airflow dags list
docker exec melisimlake-airflow-scheduler airflow dags report
```

### 3. Spark job falha com OutOfMemory

```bash
# Aumente memória dos workers no docker-compose.override.yml:
# SPARK_WORKER_MEMORY: 4G
# SPARK_WORKER_CORES: "4"
make restart
```

### 4. MinIO — bucket não encontrado

```bash
make init-buckets
# Se persistir, verifique se o volume está corrompido:
docker volume inspect melisimlake_minio-data
```

### 5. Kafka — tópico não existe

```bash
make init-topics
# Verificar tópicos existentes:
docker exec melisimlake-kafka kafka-topics \
  --bootstrap-server localhost:9092 --list
```

### 6. Debezium — sem dados do Melisim / conector FAILED

Checklist (ordem sugerida):

1. **Postgres do Melisim (`melisim-postgres`) — WAL lógico**  
   O `docker-compose.yml` do Melisim define `wal_level=logical` via `command` no serviço `postgres`.  
   Após alterar o compose, recrie o container para aplicar:  
   `docker compose -f /path/to/MeliSim/docker-compose.yml up -d postgres`  
   Confirme dentro do container:  
   `docker exec melisim-postgres psql -U melisim -d melisim -c "SHOW wal_level;"` → deve ser `logical`.

2. **Papel `REPLICATION` (Postgres)**  
   Em bases **já inicializadas** (volume antigo), o script `z-debezium_prereq.sql` do Melisim pode não ter corrido. Execute uma vez:  
   `docker exec melisim-postgres psql -U melisim -d melisim -c "ALTER ROLE melisim WITH REPLICATION;"`  
   (O utilizador `melisim` do compose é superuser; o `ALTER` é idempotente / documentação.)

3. **Rede Docker — Debezium vê o Postgres**  
   O hostname **`melisim-postgres`** só resolve a partir da rede do projeto Melisim (`melisim_melisim` por defeito).  
   Suba o Connect em **duas** redes (lake + Melisim):  
   `make up-debezium-melisim-net`  
   ou:  
   `docker compose -f docker-compose.yml -f docker-compose.melisim-network.yml up -d debezium-connect`  
   Confirme: `docker inspect melisimlake-debezium --format '{{json .NetworkSettings.Networks}}'`

4. **Kafka do lake — sem ambiguidade `kafka`**  
   O broker do lake anuncia **`melisimlake-kafka:9092`** (PLAINTEXT) para que, com o Connect na rede do Melisim, os metadados do broker **não** apontem para o hostname curto `kafka` (que poderia ser o broker do Melisim).  
   O `debezium-connect` usa `BOOTSTRAP_SERVERS=melisimlake-kafka:9092`.  
   **Nota:** os tópicos `events.*` e o Kafka à porta **19092** no Melisim são **outro cluster**; não são lidos pelo Debezium deste compose. Espelhar eventos de negócio para o lake exige mirror/replicação à parte.

5. **Tópicos CDC no broker do lake**  
   `make init-topics` (cria `cdc.melisim.public.*`, etc.). Listar:  
   `docker exec melisimlake-kafka kafka-topics --bootstrap-server localhost:9092 --list | findstr cdc` (Windows) ou `grep cdc`.

6. **Registo do conector**  
   `cp .env.example .env` e preencha `MELISIM_POSTGRES_*`. Depois: `make register-connectors`  
   (precisa de `curl`, `envsubst`, `python3` no PATH — Git Bash no Windows costuma servir.)

7. **Validação**  
   - Lista: `curl -s http://localhost:8083/connectors` → não deve ser `[]`.  
   - Estado: `curl -s http://localhost:8083/connectors/melisim-postgres/status` → `RUNNING` (não `FAILED`).  
   - Tráfego: após um `UPDATE` em `public.products` no Melisim, consuma o tópico (exemplo):  
     `docker exec melisimlake-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic cdc.melisim.public.products --from-beginning --max-messages 3`

```bash
curl -s http://localhost:8083/connectors?expand=status | python3 -m json.tool
curl -s -X POST http://localhost:8083/connectors/melisim-postgres/restart
```

### 7. MLflow — falha ao logar artefatos

```bash
# Verifique variáveis AWS no container MLflow
docker exec melisimlake-mlflow env | grep AWS
# Verifique conectividade com MinIO
docker exec melisimlake-mlflow curl http://minio:9000/minio/health/live
```

### 8. dbt build falha

```bash
cd transformation/dbt_project
dbt debug                       # valida conexão
dbt deps                        # instala pacotes
dbt build --select +failing_model  # roda apenas modelo e dependências
```

### 9. Trino — timeout em queries Delta

```bash
# Verifique se MinIO está acessível a partir do Trino
docker exec melisimlake-trino curl http://minio:9000/minio/health/live

# Verifique catalogo delta
curl -H "X-Trino-User: admin" http://localhost:8084/v1/catalog
```

## Recovery de dados

### Reprocessar partição Bronze específica

```bash
# Forçar re-execução de job Spark para data específica
docker exec melisimlake-spark-master spark-submit \
  --master spark://spark-master:7077 \
  /opt/spark-jobs/src/jobs/bronze_to_silver_users.py \
  --date 2026-01-15 \
  --mode overwrite
```

### Reset de tabela Silver (CUIDADO: apaga histórico)

```bash
# Apenas em ambiente de desenvolvimento
docker exec melisimlake-spark-master python3 -c "
from pyspark.sql import SparkSession
from delta.tables import DeltaTable
spark = SparkSession.builder.getOrCreate()
DeltaTable.forPath(spark, 's3a://silver/users/').restoreToVersion(0)
"
```

### Vacuum Delta Lake (libera espaço de versões antigas)

```bash
docker exec melisimlake-spark-master python3 -c "
from pyspark.sql import SparkSession
from delta.tables import DeltaTable
spark = SparkSession.builder.getOrCreate()
for path in ['s3a://silver/users/', 's3a://silver/products/', 's3a://silver/orders/']:
    dt = DeltaTable.forPath(spark, path)
    dt.vacuum(168)  # retém 7 dias
"
```

## Comandos de verificação rápida

```bash
# Dados em Bronze
docker exec melisimlake-minio mc ls local/bronze --recursive | head -20

# Query Silver via Trino
curl -s -X POST http://localhost:8084/v1/statement \
  -H "X-Trino-User: admin" \
  -H "Content-Type: text/plain" \
  -d "SELECT COUNT(*) FROM delta.silver.users"

# Modelos no MLflow
curl http://localhost:5000/api/2.0/mlflow/registered-models/list

# Lag Kafka
docker exec melisimlake-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --all-groups
```

## Ordem de inicialização (em caso de falha total)

1. `make up` — aguarda postgres, minio, kafka ficarem healthy
2. `make init-buckets` — cria buckets
3. `make init-topics` — cria tópicos
4. `make init-airflow` — inicializa banco airflow
5. `make register-connectors` — somente após Melisim estar rodando
6. Iniciar DAGs no Airflow UI
7. `make up-serving` — ml-api e dashboard
