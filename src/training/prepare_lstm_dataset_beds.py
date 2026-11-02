"""
Step 9: prepare a normalized windowed dataset for the LSTM baseline
(and later, the STGAT model).

Unlike the naive/ARIMA baselines, a shared-weight neural network
needs every hospital on a comparable scale, otherwise large hospitals
(80+ ICU patients) dominate the loss and the model effectively
ignores small hospitals (1-2 ICU patients).

Each hospital is z-score normalized using ONLY its own training-period
mean and std (never val/test, that would leak information). Per-hospital
stats are saved alongside the windows so predictions can be converted
back to real ICU-bed-count units before computing metrics, this is
what keeps the comparison fair against the naive and ARIMA baselines,
which operate directly in real units.
"""

import numpy as np
import pandas as pd
import pickle

PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"
TARGET_COL = "inpatient_beds_used_7_day_avg"
LOOKBACK_WEEKS = 8
HORIZON_WEEKS = 1

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15


def get_split_weeks(all_weeks):
    n = len(all_weeks)
    train_end = int(n * TRAIN_FRAC)
    val_end = int(n * (TRAIN_FRAC + VAL_FRAC))
    return all_weeks[:train_end], all_weeks[train_end:val_end], all_weeks[val_end:]


def main():
    df = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])
    all_weeks = sorted(df["collection_week"].unique())
    train_weeks, val_weeks, test_weeks = get_split_weeks(all_weeks)

    hospital_ids = df["hospital_pk"].unique()
    print(f"Computing per-hospital normalization stats (train period only)...")

    hospital_stats = {}
    for hospital_id in hospital_ids:
        series = df[df["hospital_pk"] == hospital_id]
        train_vals = series[series["collection_week"].isin(train_weeks)][TARGET_COL].dropna()
        mean = train_vals.mean()
        std = train_vals.std()
        if std == 0 or np.isnan(std):
            std = 1.0  # avoid divide-by-zero for near-constant hospitals
        hospital_stats[hospital_id] = {"mean": mean, "std": std}

    print("Building normalized windows...")
    X, y, hospital_id_list, target_weeks_list = [], [], [], []

    for hospital_id in hospital_ids:
        stats = hospital_stats[hospital_id]
        series = (
            df[df["hospital_pk"] == hospital_id]
            .sort_values("collection_week")[["collection_week", TARGET_COL]]
            .reset_index(drop=True)
        )
        raw_values = series[TARGET_COL].values
        norm_values = (raw_values - stats["mean"]) / stats["std"]
        weeks = series["collection_week"].values

        for i in range(len(norm_values) - LOOKBACK_WEEKS - HORIZON_WEEKS + 1):
            window_x = norm_values[i : i + LOOKBACK_WEEKS]
            window_y = norm_values[i + LOOKBACK_WEEKS : i + LOOKBACK_WEEKS + HORIZON_WEEKS]
            if np.isnan(window_x).any() or np.isnan(window_y).any():
                continue
            X.append(window_x)
            y.append(window_y[0])
            hospital_id_list.append(hospital_id)
            target_weeks_list.append(weeks[i + LOOKBACK_WEEKS])

    X = np.array(X)
    y = np.array(y)
    hospital_id_arr = np.array(hospital_id_list)
    target_weeks_arr = np.array(target_weeks_list)

    train_mask = np.isin(target_weeks_arr, train_weeks)
    val_mask = np.isin(target_weeks_arr, val_weeks)
    test_mask = np.isin(target_weeks_arr, test_weeks)

    print(f"\nTotal windows: {len(X)}")
    print(f"Train: {train_mask.sum()}  Val: {val_mask.sum()}  Test: {test_mask.sum()}")

    np.savez(
        "data/processed/lstm_windowed_dataset_beds.npz",
        X_train=X[train_mask], y_train=y[train_mask], hid_train=hospital_id_arr[train_mask],
        X_val=X[val_mask], y_val=y[val_mask], hid_val=hospital_id_arr[val_mask],
        X_test=X[test_mask], y_test=y[test_mask], hid_test=hospital_id_arr[test_mask],
    )
    with open("data/processed/hospital_norm_stats_beds.pkl", "wb") as f:
        pickle.dump(hospital_stats, f)

    print("\nSaved:")
    print("  data/processed/lstm_windowed_dataset_beds.npz")
    print("  data/processed/hospital_norm_stats_beds.pkl  (for converting predictions back to real units)")


if __name__ == "__main__":
    main()
