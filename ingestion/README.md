# ingestion

Módulo de ingestão de dados para a camada Bronze do MeliSimLake.

## Submódulos

| Submódulo               | Fonte              | Destino            | Tipo       |
|-------------------------|--------------------|--------------------|------------|
| `cdc_consumer`          | Kafka (Debezium)   | Bronze CDC         | Streaming  |
| `kafka_events_consumer` | Kafka (eventos)    | Bronze Events      | Streaming  |
| `batch_csv_loader`      | S3 landing zone    | Bronze CSV         | Batch      |
| `api_fetcher`           | APIs externas      | Bronze API         | Batch/hora |
| `web_scraper`           | Web (Playwright)   | Bronze Scraper     | Batch      |

## Dependências

```
pyspark==3.5.1
delta-spark==3.2.x
kafka-python==2.0.x
confluent-kafka==2.5.x
httpx==0.27.x
tenacity==9.x
playwright==1.47.x
pandera==0.20.x
loguru==0.7.x
pydantic-settings==2.4.x
```

## Como rodar

```bash
# CDC consumer (Spark Structured Streaming)
spark-submit ingestion/cdc_consumer/src/cdc_streaming_job.py \
  --table users --checkpoint s3a://checkpoints/cdc/users/

# Kafka events consumer
spark-submit ingestion/kafka_events_consumer/src/events_streaming_job.py

# Batch CSV loader
python -m ingestion.batch_csv_loader.src.csv_loader --date 2026-01-15

# API fetcher
python -m ingestion.api_fetcher.src.fetcher_main

# Web scraper
python -m ingestion.web_scraper.src.scraper_main
```
