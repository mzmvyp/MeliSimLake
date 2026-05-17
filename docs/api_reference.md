# ML API Reference — MeliSimLake

**Base URL**: `http://localhost:8000`  
**Docs interativos**: `http://localhost:8000/docs`  
**Métricas Prometheus**: `http://localhost:8000/metrics`

---

## Sistema

### `GET /health`

Verifica se a API está operacional e lista modelos carregados.

**Response 200**:
```json
{
  "status": "ok",
  "models_loaded": ["als_recommender", "churn_xgboost", "fraud_xgboost", "gru4rec", "demand_lstm"],
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### `GET /models`

Lista todos os modelos registrados com versão e stage MLflow.

**Response 200**:
```json
{
  "models": [
    {"name": "als_recommender", "version": "3"},
    {"name": "churn_xgboost", "version": "7"}
  ]
}
```

---

## Recomendações

### `POST /recommend/user/{user_id}`

Recomendações personalizadas por usuário via ALS collaborative filtering.

**Path params**: `user_id` — ID do usuário

**Request body**:
```json
{"n": 10}
```

| Campo | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `n` | int | 10 | Número de recomendações (1-100) |

**Response 200**:
```json
{
  "user_id": "user123",
  "recommendations": ["prod_1", "prod_2", "prod_3"],
  "scores": [0.95, 0.87, 0.81],
  "model_version": "3",
  "inference_ms": 12.4,
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### `POST /recommend/session`

Recomendações em tempo real baseadas nos itens da sessão atual via GRU4Rec.

**Request body**:
```json
{
  "session_items": ["prod_101", "prod_205", "prod_88"],
  "n": 5
}
```

| Campo | Tipo | Validação | Descrição |
|-------|------|-----------|-----------|
| `session_items` | list[str] | min_length=1 | Itens vistos na sessão (ordem importa) |
| `n` | int | 1-100 | Número de recomendações |

**Response 200**:
```json
{
  "session_items": ["prod_101", "prod_205", "prod_88"],
  "recommendations": ["prod_10", "prod_55", "prod_42", "prod_7", "prod_99"],
  "model_version": "2",
  "inference_ms": 8.1,
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Predições

### `POST /predict/churn/{user_id}`

Probabilidade de churn nos próximos 60 dias.

**Path params**: `user_id` — ID do usuário

**Response 200**:
```json
{
  "user_id": "user123",
  "churn_probability": 0.73,
  "risk_level": "high",
  "model_version": "7",
  "inference_ms": 5.2,
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

`risk_level`: `low` (<0.3), `medium` (0.3-0.6), `high` (>0.6)

---

### `POST /predict/fraud`

Score de fraude para uma transação.

**Request body**:
```json
{
  "total_amount": 1500.00,
  "items_count": 3,
  "hour_of_day": 2,
  "days_since_account_creation": 5,
  "orders_in_last_hour": 4,
  "avg_order_value_deviation": 5.2
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `total_amount` | float | Valor total da transação |
| `items_count` | int | Número de itens |
| `hour_of_day` | int (0-23) | Hora local da transação |
| `days_since_account_creation` | int | Idade da conta em dias |
| `orders_in_last_hour` | int | Pedidos recentes da conta |
| `avg_order_value_deviation` | float | Desvio em relação ao AOV histórico |

**Response 200**:
```json
{
  "fraud_probability": 0.91,
  "is_suspicious": true,
  "model_version": "4",
  "inference_ms": 3.8,
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Previsão de Demanda

### `POST /forecast/demand/{category}`

Previsão de demanda por categoria via LSTM.

**Path params**: `category` — slug da categoria (ex: `eletronicos`, `moda`)

**Request body**:
```json
{"horizon_days": 7}
```

| Campo | Tipo | Validação | Descrição |
|-------|------|-----------|-----------|
| `horizon_days` | int | 1-30 | Horizonte de previsão em dias |

**Response 200**:
```json
{
  "category": "eletronicos",
  "forecast": [1250.5, 1320.1, 980.3, 1100.0, 1450.7, 1380.2, 1290.8],
  "dates": ["2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19", "2024-01-20", "2024-01-21", "2024-01-22"],
  "horizon_days": 7,
  "model_version": "2",
  "inference_ms": 15.6,
  "request_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Rate Limiting

Todos os endpoints estão sujeitos a rate limiting via `slowapi`:
- **Padrão**: 100 req/min por IP
- **Predições**: 200 req/min por IP
- Resposta ao exceder: HTTP 429 com header `Retry-After`

## Headers de Resposta

| Header | Descrição |
|--------|-----------|
| `X-Request-ID` | UUID único da requisição |
| `X-Model-Version` | Versão do modelo usado |
| `X-Inference-Ms` | Tempo de inferência em ms |
