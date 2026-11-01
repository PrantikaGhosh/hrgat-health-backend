"""
Step 10: prepare the graph-snapshot dataset for the STGAT model
— ICU TARGET VERSION.

Permanently ICU-only file. See prepare_stgat_dataset_beds.py for the
general bed occupancy equivalent.
"""

import pickle
import numpy as np
import pandas as pd

PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"
NODES_PATH = "data/processed/hospital_nodes.csv"
EDGES_PATH = "data/processed/hospital_edges.csv"
STATS_PATH = "data/processed/hospital_norm_stats.pkl"

TARGET_COL = "staffed_adult_icu_bed_occupancy_7_day_avg"
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
    print("Loading panel, node list, edges, and normalization stats...")
    df = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])

    nodes = pd.read_csv(NODES_PATH, dtype={"hospital_pk": str})
    edges = pd.read_csv(EDGES_PATH, dtype={"source": str, "target": str})
    with open(STATS_PATH, "rb") as f:
        stats = pickle.load(f)

    hospital_order = sorted(nodes["hospital_pk"].unique())
    node_index = {h: i for i, h in enumerate(hospital_order)}
    num_nodes = len(hospital_order)
    print(f"Num nodes: {num_nodes}")

    print("\nBuilding edge_index (bidirectional, since referral relationships are undirected)...")
    src = edges["source"].map(node_index).values
    tgt = edges["target"].map(node_index).values
    edge_index = np.array([
        np.concatenate([src, tgt]),
        np.concatenate([tgt, src]),
    ])
    print(f"edge_index shape: {edge_index.shape}  (directed edges, both directions included)")

    print("\nBuilding (weeks x nodes) normalized value tensor...")
    all_weeks = sorted(df["collection_week"].unique())
    week_index = {w: i for i, w in enumerate(all_weeks)}
    num_weeks = len(all_weeks)

    tensor = np.full((num_weeks, num_nodes), np.nan, dtype=np.float32)
    for _, row in df.iterrows():
        h = row["hospital_pk"]
        if h not in node_index:
            continue
        w_idx = week_index[row["collection_week"]]
        n_idx = node_index[h]
        raw_val = row[TARGET_COL]
        if pd.isna(raw_val):
            continue
        s = stats[h]
        tensor[w_idx, n_idx] = (raw_val - s["mean"]) / s["std"]

    remaining_nan = np.isnan(tensor).sum()
    total_cells = tensor.size
    print(f"Remaining NaN cells: {remaining_nan} / {total_cells} ({remaining_nan / total_cells * 100:.2f}%)")
    print("Filling remaining NaN with 0 (each hospital's own normalized mean)...")
    tensor = np.nan_to_num(tensor, nan=0.0)

    print("\nBuilding full-graph lookback windows...")
    train_weeks, val_weeks, test_weeks = get_split_weeks(all_weeks)

    X, y, target_week_list = [], [], []
    for i in range(num_weeks - LOOKBACK_WEEKS - HORIZON_WEEKS + 1):
        window_x = tensor[i : i + LOOKBACK_WEEKS, :]
        window_y = tensor[i + LOOKBACK_WEEKS + HORIZON_WEEKS - 1, :]
        X.append(window_x)
        y.append(window_y)
        target_week_list.append(all_weeks[i + LOOKBACK_WEEKS + HORIZON_WEEKS - 1])

    X = np.array(X)
    y = np.array(y)
    target_weeks_arr = np.array(target_week_list)

    train_mask = np.isin(target_weeks_arr, train_weeks)
    val_mask = np.isin(target_weeks_arr, val_weeks)
    test_mask = np.isin(target_weeks_arr, test_weeks)

    print(f"\nTotal graph-snapshot windows: {len(X)}")
    print(f"Train: {train_mask.sum()}  Val: {val_mask.sum()}  Test: {test_mask.sum()}")

    np.savez(
        "data/processed/stgat_dataset.npz",
        X_train=X[train_mask], y_train=y[train_mask],
        X_val=X[val_mask], y_val=y[val_mask],
        X_test=X[test_mask], y_test=y[test_mask],
        edge_index=edge_index,
        hospital_order=np.array(hospital_order),
    )
    print("\nSaved to data/processed/stgat_dataset.npz")
    print("Contains: X/y for train/val/test, edge_index, hospital_order (for denormalization)")


if __name__ == "__main__":
    main()
