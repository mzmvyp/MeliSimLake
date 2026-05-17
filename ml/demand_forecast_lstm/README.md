# Demand Forecast LSTM — MeliSimLake

Previsão de demanda por categoria com LSTM multi-step (horizon 7 ou 14 dias).

## Treinamento

```bash
python -m ml.demand_forecast_lstm.src.train
```

## Arquitetura

```
LSTM(input_size=1, hidden_size=64, num_layers=2, batch_first=True)
  → Linear(64, 64) → ReLU → Dropout(0.2)
  → Linear(64, horizon_days)
```

## Dados

- Fonte: `gold.fact_orders` agregado por categoria e dia
- Geração sintética disponível via `use_synthetic=True` (trend + weekly + monthly seasonality + noise)
- Sliding windows: `window_size=30` dias de histórico → `horizon=7` dias de previsão

## Treinamento

- Loss: `HuberLoss` (robusta a outliers de vendas)
- Optimizer: Adam (lr=1e-3)
- Gradient clipping: `max_norm=1.0`
- Walk-forward validation (5 folds) para avaliação realista

## Métricas

**WAPE** (Weighted Absolute Percentage Error):
```
WAPE = Σ|y - ŷ| / Σ|y| × 100%
```
Target: WAPE < 20%

## Serving

```
POST /forecast/demand/{category}
{"horizon_days": 7}
```

Retorna `forecast[]` (valores) e `dates[]` (datas no formato YYYY-MM-DD).
