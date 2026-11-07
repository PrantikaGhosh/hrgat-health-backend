"""
Loads the trained STGAT models (ICU and general beds) and serves
predictions.

DEMO DESIGN NOTE, worth stating plainly in your paper's limitations
section: the model needs an 8-week lookback window across ALL 369
hospitals to make a prediction, and only has real historical depth
through the training data's timeline (April 2024).

For the bulk endpoint (GET /forecast/all), every hospital uses pure
historical data, since computing live occupancy for all 369 hospitals
on every call isn't practical for a demo.

For a single hospital's forecast/history (GET /hospitals/{id}/forecast
and /history), the hospital being viewed gets a "live" current week:
its last known real value plus net admissions/discharges/transfers
recorded in this demo since seeding. Every other hospital in that same
graph pass still uses its frozen historical value, we only have live
data for whichever hospital someone is actually looking at. This is a
deliberate approximation, not a claim that live occupancy equals
"last known real week + demo activity" in a rigorous sense, but it
keeps the dashboard responsive to real actions without fabricating
data for hospitals nobody is interacting with.

Models and data are loaded once and cached in memory (first request
after server start will be slightly slower).
"""

import pickle
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import torch

sys.path.append("src/models")
from stgat import STGAT  # noqa: E402

ICU_MODEL_PATH = "saved_models/stgat_model.pt"
BEDS_MODEL_PATH = "saved_models/stgat_model_beds.pt"
ICU_STATS_PATH = "data/processed/hospital_norm_stats.pkl"
BEDS_STATS_PATH = "data/processed/hospital_norm_stats_beds.pkl"
PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"
EDGES_PATH = "data/processed/hospital_edges.csv"
NODES_PATH = "data/processed/hospital_nodes.csv"

ICU_TARGET_COL = "staffed_adult_icu_bed_occupancy_7_day_avg"
BEDS_TARGET_COL = "inpatient_beds_used_7_day_avg"
LOOKBACK_WEEKS = 8

_cache: dict = {}


def _load_common() -> None:
    if "hospital_order" in _cache:
        return

    nodes = pd.read_csv(NODES_PATH, dtype={"hospital_pk": str})
    edges = pd.read_csv(EDGES_PATH, dtype={"source": str, "target": str})
    hospital_order = sorted(nodes["hospital_pk"].unique())
    node_index = {h: i for i, h in enumerate(hospital_order)}

    src = edges["source"].map(node_index).values
    tgt = edges["target"].map(node_index).values
    edge_index = np.array([np.concatenate([src, tgt]), np.concatenate([tgt, src])])

    _cache["hospital_order"] = hospital_order
    _cache["edge_index"] = torch.tensor(edge_index, dtype=torch.long)

    panel = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)
    panel["collection_week"] = pd.to_datetime(panel["collection_week"])
    _cache["panel"] = panel


def _load_model_and_stats(target: str):
    key = f"model_{target}"
    if key in _cache:
        return _cache[key], _cache[f"stats_{target}"]

    model_path = ICU_MODEL_PATH if target == "icu" else BEDS_MODEL_PATH
    stats_path = ICU_STATS_PATH if target == "icu" else BEDS_STATS_PATH

    model = STGAT()
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()

    with open(stats_path, "rb") as f:
        stats = pickle.load(f)

    _cache[key] = model
    _cache[f"stats_{target}"] = stats
    return model, stats


def _build_latest_window(target_col: str, stats: dict):
    _load_common()
    panel = _cache["panel"]
    hospital_order = _cache["hospital_order"]

    last_weeks = sorted(panel["collection_week"].unique())[-LOOKBACK_WEEKS:]

    tensor = np.zeros((LOOKBACK_WEEKS, len(hospital_order)), dtype=np.float32)
    for w_idx, week in enumerate(last_weeks):
        week_data = panel[panel["collection_week"] == week].set_index("hospital_pk")[target_col]
        for h_idx, hospital_pk in enumerate(hospital_order):
            if hospital_pk in week_data.index:
                raw_val = week_data.loc[hospital_pk]
                if pd.notna(raw_val):
                    s = stats[hospital_pk]
                    tensor[w_idx, h_idx] = (raw_val - s["mean"]) / s["std"]

    return torch.tensor(tensor, dtype=torch.float32), last_weeks[-1]


def get_forecast_for_all_hospitals(target: str = "icu"):
    """
    target: 'icu' or 'beds'.
    Returns (predictions, last_week): predictions is a dict mapping
    hospital_pk -> predicted value in real units, last_week is the
    most recent week the window was built from.

    This is the BULK version (all hospitals at once), used only by
    GET /forecast/all, and stays pure-historical: computing live data
    for all 369 hospitals on every call would mean 369 extra database
    queries per request. For a single hospital's live-aware forecast,
    see get_forecast_for_hospital_live below.
    """
    target_col = ICU_TARGET_COL if target == "icu" else BEDS_TARGET_COL
    model, stats = _load_model_and_stats(target)
    _load_common()

    window, last_week = _build_latest_window(target_col, stats)
    edge_index = _cache["edge_index"]

    with torch.no_grad():
        pred_norm = model(window, edge_index).numpy()

    hospital_order = _cache["hospital_order"]
    predictions = {}
    for i, hospital_pk in enumerate(hospital_order):
        s = stats[hospital_pk]
        predictions[hospital_pk] = float(pred_norm[i] * s["std"] + s["mean"])

    return predictions, last_week


def get_latest_raw_value(hospital_pk: str, target_col: str):
    """Most recent non-null real-unit value on file for this hospital
    and target, or None if there's no data at all."""
    _load_common()
    panel = _cache["panel"]
    series = panel[panel["hospital_pk"] == hospital_pk].sort_values("collection_week")
    series = series[["collection_week", target_col]].dropna()
    if series.empty:
        return None
    return float(series.iloc[-1][target_col])


def _build_window_with_override(target_col: str, stats: dict, override_hospital_pk: str, override_raw_value: float):
    """
    Same lookback window as _build_latest_window, except the LAST
    week's value for ONE hospital's column is replaced with
    override_raw_value (normalized before insertion). Every other
    hospital's column stays pure historical, we only have a live
    count for whichever hospital is actually being viewed right now.
    """
    window, last_week = _build_latest_window(target_col, stats)
    hospital_order = _cache["hospital_order"]
    if override_hospital_pk in hospital_order:
        h_idx = hospital_order.index(override_hospital_pk)
        s = stats[override_hospital_pk]
        window[-1, h_idx] = (override_raw_value - s["mean"]) / s["std"]
    return window, last_week


def get_forecast_for_hospital_live(hospital_pk: str, target: str, live_addition: float):
    """
    Forecast for ONE hospital, treating "this week" as the last known
    real value plus live_addition (net admissions since seeding for
    that bed type), instead of relying purely on frozen historical
    data. Still runs the full 369-hospital graph through the model
    (GAT needs every hospital's context to inform its neighbors), we
    just override this one hospital's own most recent value first.

    Returns (predicted_value, last_week, live_current_value). All
    three are None-safe: predicted_value is None if hospital_pk isn't
    part of the trained model.
    """
    target_col = ICU_TARGET_COL if target == "icu" else BEDS_TARGET_COL
    model, stats = _load_model_and_stats(target)
    _load_common()

    hospital_order = _cache["hospital_order"]
    if hospital_pk not in hospital_order:
        return None, None, None

    baseline = get_latest_raw_value(hospital_pk, target_col)
    if baseline is None:
        baseline = stats[hospital_pk]["mean"]
    live_current_value = baseline + live_addition

    window, last_week = _build_window_with_override(target_col, stats, hospital_pk, live_current_value)
    edge_index = _cache["edge_index"]

    with torch.no_grad():
        pred_norm = model(window, edge_index).numpy()

    h_idx = hospital_order.index(hospital_pk)
    s = stats[hospital_pk]
    predicted_value = float(pred_norm[h_idx] * s["std"] + s["mean"])
    return predicted_value, last_week, live_current_value


def get_history_for_hospital(hospital_pk: str, target_col: str, weeks: int = 26) -> pd.DataFrame:
    _load_common()
    panel = _cache["panel"]
    series = panel[panel["hospital_pk"] == hospital_pk].sort_values("collection_week")
    return series[["collection_week", target_col]].dropna().tail(weeks)


def get_week_offset() -> timedelta:
    """
    College-project design choice: the real dataset ends in April
    2024, but the demo should feel current. Every date shown to the
    user is shifted forward by a whole number of weeks so the most
    recent historical week reads as "now". Computed fresh from the
    real system clock (datetime.now()) on every call, so however far
    in the future this demo gets run, the dates still read as recent,
    they don't stay frozen at whatever day this feature was built.

    Nothing about the underlying data or the model's own logic is
    touched by this, capacity checks, live-blending, and the model's
    actual lookback window all still use the real historical dates
    internally. Only the date LABELS shown to the user are shifted.
    """
    _load_common()
    panel = _cache["panel"]
    last_historical_week = sorted(panel["collection_week"].unique())[-1]
    days_diff = (datetime.now() - last_historical_week.to_pydatetime()).days
    offset_weeks = round(days_diff / 7)
    return timedelta(weeks=offset_weeks)


def shift_week_label(real_date) -> str:
    """Applies get_week_offset() to a real historical date, returns
    the shifted date as an ISO date string for display."""
    shifted = real_date + get_week_offset()
    return str(shifted.date()) if hasattr(shifted, "date") else str(shifted)
