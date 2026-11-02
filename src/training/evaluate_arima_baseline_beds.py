"""
Baseline 1: per-hospital ARIMA.

Fits one ARIMA model per hospital on the training period, then
walks forward through val/test one week at a time: forecast the
next week, then reveal the true value before forecasting the week
after (refit=False updates model state without re-estimating
parameters, this is standard and much faster than refitting from
scratch every week while still being a fair one-step-ahead test).

Fixed order (2,1,2) is used for every hospital rather than tuning
per hospital, this is a deliberate scope decision for compute time,
noted here so it can be stated plainly in the paper's methodology
rather than presented as an oversight.
"""

import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from metrics import report_metrics

warnings.filterwarnings("ignore")  # ARIMA convergence warnings are expected and noisy

PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"
TARGET_COL = "inpatient_beds_used_7_day_avg"
ARIMA_ORDER = (2, 1, 2)

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
    eval_weeks = list(val_weeks) + list(test_weeks)

    hospital_ids = df["hospital_pk"].unique()
    print(f"Fitting ARIMA{ARIMA_ORDER} on general bed occupancy for {len(hospital_ids)} hospitals...")

    val_true, val_pred, test_true, test_pred = [], [], [], []
    n_failed = 0

    for idx, hospital_id in enumerate(hospital_ids):
        series = (
            df[df["hospital_pk"] == hospital_id]
            .sort_values("collection_week")
            .set_index("collection_week")[TARGET_COL]
        )
        train_series = series.loc[series.index.isin(train_weeks)].dropna()

        if len(train_series) < 20:  # not enough history to fit meaningfully
            n_failed += 1
            continue

        try:
            model = ARIMA(train_series, order=ARIMA_ORDER)
            fit = model.fit()
        except Exception:
            n_failed += 1
            continue

        history = train_series.copy()
        for week in eval_weeks:
            true_val = series.get(week, np.nan)
            if np.isnan(true_val):
                continue
            try:
                forecast = fit.forecast(steps=1).iloc[0]
            except Exception:
                n_failed += 1
                break

            if week in val_weeks:
                val_true.append(true_val)
                val_pred.append(forecast)
            else:
                test_true.append(true_val)
                test_pred.append(forecast)

            # reveal true value, update state without full refit
            history = pd.concat([history, pd.Series([true_val], index=[week])])
            try:
                fit = fit.apply(history, refit=False)
            except Exception:
                break

        if (idx + 1) % 50 == 0:
            print(f"  processed {idx + 1}/{len(hospital_ids)} hospitals...")

    print(f"\nHospitals skipped/failed: {n_failed} / {len(hospital_ids)}")

    print("\n" + "=" * 60)
    print("ARIMA Beds results")
    print("=" * 60)
    report_metrics(np.array(val_true), np.array(val_pred), label="ARIMA Beds (val)")
    report_metrics(np.array(test_true), np.array(test_pred), label="ARIMA Beds (test)")


if __name__ == "__main__":
    main()
