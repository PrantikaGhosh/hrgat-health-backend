"""
Baseline 2: shared-weight LSTM.

One LSTM trained across all 369 hospitals' windows pooled together
(each hospital contributes many training windows, but there's a
single set of model weights). This is still the "existing approach"
from our diagram, each prediction only sees that one hospital's own
8-week history, no cross-hospital information, that's exactly what
your STGAT model will add on top of this.

Trains with early stopping on validation loss, then evaluates on
the test set in real (denormalized) units for a fair comparison
against the naive and ARIMA baselines.
"""

import pickle
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from metrics import report_metrics

DATA_PATH = "data/processed/lstm_windowed_dataset_beds.npz"
STATS_PATH = "data/processed/hospital_norm_stats_beds.pkl"
MODEL_SAVE_PATH = "saved_models/lstm_baseline_beds.pt"

HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.2
BATCH_SIZE = 256
MAX_EPOCHS = 80
PATIENCE = 15
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 1e-5
GRAD_CLIP_NORM = 1.0


class LSTMBaseline(nn.Module):
    def __init__(self, hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS, dropout=DROPOUT):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        # x shape: (batch, seq_len) -> add feature dim -> (batch, seq_len, 1)
        x = x.unsqueeze(-1)
        _, (h_n, _) = self.lstm(x)
        out = self.fc(self.dropout(h_n[-1]))  # last layer's hidden state
        return out.squeeze(-1)


def denormalize(values, hospital_ids, stats):
    means = np.array([stats[h]["mean"] for h in hospital_ids])
    stds = np.array([stats[h]["std"] for h in hospital_ids])
    return values * stds + means


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")

    data = np.load(DATA_PATH, allow_pickle=True)
    with open(STATS_PATH, "rb") as f:
        stats = pickle.load(f)

    X_train = torch.tensor(data["X_train"], dtype=torch.float32)
    y_train = torch.tensor(data["y_train"], dtype=torch.float32)
    X_val = torch.tensor(data["X_val"], dtype=torch.float32)
    y_val = torch.tensor(data["y_val"], dtype=torch.float32)
    X_test = torch.tensor(data["X_test"], dtype=torch.float32)
    y_test = torch.tensor(data["y_test"], dtype=torch.float32)

    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=BATCH_SIZE, shuffle=True)

    model = LSTMBaseline().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    epochs_without_improvement = 0

    print("\nTraining...")
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP_NORM)
            optimizer.step()

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val.to(device))
            val_loss = loss_fn(val_pred, y_val.to(device)).item()

        print(f"  epoch {epoch:2d}   val_loss={val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= PATIENCE:
                print(f"Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
                break

    print(f"\nBest model saved to {MODEL_SAVE_PATH}")

    # Load best checkpoint and evaluate in real units
    model.load_state_dict(torch.load(MODEL_SAVE_PATH))
    model.eval()
    with torch.no_grad():
        val_pred_norm = model(X_val.to(device)).cpu().numpy()
        test_pred_norm = model(X_test.to(device)).cpu().numpy()

    val_pred_real = denormalize(val_pred_norm, data["hid_val"], stats)
    val_true_real = denormalize(data["y_val"], data["hid_val"], stats)
    test_pred_real = denormalize(test_pred_norm, data["hid_test"], stats)
    test_true_real = denormalize(data["y_test"], data["hid_test"], stats)

    print("\n" + "=" * 60)
    print("LSTM Beds baseline results (real bed-count units)")
    print("=" * 60)
    report_metrics(val_true_real, val_pred_real, label="LSTM Beds (val)")
    report_metrics(test_true_real, test_pred_real, label="LSTM Beds (test)")


if __name__ == "__main__":
    main()
