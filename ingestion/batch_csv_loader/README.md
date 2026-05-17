# ingestion/batch_csv_loader

Carrega CSVs da landing zone (MinIO `s3a://landing/csv/`) para Bronze (Parquet).

## Tipos suportados

| Tipo        | Schema           | Validação Pandera |
|-------------|------------------|-------------------|
| `catalog`   | LegacyCatalogSchema | sim            |
| `logistics` | LogisticsSchema  | sim               |

## Saída Bronze

```
s3a://bronze/csv/{tipo}/event_date=YYYY-MM-DD/{arquivo}.parquet
```
