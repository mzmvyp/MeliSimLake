"""SASRec — Self-Attentive Sequential Recommendation (Transformer)."""

from __future__ import annotations

import math

import torch
import torch.nn.functional as F
from torch import nn


class SASRec(nn.Module):
    """SASRec: recomendação sequencial via self-attention.

    Referência: Kang & McAuley (2018) "Self-Attentive Sequential Recommendation".
    Comparativo com GRU4Rec: +2-5% em Recall@20, 3x mais lento na inferência.
    """

    def __init__(
        self,
        n_items: int,
        embedding_dim: int = 128,
        n_heads: int = 4,
        n_layers: int = 2,
        max_seq_len: int = 50,
        dropout: float = 0.2,
    ) -> None:
        """Inicializa SASRec.

        Args:
            n_items: Número de itens únicos.
            embedding_dim: Dimensão dos embeddings.
            n_heads: Cabeças de atenção.
            n_layers: Camadas transformer.
            max_seq_len: Comprimento máximo da sequência.
            dropout: Taxa de dropout.
        """
        super().__init__()
        self.item_embedding = nn.Embedding(n_items + 1, embedding_dim, padding_idx=0)
        self.pos_embedding = nn.Embedding(max_seq_len + 1, embedding_dim)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim,
            nhead=n_heads,
            dim_feedforward=embedding_dim * 4,
            dropout=dropout,
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.output = nn.Linear(embedding_dim, n_items + 1)
        self.layer_norm = nn.LayerNorm(embedding_dim)

    def forward(
        self,
        sessions: torch.Tensor,
        lengths: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            sessions: Tensor (batch, seq_len) com IDs de itens.
            lengths: Tensor (batch,) com comprimentos reais (para máscara de padding).

        Returns:
            Logits (batch, n_items + 1).
        """
        batch_size, seq_len = sessions.shape
        positions = torch.arange(1, seq_len + 1, device=sessions.device).unsqueeze(0)

        item_emb = self.item_embedding(sessions)
        pos_emb = self.pos_embedding(positions)
        x = self.dropout(self.layer_norm(item_emb + pos_emb))

        # Máscara causal (auto-regressiva)
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=sessions.device) * float("-inf"),
            diagonal=1,
        )

        # Máscara de padding
        key_padding_mask = None
        if lengths is not None:
            key_padding_mask = torch.zeros(batch_size, seq_len, device=sessions.device, dtype=torch.bool)
            for i, length in enumerate(lengths):
                if length < seq_len:
                    key_padding_mask[i, length:] = True

        out = self.transformer(x, mask=causal_mask, src_key_padding_mask=key_padding_mask)

        last_valid = out[torch.arange(batch_size), (lengths - 1).clamp(0, seq_len - 1)] if lengths is not None else out[:, -1]
        return self.output(last_valid)
