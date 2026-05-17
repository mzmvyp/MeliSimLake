# transformation/great_expectations

Suítes de qualidade de dados com Great Expectations 1.x para Bronze, Silver e Gold.

## Estrutura

```
great_expectations/
├── expectations/
│   ├── bronze_users.json
│   ├── bronze_events.json
│   ├── silver_users.json
│   ├── silver_orders.json
│   └── gold_fact_orders.json
├── checkpoints/
│   ├── bronze_checkpoint.yml
│   └── silver_checkpoint.yml
└── great_expectations.yml
```

## Como rodar

```bash
cd transformation/great_expectations
great_expectations checkpoint run bronze_checkpoint
great_expectations docs build
```

## DataDocs

Os DataDocs são publicados em `s3://great-expectations/datadocs/` e acessíveis via MinIO.
