"""
Baseline 0: naive persistence model — ICU TARGET VERSION.

Predicts next week's ICU occupancy = this week's ICU occupancy.
Permanently ICU-only file. See evaluate_naive_baseline_beds.py for
the general bed occupancy equivalent.
"""

import numpy as np
from metrics import report_metrics

DATA_PATH = "data/processed/windowed_dataset.npz"


def main():
    data = np.load(DATA_PATH)

    results = {}
    for split in ["train", "val", "test"]:
        X = data[f"X_{split}"]
        y = data[f"y_{split}"]
        y_pred = X[:, -1]  # last known value in the lookback window
        results[split] = report_metrics(y, y_pred, label=f"Naive ICU ({split})")

    print("\nThis is the bar every ICU model must clear.")
    print(f"Test RMSE to beat: {results['test']['rmse']:.3f}")


if __name__ == "__main__":
    main()
