# ALS Recommender — MeliSimLake

Recomendação colaborativa com Alternating Least Squares (Implicit 0.7).

## Treinamento

```bash
cd ml/recommendation_als
python -m ml.recommendation_als.src.train
```

## Hiperparâmetros

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `factors` | 128 | Dimensão dos embeddings |
| `regularization` | 0.01 | Penalidade L2 |
| `iterations` | 50 | Rodadas ALS |
| `alpha` | 40 | Peso de confiança para feedback implícito |

## Métricas

Avaliado com K ∈ {10, 20, 50}:
- **Recall@K** — fração dos itens relevantes no top-K
- **NDCG@K** — qualidade do ranking
- **MRR@K** — posição média da primeira recomendação relevante

## Serving

`POST /recommend/user/{user_id}` com body `{"n": 10}`
