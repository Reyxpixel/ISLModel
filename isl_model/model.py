import torch
from torch import nn


class SignBiLSTM(nn.Module):
    """Two-layer bidirectional LSTM over the frame features, then a linear classifier."""

    def __init__(self, n_features, n_classes, hidden=128, layers=2, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=layers, batch_first=True,
                            bidirectional=True, dropout=dropout)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(4 * hidden, n_classes))

    def forward(self, x):                       # x: (batch, frames, features)
        out, _ = self.lstm(x)                   # (batch, frames, 2 * hidden)
        pooled = torch.cat([out.mean(dim=1), out.max(dim=1).values], dim=1)
        return self.head(pooled)
