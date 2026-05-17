# GRU4Rec — Session-Based Recommendation

Recomendação baseada em sessão com GRU (Gated Recurrent Unit) em PyTorch.

## Treinamento

```bash
python -m ml.recommendation_gru4rec.src.train
```

## Arquitetura

```
Embedding(vocab_size, hidden_size, padding_idx=0)
  → GRU(hidden_size, hidden_size, n_layers=1, batch_first=True)
  → Linear(hidden_size, vocab_size)
```

Xavier initialization em todos os parâmetros.

## Dados

- Fonte: `gold.ml_session_features` (sessões com `sequence_length >= 2`)
- Input: sequência de IDs de produtos (exceto último)
- Target: último produto da sequência
- Padding: índice 0, `pack_padded_sequence` para eficiência

## Hiperparâmetros Default

| Parâmetro | Valor |
|-----------|-------|
| `hidden_size` | 128 |
| `n_layers` | 1 |
| `batch_size` | 512 |
| `lr` | 1e-3 |
| `max_epochs` | 50 |
| `patience` | 5 |
| `grad_clip` | 5.0 |

## Métricas

- **Recall@20** (principal)
- **MRR@20** — Mean Reciprocal Rank
- Avaliadas a cada 5 épocas

## Serving

`POST /recommend/session` com `{"session_items": ["p1", "p2", "p3"], "n": 5}`
