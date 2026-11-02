"""
Baseline 0: naive persistence model.

Predicts next week's ICU occupancy = this week's ICU occupancy
(the last value in the lookback window). No training involved.

This is the single most important number in the whole project:
every beds model we build must beat this, or it isn't adding value.
"""

import numpy as np
from metrics import report_metrics

DATA_PATH = "data/processed/windowed_dataset_beds.npz"


def main():
    data = np.load(DATA_PATH)

    results = {}
    for split in ["train", "val", "test"]:
        X = data[f"X_{split}"]
        y = data[f"y_{split}"]
        y_pred = X[:, -1]  # last known value in the lookback window
        results[split] = report_metrics(y, y_pred, label=f"Naive Beds ({split})")

    print("\nThis is the bar every beds model must clear.")
    print(f"Test RMSE to beat: {results['test']['rmse']:.3f}")


if __name__ == "__main__":
    main()
