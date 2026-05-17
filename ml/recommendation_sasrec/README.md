# SASRec — Self-Attentive Sequential Recommendation

Recomendação sequencial com Transformer e atenção causal (comparador do GRU4Rec).

## Treinamento

```bash
python -m ml.recommendation_sasrec.src.train
```

## Arquitetura

```
item_embedding(vocab_size, hidden_size) + positional_embedding(max_len, hidden_size)
  → TransformerEncoderLayer × n_blocks
     (norm_first=True, batch_first=True, causal mask upper-triangular)
  → Seleciona última posição válida via lengths
  → Linear(hidden_size, vocab_size)
```

## Diferencial vs GRU4Rec

| Aspecto | GRU4Rec | SASRec |
|---------|---------|--------|
| Mecanismo | GRU recorrente | Self-attention |
| Dependências longas | Limitado | Capturas diretamente |
| Paralelismo no treino | Sequencial | Paralelo |
| Interpretabilidade | Baixa | Média (attention weights) |
| Velocidade de inferência | Mais rápido | Ligeiramente mais lento |

## Máscara Causal

`torch.triu(torch.full((L, L), float('-inf')), diagonal=1)` garante que posição `i` só atende posições `j <= i`.

## Serving

Mesmo endpoint `/recommend/session` — modelo selecionável via parâmetro.
