"""Arquiteturas PyTorch espelhadas dos trainers para load via state_dict."""
from __future__ import annotations

import torch
from torch import nn


class DemandLSTM(nn.Module):
    """Mesma arquitetura usada em ml/trainer/src/train_demand_forecast.py."""

    def __init__(self, n_features: int = 2, hidden: int = 32) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden, batch_first=True)
        self.head = nn.Linear(hidden, n_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])
