# ingestion/cdc_consumer

Spark Structured Streaming que consome tópicos Debezium do Kafka e escreve em Bronze (Parquet particionado por `event_date`).

## Tópicos consumidos

| Tópico                              | Tabela origem        | Banco        |
|-------------------------------------|----------------------|--------------|
| `cdc.melisim.public.users`          | public.users         | PostgreSQL   |
| `cdc.melisim.public.products`       | public.products      | PostgreSQL   |
| `cdc.melisim.public.orders`         | public.orders        | PostgreSQL   |

Em instâncias Melisim com um único banco `melisim`, ajuste `MELISIM_POSTGRES_TABLES` no `.env` e o conector em `infra/debezium/connectors/`.

## Saída Bronze

```
s3a://bronze/cdc/users/event_date=YYYY-MM-DD/
s3a://bronze/cdc/products/event_date=YYYY-MM-DD/
s3a://bronze/cdc/orders/event_date=YYYY-MM-DD/
```

## Como rodar

```bash
spark-submit \
  ingestion/cdc_consumer/src/cdc_streaming_job.py \
  --tables users products orders \
  --trigger-seconds 30
```

## Campos no Bronze

| Campo           | Tipo      | Descrição                     |
|-----------------|-----------|-------------------------------|
| `record_key`    | string    | Chave da mensagem Kafka        |
| `raw_json`      | string    | Envelope Debezium completo     |
| `cdc_op`        | string    | Operação: c=create, u=update, d=delete, r=read |
| `cdc_ts_ms`     | string    | Timestamp do evento no banco   |
| `payload_after` | string    | Estado após a operação (JSON)  |
| `payload_before`| string    | Estado antes da operação (JSON)|
| `kafka_timestamp`| timestamp| Timestamp de chegada no Kafka  |
| `event_date`    | date      | Partição por data              |
