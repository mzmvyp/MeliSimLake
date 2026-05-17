# Data Dictionary — MeliSimLake

## Camada Bronze

### `bronze/cdc/users/`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `op` | string | Operação Debezium: `c` (create), `u` (update), `d` (delete), `r` (snapshot) |
| `ts_ms` | long | Timestamp do evento em milissegundos |
| `source_table` | string | Tabela de origem do CDC |
| `payload` | string | JSON com os campos do registro |
| `event_date` | date | Partição por data de ingestão |

### `bronze/cdc/products/`
Mesma estrutura de `bronze/cdc/users/`, fonte: MySQL Debezium connector.

### `bronze/cdc/orders/`
Mesma estrutura de `bronze/cdc/users/`, fonte: PostgreSQL Debezium connector.

### `bronze/events/clicks/`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `event_id` | string | UUID do evento |
| `user_id` | string | ID do usuário (pode ser null para anônimos) |
| `session_id` | string | UUID da sessão |
| `product_id` | string | ID do produto clicado |
| `page_url` | string | URL da página |
| `referrer` | string | URL de referência |
| `device_type` | string | `mobile`, `desktop`, `tablet` |
| `timestamp` | timestamp | Momento do clique |
| `event_date` | date | Partição |

---

## Camada Silver

### `silver/users/` (Delta Lake, SCD Type 2)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | string | Chave de negócio |
| `email` | string | E-mail normalizado (lowercase + trim) |
| `name` | string | Nome completo |
| `gender` | string | `M`, `F`, `NB` |
| `birth_date` | date | Data de nascimento |
| `region` | string | Estado (UF) |
| `income_class` | string | `A`, `B`, `C`, `D` |
| `created_at` | timestamp | Criação na origem |
| `updated_at` | timestamp | Última atualização na origem |
| `valid_from` | timestamp | Início de vigência desta versão (SCD2) |
| `valid_to` | timestamp | Fim de vigência (`9999-12-31` = vigente) |
| `is_current` | boolean | `true` se versão ativa |
| `row_hash` | string | MD5 das colunas de negócio para detecção de mudança |

### `silver/products/` (Delta Lake, SCD Type 2)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `product_id` | string | Chave de negócio |
| `product_name` | string | Nome do produto |
| `category` | string | Categoria principal |
| `subcategory` | string | Subcategoria |
| `price` | decimal(10,2) | Preço vigente |
| `stock_quantity` | int | Estoque disponível |
| `seller_id` | string | ID do vendedor |
| `valid_from` | timestamp | SCD2 início |
| `valid_to` | timestamp | SCD2 fim |
| `is_current` | boolean | Versão ativa |
| `row_hash` | string | Hash de integridade |

### `silver/orders/` (Delta Lake, upsert por `order_id`)
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `order_id` | string | Chave de negócio |
| `user_id` | string | FK para usuários |
| `product_id` | string | FK para produtos |
| `session_id` | string | Sessão que originou o pedido |
| `status` | string | `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`, `refunded` |
| `total_amount` | decimal(10,2) | Valor total do pedido |
| `quantity` | int | Quantidade comprada |
| `payment_method` | string | Método de pagamento |
| `created_at` | timestamp | Criação do pedido |
| `updated_at` | timestamp | Última atualização de status |

---

## Camada Gold (dbt + Trino)

### `gold.dim_users`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_key` | string | Surrogate key (hash SHA1 de user_id) |
| `user_id` | string | Chave de negócio |
| `email` | string | E-mail |
| `name` | string | Nome |
| `gender_label` | string | `Masculino`, `Feminino`, `Não-Binário` |
| `age` | int | Idade calculada (anos completos) |
| `region` | string | Estado |
| `income_class` | string | Classe de renda |
| `created_at` | timestamp | Data de cadastro |

### `gold.dim_products`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `product_key` | string | Surrogate key |
| `product_id` | string | Chave de negócio |
| `product_name` | string | Nome |
| `category` | string | Categoria |
| `subcategory` | string | Subcategoria |
| `price` | decimal | Preço |
| `seller_id` | string | Vendedor |

### `gold.dim_date`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `date_key` | int | YYYYMMDD |
| `date_actual` | date | Data |
| `year` | int | Ano |
| `month` | int | Mês (1-12) |
| `day` | int | Dia do mês |
| `day_of_week` | int | 1=Dom … 7=Sáb |
| `week_of_year` | int | Semana ISO |
| `quarter` | int | Trimestre (1-4) |
| `is_weekend` | boolean | Sábado ou domingo |
| `is_holiday` | boolean | Feriado nacional brasileiro |
| `holiday_name` | string | Nome do feriado (null se não feriado) |
| `is_black_friday` | boolean | Última sexta de novembro |

### `gold.fact_orders`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `order_id` | string | PK |
| `user_key` | string | FK dim_users |
| `product_key` | string | FK dim_products |
| `date_key` | int | FK dim_date |
| `session_id` | string | Sessão de origem |
| `status` | string | Status final |
| `total_amount` | decimal | GMV |
| `quantity` | int | Unidades |
| `payment_method` | string | Pagamento |
| `order_date` | date | Data do pedido |

### `gold.fact_sessions`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `session_id` | string | PK |
| `user_id` | string | FK usuário |
| `started_at` | timestamp | Início da sessão |
| `ended_at` | timestamp | Fim (30min de inatividade) |
| `session_duration_seconds` | int | Duração |
| `product_sequence` | array(string) | Produtos vistos em ordem |
| `sequence_length` | int | Tamanho da sequência |
| `device_type` | string | Dispositivo |
| `converted` | boolean | Resultou em compra |
| `total_value` | decimal | Valor das compras na sessão |

### `gold.customer_rfm`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | string | PK |
| `snapshot_date` | date | Data do snapshot |
| `recency` | int | Dias desde última compra |
| `frequency` | int | Total de pedidos confirmados |
| `monetary` | decimal | Valor total gasto |
| `r_score` | int | NTILE(5) de recência (5=mais recente) |
| `f_score` | int | NTILE(5) de frequência |
| `m_score` | int | NTILE(5) de valor |
| `rfm_segment` | string | Champions, Loyal, At Risk, Lost, etc. |
| `ltv` | decimal | Lifetime Value acumulado |

### `gold.churn_features`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user_id` | string | PK |
| `label_date` | date | Data de referência |
| `recency_days` | int | Dias desde última compra |
| `frequency_30d` | int | Pedidos em 30 dias |
| `frequency_90d` | int | Pedidos em 90 dias |
| `monetary_30d` | decimal | Gasto em 30 dias |
| `monetary_90d` | decimal | Gasto em 90 dias |
| `avg_order_value` | decimal | Ticket médio |
| `days_since_account_creation` | int | Tempo de conta |
| `support_tickets_last_90d` | int | Chamados de suporte |
| `return_rate` | decimal | Taxa de devolução |
| `recency_ratio` | decimal | recency / tenure |
| `churn_label` | int | 1 se não comprou nos próximos 60 dias |
