# ingestion/api_fetcher

Coleta dados de APIs externas com retry exponencial e persiste em Bronze.

## APIs coletadas

| API             | URL                                         | Frequência |
|-----------------|---------------------------------------------|------------|
| Exchange Rates  | open.er-api.com/v6/latest/USD               | Diária     |
| ViaCEP          | viacep.com.br/ws/{cep}/json/                | Sob demanda|

## Saída Bronze

```
s3a://bronze/api/exchange_rates/event_date=YYYY-MM-DD/
s3a://bronze/api/viacep/event_date=YYYY-MM-DD/
```
