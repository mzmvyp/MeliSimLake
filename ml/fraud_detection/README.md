# Fraud Detection — MeliSimLake

Detecção de fraude em duas etapas: Isolation Forest + XGBoost.

## Treinamento

```bash
python -m ml.fraud_detection.src.train
```

## Pipeline

**Etapa 1 — Detecção de Anomalia**:
- `IsolationForest(n_estimators=200, contamination=0.05)`
- `StandardScaler` nos features numéricos
- Score de anomalia adicionado como feature para Etapa 2

**Etapa 2 — Classificação**:
- `XGBClassifier(scale_pos_weight=19)` — compensa classes desbalanceadas (5% fraude)
- Métrica principal: **Precision@top1%** (mais relevante para triagem)
- Também reporta: AUC-ROC, F1

## Features da Transação

| Feature | Tipo | Descrição |
|---------|------|-----------|
| `total_amount` | float | Valor da transação |
| `items_count` | int | Número de itens |
| `hour_of_day` | int | Hora local (0-23) |
| `days_since_account_creation` | int | Idade da conta |
| `orders_in_last_hour` | int | Pedidos recentes |
| `avg_order_value_deviation` | float | Desvio vs. histórico |
| `isolation_score` | float | Score Isolation Forest (derivado) |

## Serving

`POST /predict/fraud` com JSON dos features da transação
