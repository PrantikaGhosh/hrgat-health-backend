"""
Train and evaluate the STGAT model, the core contribution of this
project, and compare against the naive, ARIMA, and LSTM baselines
already established.

Since we only have 128 training windows (one per week, not one per
hospital, see prepare_stgat_dataset.py for why), we train with a
simple per-window loop rather than heavy batching machinery, this
dataset is small enough that it doesn't need it.
"""

import sys
import pickle
import numpy as np
import torch
import torch.nn as nn

sys.path.append("src/models")
sys.path.append("src/training")
from stgat import STGAT
from metrics import report_metrics

DATA_PATH = "data/processed/stgat_dataset_beds.npz"
STATS_PATH = "data/processed/hospital_norm_stats_beds.pkl"
MODEL_SAVE_PATH = "saved_models/stgat_model_beds.pt"

MAX_EPOCHS = 300
PATIENCE = 25
LEARNING_RATE = 6e-4
WEIGHT_DECAY = 2e-4


def denormalize(values, hospital_order, stats):
    means = np.array([stats[h]["mean"] for h in hospital_order])
    stds = np.array([stats[h]["std"] for h in hospital_order])
    return values * stds + means


def evaluate(model, X, y, edge_index, device):
    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(len(X)):
            x_i = torch.tensor(X[i], dtype=torch.float32).to(device)
            pred = model(x_i, edge_index).cpu().numpy()
            preds.append(pred)
    return np.array(preds)


def main():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")

    data = np.load(DATA_PATH, allow_pickle=True)
    with open(STATS_PATH, "rb") as f:
        stats = pickle.load(f)

    X_train, y_train = data["X_train"], data["y_train"]
    X_val, y_val = data["X_val"], data["y_val"]
    X_test, y_test = data["X_test"], data["y_test"]
    hospital_order = data["hospital_order"]
    edge_index = torch.tensor(data["edge_index"], dtype=torch.long).to(device)

    print(f"Train windows: {len(X_train)}  Val: {len(X_val)}  Test: {len(X_test)}")

    model = STGAT(dropout=0.4).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    epochs_without_improvement = 0

    print("\nTraining...")
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        perm = np.random.permutation(len(X_train))
        total_loss = 0.0

        for i in perm:
            x_i = torch.tensor(X_train[i], dtype=torch.float32).to(device)
            y_i = torch.tensor(y_train[i], dtype=torch.float32).to(device)

            optimizer.zero_grad()
            pred = model(x_i, edge_index)
            loss = loss_fn(pred, y_i)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        avg_train_loss = total_loss / len(X_train)

        # Validation
        model.eval()
        val_losses = []
        with torch.no_grad():
            for i in range(len(X_val)):
                x_i = torch.tensor(X_val[i], dtype=torch.float32).to(device)
                y_i = torch.tensor(y_val[i], dtype=torch.float32).to(device)
                pred = model(x_i, edge_index)
                val_losses.append(loss_fn(pred, y_i).item())
        avg_val_loss = np.mean(val_losses)

        print(f"  epoch {epoch:3d}   train_loss={avg_train_loss:.4f}   val_loss={avg_val_loss:.4f}")

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            epochs_without_improvement = 0
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= PATIENCE:
                print(f"Early stopping at epoch {epoch} (no improvement for {PATIENCE} epochs)")
                break

    print(f"\nBest model saved to {MODEL_SAVE_PATH}")
    model.load_state_dict(torch.load(MODEL_SAVE_PATH))

    val_pred_norm = evaluate(model, X_val, y_val, edge_index, device)
    test_pred_norm = evaluate(model, X_test, y_test, edge_index, device)

    # Denormalize: each window has predictions for all 369 hospitals,
    # flatten everything to real units for metric computation
    val_pred_real = np.array([denormalize(val_pred_norm[i], hospital_order, stats) for i in range(len(val_pred_norm))]).flatten()
    val_true_real = np.array([denormalize(y_val[i], hospital_order, stats) for i in range(len(y_val))]).flatten()
    test_pred_real = np.array([denormalize(test_pred_norm[i], hospital_order, stats) for i in range(len(test_pred_norm))]).flatten()
    test_true_real = np.array([denormalize(y_test[i], hospital_order, stats) for i in range(len(y_test))]).flatten()

    print("\n" + "=" * 60)
    print("STGAT Beds results (real bed-count units)")
    print("=" * 60)
    report_metrics(val_true_real, val_pred_real, label="STGAT Beds (val)")
    report_metrics(test_true_real, test_pred_real, label="STGAT Beds (test)")

    print("\nCompare these numbers against the naive/ARIMA/LSTM results")
    print("you ran earlier for this same target variable.")


if __name__ == "__main__":
    main()
