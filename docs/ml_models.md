# ML Models — MeliSimLake

## Visão Geral

| Modelo | Tipo | Framework | Métrica Principal | Target |
|--------|------|-----------|-------------------|--------|
| ALS Recommender | Collaborative Filtering | Implicit 0.7 | Recall@20 | Recomendação user-based |
| GRU4Rec | Sequential Rec | PyTorch 2.3 | Recall@20, MRR@20 | Próximo item na sessão |
| SASRec | Sequential Rec (Transformer) | PyTorch 2.3 | Recall@20, MRR@20 | Alternativa ao GRU4Rec |
| Churn XGBoost | Classificação Binária | XGBoost 2.x | AUC-ROC, F1 | P(churn em 60 dias) |
| Fraud XGBoost | Classificação Binária | XGBoost 2.x + Isolation Forest | AUC, Precision@top1% | P(fraude na transação) |
| Demand LSTM | Previsão de Série Temporal | PyTorch 2.3 | WAPE | Demanda por categoria 7/14d |

---

## ALS Recommender (`ml/recommendation_als/`)

**Algoritmo**: Alternating Least Squares (Collaborative Filtering implícito)

**Hiperparâmetros**:
- `factors=128` — dimensão dos embeddings de usuário/item
- `regularization=0.01` — penalidade L2
- `iterations=50` — rodadas de otimização ALS
- `alpha=40` — peso de confiança para feedback implícito

**Pipeline de treinamento**:
1. Lê interações Gold (`fact_orders` + `fact_sessions`) via Trino
2. Constrói matriz esparsa `user × item` com frequência ponderada
3. Treina modelo Implicit ALS
4. Avalia Recall@K, NDCG@K, MRR@K para K∈{10,20,50}
5. Loga artefatos e métricas no MLflow
6. Registra modelo em Production se AUC melhorou

**Serving**: `GET /recommend/user/{user_id}?n=10`

---

## GRU4Rec (`ml/recommendation_gru4rec/`)

**Arquitetura**:
```
item_embedding(vocab_size, hidden_size, padding_idx=0)
  → GRU(hidden_size, hidden_size, n_layers, batch_first=True)
  → Linear(hidden_size, vocab_size)
```

**Treinamento**:
- Loss: CrossEntropyLoss (last-item prediction)
- Optimizer: Adam (lr=1e-3)
- Scheduler: ReduceLROnPlateau (patience=3, factor=0.5)
- Gradient clipping: max_norm=5.0
- Early stopping: patience=5 épocas sem melhora em Recall@20

**Dados**: sessões com `sequence_length >= 2` da `gold.ml_session_features`

**Serving**: `POST /recommend/session` com `session_items: list[str]`

---

## SASRec (`ml/recommendation_sasrec/`)

**Arquitetura**:
```
item_embedding + positional_embedding
  → TransformerEncoderLayer × n_blocks (norm_first=True, causal mask)
  → Seleciona última posição válida
  → Linear(hidden_size, vocab_size)
```

**Diferencial vs GRU4Rec**: atenção causal captura dependências de longa distância na sessão.

**Serving**: mesmo endpoint `/recommend/session` (selecionável por parâmetro `model`).

---

## Churn XGBoost (`ml/churn_xgboost/`)

**Features** (via Feast `user_churn_features`):
- `recency_days`, `frequency_30d`, `frequency_90d`
- `monetary_30d`, `monetary_90d`, `avg_order_value`
- `days_since_account_creation`, `support_tickets_last_90d`
- `return_rate`, `recency_ratio`

**Pipeline**:
1. Optuna — 50 trials, objective = maximize AUC-ROC
2. Parâmetros buscados: `max_depth`, `n_estimators`, `learning_rate`, `subsample`, `colsample_bytree`, `min_child_weight`
3. `CalibratedClassifierCV` (cv=5, method='isotonic') para calibração de probabilidades
4. SHAP TreeExplainer — gera gráfico de feature importance como artefato MLflow

**Serving**: `POST /predict/churn/{user_id}` → retorna `churn_probability` ∈ [0,1]

---

## Fraud Detection (`ml/fraud_detection/`)

**Pipeline em duas etapas**:

**Etapa 1 — Isolation Forest** (detecção de anomalias):
- `n_estimators=200`, `contamination=0.05`
- StandardScaler pré-processamento
- Score de anomalia como feature adicional

**Etapa 2 — XGBoost Classifier**:
- `scale_pos_weight=19` (ratio negativo/positivo ≈ 95/5%)
- Features: `total_amount`, `items_count`, `hour_of_day`, `days_since_account_creation`, `orders_in_last_hour`, `avg_order_value_deviation`, `isolation_score`

**Métricas**: AUC-ROC + Precision@top1% (mais relevante para fraude)

**Serving**: `POST /predict/fraud` com features da transação

---

## Demand LSTM (`ml/demand_forecast_lstm/`)

**Arquitetura**:
```
LSTM(input_size, hidden_size, num_layers)
  → Linear(hidden_size, 64) → ReLU → Dropout(0.2)
  → Linear(64, horizon_days)
```

**Treinamento**:
- Sliding windows com `window_size=30` dias de histórico
- `horizon=7` ou `14` dias de previsão
- Walk-forward validation (5 folds)
- Loss: HuberLoss (robusta a outliers)
- Gradient clipping: max_norm=1.0

**Métrica**: WAPE = Σ|y - ŷ| / Σ|y| × 100%

**Serving**: `POST /forecast/demand/{category}?horizon_days=7`

---

## MLflow Registry

Todos os modelos são versionados no MLflow Registry com stages:
- **Staging**: recém treinado, aguardando validação
- **Production**: modelo ativo para serving
- **Archived**: versões anteriores de Production

Promoção automática: se nova versão supera `min_delta=0.01` na métrica principal.
