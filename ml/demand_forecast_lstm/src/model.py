"""LSTM Demand Forecast — modelo de previsão de demanda por categoria."""

from __future__ import annotations

import torch
from torch import nn


class DemandForecastLSTM(nn.Module):
    """LSTM para previsão de demanda: lookback 90d → horizonte 14d.

    Domínio apropriado para LSTM: séries temporais de vendas com
    sazonalidade semanal/mensal, onde o modelo supera naive e Prophet
    ao capturar dependências longas (promoções, feriados).
    """

    def __init__(
        self,
        input_size: int = 7,
        hidden_size: int = 128,
        n_layers: int = 2,
        output_size: int = 14,
        dropout: float = 0.2,
    ) -> None:
        """Inicializa o modelo.

        Args:
            input_size: Número de features auxiliares por timestep.
            hidden_size: Dimensão do estado oculto LSTM.
            n_layers: Número de camadas LSTM.
            output_size: Horizonte de previsão em dias.
            dropout: Taxa de dropout.
        """
        super().__init__()
        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor (batch, lookback, input_size) com features temporais.

        Returns:
            Tensor (batch, output_size) com previsões de demanda.
        """
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])
