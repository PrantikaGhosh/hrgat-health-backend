"""
Step 7 of data pipeline: build the final graph structure.

- Drops the 57 hospitals with no HRR match.
- Filters the final panel down to the 369 matched hospitals.
- Builds the edge list: two hospitals are connected if they belong
  to the same HRR (shared regional referral market).

Outputs:
  data/processed/texas_panel_graph_ready.csv   (node time series data)
  data/processed/hospital_edges.csv            (graph structure)
  data/processed/hospital_nodes.csv            (node metadata: which HRR each hospital belongs to)
"""

import itertools
import pandas as pd

MAPPING_PATH = "data/processed/hospital_to_hrr_mapping.csv"
PANEL_PATH = "data/processed/texas_panel_final.csv"

NODES_OUTPUT_PATH = "data/processed/hospital_nodes.csv"
EDGES_OUTPUT_PATH = "data/processed/hospital_edges.csv"
PANEL_OUTPUT_PATH = "data/processed/texas_panel_graph_ready.csv"


def main():
    print("Loading HRR mapping and dropping unmatched hospitals...")
    mapping = pd.read_csv(MAPPING_PATH, dtype={"hospital_pk": str})
    mapping = mapping.dropna(subset=["hrrnum"])
    mapping["hrrnum"] = mapping["hrrnum"].astype(int)
    matched_ids = mapping["hospital_pk"].unique()
    print(f"Matched hospitals: {len(matched_ids)}")

    print("\nSaving node metadata...")
    nodes = mapping[["hospital_pk", "hrrnum", "hrrcity", "hsanum", "hsacity"]].drop_duplicates()
    nodes.to_csv(NODES_OUTPUT_PATH, index=False)
    print(f"Saved {len(nodes)} nodes to {NODES_OUTPUT_PATH}")

    print("\nBuilding edge list (hospitals sharing the same HRR)...")
    edges = []
    for hrr, group in nodes.groupby("hrrnum"):
        hospital_ids = group["hospital_pk"].tolist()
        for h1, h2 in itertools.combinations(hospital_ids, 2):
            edges.append({"source": h1, "target": h2, "hrrnum": hrr})
    edges_df = pd.DataFrame(edges)
    edges_df.to_csv(EDGES_OUTPUT_PATH, index=False)
    print(f"Total edges: {len(edges_df)}")

    print("\nEdge count per HRR (top 10):")
    print(edges_df["hrrnum"].value_counts().head(10))

    print("\nFiltering panel to graph-ready hospitals...")
    panel = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)
    panel = panel[panel["hospital_pk"].isin(matched_ids)]
    panel.to_csv(PANEL_OUTPUT_PATH, index=False)
    print(f"Final panel shape: {panel.shape}")
    print(f"Saved to {PANEL_OUTPUT_PATH}")

    print("\nDone. Graph structure ready:")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges_df)}")
    print(f"  HRRs (connected components): {nodes['hrrnum'].nunique()}")


if __name__ == "__main__":
    main()
