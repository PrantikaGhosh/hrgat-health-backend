"""
Shared evaluation metrics. Every model (naive, ARIMA, LSTM, STGAT)
reports results using these same functions, so numbers in the final
comparison table are computed identically across models.
"""

import numpy as np


def rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true, y_pred):
    return float(np.mean(np.abs(y_true - y_pred)))


def mape(y_true, y_pred, epsilon=1.0):
    """
    Standard MAPE, with a small epsilon added to the denominator.
    Necessary here because many hospitals legitimately have near-zero
    ICU occupancy in a given week, plain MAPE explodes (divide by
    near-zero) without this safeguard.
    """
    return float(np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100)


def report_metrics(y_true, y_pred, label=""):
    r = rmse(y_true, y_pred)
    m = mae(y_true, y_pred)
    p = mape(y_true, y_pred)
    print(f"{label:20s}  RMSE={r:7.3f}   MAE={m:7.3f}   MAPE={p:6.2f}%")
    return {"rmse": r, "mae": m, "mape": p}
