"""GRU4Rec — modelo de recomendação session-based com GRU."""

from __future__ import annotations

import torch
from torch import nn


class GRU4Rec(nn.Module):
    """GRU4Rec: recomendação baseada em sessão via Gated Recurrent Unit.

    Referência: Hidasi et al. (2016) "Session-based Recommendations with
    Recurrent Neural Networks".
    """

    def __init__(
        self,
        n_items: int,
        embedding_dim: int = 128,
        hidden_dim: int = 256,
        n_layers: int = 1,
        dropout: float = 0.25,
    ) -> None:
        """Inicializa GRU4Rec.

        Args:
            n_items: Tamanho do vocabulário de itens.
            embedding_dim: Dimensão dos embeddings de itens.
            hidden_dim: Dimensão do estado oculto GRU.
            n_layers: Número de camadas GRU.
            dropout: Taxa de dropout (aplicado apenas se n_layers > 1).
        """
        super().__init__()
        self.n_items = n_items
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim

        self.item_embedding = nn.Embedding(n_items + 1, embedding_dim, padding_idx=0)
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.output = nn.Linear(hidden_dim, n_items + 1)
        self.dropout = nn.Dropout(dropout)
        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.xavier_uniform_(self.item_embedding.weight)
        nn.init.xavier_uniform_(self.output.weight)

    def forward(
        self,
        sessions: torch.Tensor,
        lengths: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            sessions: Tensor (batch, max_seq_len) com IDs de itens.
            lengths: Tensor (batch,) com comprimentos reais das sessões.

        Returns:
            Logits (batch, n_items + 1) para o próximo item.
        """
        embedded = self.dropout(self.item_embedding(sessions))
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded,
            lengths.cpu(),
            batch_first=True,
            enforce_sorted=False,
        )
        _, h_n = self.gru(packed)
        last_hidden = self.dropout(h_n[-1])
        return self.output(last_hidden)
