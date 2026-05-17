"""GRU4Rec — Dataset e DataLoader para sequências de sessões."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

PAD_IDX: Final[int] = 0


class SessionDataset(Dataset):
    """Dataset de sequências de itens por sessão.

    Cada item retornado é (session_input, target, length):
    - session_input: sequência sem o último item (padding com 0)
    - target: último item da sessão
    - length: comprimento real da sequência de input
    """

    def __init__(
        self,
        sequences: list[list[int]],
        max_len: int = 50,
    ) -> None:
        """Inicializa dataset.

        Args:
            sequences: Lista de sequências de IDs de itens por sessão.
            max_len: Comprimento máximo da sequência (trunca à direita).
        """
        self.sequences = sequences
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int, int]:
        seq = self.sequences[idx][-self.max_len:]
        if len(seq) < 2:
            seq = [PAD_IDX, seq[-1]] if seq else [PAD_IDX, PAD_IDX]

        input_seq = seq[:-1]
        target = seq[-1]
        length = len(input_seq)

        padded = input_seq + [PAD_IDX] * (self.max_len - length)
        return torch.tensor(padded[:self.max_len], dtype=torch.long), target, length


def collate_fn(
    batch: list[tuple[torch.Tensor, int, int]],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Agrupa amostras em batch.

    Args:
        batch: Lista de (input_tensor, target, length).

    Returns:
        Tupla (sessions, targets, lengths).
    """
    sessions = torch.stack([b[0] for b in batch])
    targets = torch.tensor([b[1] for b in batch], dtype=torch.long)
    lengths = torch.tensor([b[2] for b in batch], dtype=torch.long)
    return sessions, targets, lengths


def build_item_index(sequences: list[list[int]]) -> dict[int, int]:
    """Constrói mapeamento item_id → índice sequencial.

    Args:
        sequences: Sequências de IDs de itens.

    Returns:
        Dict {item_id: index}, começando em 1 (0 = padding).
    """
    all_items: set[int] = set()
    for seq in sequences:
        all_items.update(seq)
    return {item: idx + 1 for idx, item in enumerate(sorted(all_items))}
