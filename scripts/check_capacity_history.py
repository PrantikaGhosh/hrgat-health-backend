"""
Diagnostic: check whether a hospital's ICU capacity genuinely changed
over time in the source data, which would explain a historical
occupancy value exceeding the single "current capacity" snapshot
we seeded into the database.

Run from backend/ with venv active:
    python scripts/check_capacity_history.py "Medical City Decatur"
"""

import sys
import pandas as pd

hospital_name_query = sys.argv[1] if len(sys.argv) > 1 else "Medical City Decatur"

panel = pd.read_csv("data/processed/texas_panel_graph_ready.csv", dtype={"hospital_pk": str}, low_memory=False)
panel["collection_week"] = pd.to_datetime(panel["collection_week"])

matches = panel[panel["hospital_name"].str.contains(hospital_name_query, case=False, na=False)]

if matches.empty:
    print(f"No hospital found matching '{hospital_name_query}'")
    sys.exit(0)

hospital_pk = matches["hospital_pk"].iloc[0]
hospital_name = matches["hospital_name"].iloc[0]
print(f"Hospital: {hospital_name}  (hospital_pk={hospital_pk})\n")

series = panel[panel["hospital_pk"] == hospital_pk].sort_values("collection_week")
series = series[["collection_week", "total_icu_beds_7_day_avg", "staffed_adult_icu_bed_occupancy_7_day_avg"]]

print(f"{'Week':<12}  {'ICU capacity':>13}  {'ICU occupied':>13}  {'Over capacity?':>15}")
print("-" * 60)
for _, row in series.iterrows():
    cap = row["total_icu_beds_7_day_avg"]
    occ = row["staffed_adult_icu_bed_occupancy_7_day_avg"]
    over = "  <-- YES" if pd.notna(cap) and pd.notna(occ) and occ > cap else ""
    cap_str = f"{cap:.0f}" if pd.notna(cap) else "—"
    occ_str = f"{occ:.1f}" if pd.notna(occ) else "—"
    print(f"{str(row['collection_week'].date()):<12}  {cap_str:>13}  {occ_str:>13}  {over:>15}")

print(f"\nMost recent capacity on file (this is what got seeded into the DB): "
      f"{series['total_icu_beds_7_day_avg'].dropna().iloc[-1]:.0f}")
print(f"Max capacity ever reported historically: {series['total_icu_beds_7_day_avg'].max():.0f}")
print(f"Max occupancy ever reported historically: {series['staffed_adult_icu_bed_occupancy_7_day_avg'].max():.1f}")
