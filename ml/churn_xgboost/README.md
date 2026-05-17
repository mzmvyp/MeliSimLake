# Churn Prediction — MeliSimLake

Predição de churn em 60 dias com XGBoost + Optuna + SHAP.

## Treinamento

```bash
python -m ml.churn_xgboost.src.train
```

## Pipeline

1. **Feature extraction** — Feast `user_churn_features` (recency, frequency, monetary, etc.)
2. **Hyperparameter search** — Optuna 50 trials, objetivo: maximize AUC-ROC
3. **Calibração** — CalibratedClassifierCV(cv=5, method='isotonic')
4. **Interpretabilidade** — SHAP TreeExplainer, gráfico logado no MLflow
5. **Registro** — MLflow Registry com promoção automática se AUC melhora >0.01

## Features

| Feature | Tipo | Descrição |
|---------|------|-----------|
| `recency_days` | int | Dias desde última compra |
| `frequency_30d` | int | Pedidos em 30 dias |
| `frequency_90d` | int | Pedidos em 90 dias |
| `monetary_30d` | float | Gasto em 30 dias |
| `monetary_90d` | float | Gasto em 90 dias |
| `avg_order_value` | float | Ticket médio |
| `days_since_account_creation` | int | Idade da conta |
| `support_tickets_last_90d` | int | Tickets de suporte |
| `return_rate` | float | Taxa de devolução |
| `recency_ratio` | float | recency / tenure |

## Serving

`POST /predict/churn/{user_id}` → `{"churn_probability": 0.73, "risk_level": "high"}`
