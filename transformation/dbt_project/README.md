# transformation/dbt_project

Modelagem dimensional Kimball via dbt — Silver → Gold.

## Como rodar

```bash
cd transformation/dbt_project
dbt deps                    # instala pacotes (dbt_utils)
dbt debug                   # valida conexão com Trino
dbt build                   # roda todos os modelos + testes
dbt test                    # só testes
dbt docs generate && dbt docs serve  # documentação com lineage
```

## Modelos

| Modelo                      | Tipo      | Descrição                          |
|-----------------------------|-----------|-------------------------------------|
| `stg_users`                 | view      | Usuários correntes da Silver        |
| `stg_products`              | view      | Produtos correntes da Silver        |
| `stg_orders`                | view      | Pedidos da Silver                   |
| `stg_events`                | view      | Eventos comportamentais da Silver   |
| `dim_users`                 | table     | Dimensão usuários (surrogate key)   |
| `dim_products`              | table     | Dimensão produtos                   |
| `dim_date`                  | table     | Calendário 2020-2030 com flags BR   |
| `fact_orders`               | table     | Fato pedidos                        |
| `fact_events`               | table     | Fato eventos                        |
| `fact_sessions`             | table     | Fato sessões (sessionização 30min)  |
| `customer_rfm`              | table     | RFM por usuário                     |
| `product_metrics_daily`     | table     | Métricas diárias por produto        |
| `churn_features`            | table     | Features + label de churn           |
| `ml_user_features`          | table     | Features usuário para Feast         |
| `ml_product_features`       | table     | Features produto para Feast         |
| `ml_session_features`       | table     | Sequências para GRU4Rec             |
