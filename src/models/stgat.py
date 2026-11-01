"""
STGAT model: Spatio-Temporal Graph Attention Network for hospital
ICU occupancy forecasting.

Architecture:
  1. A GATConv layer applied independently at each of the LOOKBACK
     weeks, letting each hospital's representation be informed by
     its referral-network neighbors (spatial dependency).
  2. The resulting sequence of per-hospital embeddings is fed into
     a GRU, treating each hospital's own sequence independently
     (temporal dependency).
  3. A final linear layer maps each hospital's summarized state to
     a single next-week ICU occupancy prediction.
"""

import torch
import torch.nn as nn
from torch_geometric.nn import GATConv


class STGAT(nn.Module):
    def __init__(self, gat_hidden=8, gat_heads=1, gru_hidden=8, dropout=0.3):
        super().__init__()
        self.gat = GATConv(
            in_channels=1,
            out_channels=gat_hidden,
            heads=gat_heads,
            concat=False,       # average the heads instead of concatenating, keeps output dim = gat_hidden
            dropout=dropout,
        )
        self.gru = nn.GRU(input_size=gat_hidden, hidden_size=gru_hidden, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(gru_hidden, 1)
        # Start the residual head near-zero, so at initialization the
        # model's prediction is close to plain persistence (last known
        # value), and training only has to learn the correction on top,
        # not rediscover persistence from scratch with 128 examples.
        nn.init.zeros_(self.fc.weight)
        nn.init.zeros_(self.fc.bias)

    def forward(self, x, edge_index):
        """
        x: (lookback, num_nodes) - one graph snapshot window, values only
        edge_index: (2, num_edges) - static referral-network graph structure
        returns: (num_nodes,) - predicted next-week value per hospital
        """
        lookback, num_nodes = x.shape
        spatial_embeddings = []

        for t in range(lookback):
            node_features = x[t].unsqueeze(-1)          # (num_nodes, 1)
            spatial_out = self.gat(node_features, edge_index)  # (num_nodes, gat_hidden)
            spatial_embeddings.append(spatial_out)

        # (num_nodes, lookback, gat_hidden) - GRU treats each node's own
        # sequence independently, num_nodes acts as the GRU's batch dimension
        sequence = torch.stack(spatial_embeddings, dim=1)

        _, h_n = self.gru(sequence)          # h_n: (1, num_nodes, gru_hidden)
        h_n = self.dropout(h_n.squeeze(0))   # (num_nodes, gru_hidden)
        delta = self.fc(h_n).squeeze(-1)     # (num_nodes,) learned correction

        last_known_value = x[-1]             # (num_nodes,) persistence anchor
        return last_known_value + delta
