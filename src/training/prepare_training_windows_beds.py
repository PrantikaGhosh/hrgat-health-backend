"""
Step 8: shared training data preparation.

Defines the chronological train/val/test split and the sliding-window
sample construction used by every model in this project (baselines
and the STGAT model alike), so all models are evaluated on identical
splits and identical windows. This is what makes the final comparison
fair.

This script is a diagnostic run: it builds the windows and reports
counts, it does not train anything yet.
"""

import numpy as np
import pandas as pd

PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"

TARGET_COL = "inpatient_beds_used_7_day_avg"
LOOKBACK_WEEKS = 8
HORIZON_WEEKS = 1

TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
# remaining ~0.15 goes to test


def get_split_weeks(all_weeks):
    n = len(all_weeks)
    train_end = int(n * TRAIN_FRAC)
    val_end = int(n * (TRAIN_FRAC + VAL_FRAC))
    return all_weeks[:train_end], all_weeks[train_end:val_end], all_weeks[val_end:]


def build_windows(df, hospital_ids, target_col=TARGET_COL, lookback=LOOKBACK_WEEKS, horizon=HORIZON_WEEKS):
    """
    For each hospital, slide an (lookback -> horizon) window across its
    time series. Returns X (n_samples, lookback), y (n_samples,),
    and metadata (hospital_pk, target_week) per sample.
    Windows containing any NaN in input or target are dropped.
    """
    X, y, meta = [], [], []
    for hospital_id in hospital_ids:
        series = (
            df[df["hospital_pk"] == hospital_id]
            .sort_values("collection_week")[["collection_week", target_col]]
            .reset_index(drop=True)
        )
        values = series[target_col].values
        weeks = series["collection_week"].values

        for i in range(len(values) - lookback - horizon + 1):
            window_x = values[i : i + lookback]
            window_y = values[i + lookback : i + lookback + horizon]
            if np.isnan(window_x).any() or np.isnan(window_y).any():
                continue
            X.append(window_x)
            y.append(window_y[0])  # horizon=1 for now
            meta.append((hospital_id, weeks[i + lookback]))

    return np.array(X), np.array(y), meta


def main():
    df = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])

    all_weeks = sorted(df["collection_week"].unique())
    train_weeks, val_weeks, test_weeks = get_split_weeks(all_weeks)

    print("=" * 60)
    print("Chronological split")
    print("=" * 60)
    print(f"Train: {train_weeks[0]} to {train_weeks[-1]}  ({len(train_weeks)} weeks)")
    print(f"Val:   {val_weeks[0]} to {val_weeks[-1]}  ({len(val_weeks)} weeks)")
    print(f"Test:  {test_weeks[0]} to {test_weeks[-1]}  ({len(test_weeks)} weeks)")

    hospital_ids = df["hospital_pk"].unique()
    print(f"\nBuilding windows for {len(hospital_ids)} hospitals "
          f"(lookback={LOOKBACK_WEEKS}, horizon={HORIZON_WEEKS})...")

    X_all, y_all, meta_all = build_windows(df, hospital_ids)
    print(f"Total valid windows across all hospitals: {len(X_all)}")

    # Split windows by the date of their TARGET week
    target_weeks = np.array([m[1] for m in meta_all])
    train_mask = np.isin(target_weeks, train_weeks)
    val_mask = np.isin(target_weeks, val_weeks)
    test_mask = np.isin(target_weeks, test_weeks)

    print("\n" + "=" * 60)
    print("Sample counts per split")
    print("=" * 60)
    print(f"Train windows: {train_mask.sum()}")
    print(f"Val windows:   {val_mask.sum()}")
    print(f"Test windows:  {test_mask.sum()}")

    print(f"\nTarget variable: {TARGET_COL}")
    print(f"Target stats (train): mean={y_all[train_mask].mean():.2f}, "
          f"std={y_all[train_mask].std():.2f}")

    # Save as .npz for reuse by baseline and model training scripts
    np.savez(
        "data/processed/windowed_dataset_beds.npz",
        X_train=X_all[train_mask], y_train=y_all[train_mask],
        X_val=X_all[val_mask], y_val=y_all[val_mask],
        X_test=X_all[test_mask], y_test=y_all[test_mask],
    )
    print("\nSaved windowed dataset to data/processed/windowed_dataset_beds.npz")


if __name__ == "__main__":
    main()
