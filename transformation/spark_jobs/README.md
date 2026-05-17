# transformation/spark_jobs

Jobs PySpark para transformar dados da camada Bronze em Silver (Delta Lake + SCD Type 2).

## Jobs disponíveis

| Job                            | Fonte Bronze       | Destino Silver     | Estratégia  |
|-------------------------------|--------------------|--------------------|-------------|
| `bronze_to_silver_users.py`   | cdc/users          | silver/users       | SCD Type 2  |
| `bronze_to_silver_products.py`| cdc/products       | silver/products    | SCD Type 2  |
| `bronze_to_silver_orders.py`  | cdc/orders         | silver/orders      | Upsert      |
| `bronze_to_silver_events.py`  | events/*           | silver/events      | Upsert      |

## Como rodar

```bash
spark-submit \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4 \
  transformation/spark_jobs/src/jobs/bronze_to_silver_users.py \
  --date 2026-01-15
```

## Verificar via Trino

```sql
SELECT * FROM delta.silver.users LIMIT 10;
SELECT COUNT(*) FROM delta.silver.orders;
SELECT COUNT(*), is_current FROM delta.silver.users GROUP BY is_current;
```

## Idempotência

Todos os jobs usam `MERGE INTO` do Delta Lake. Re-executar o mesmo job para a mesma data não duplica dados.
