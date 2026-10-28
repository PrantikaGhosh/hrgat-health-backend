"""
Step 5 of data pipeline: build the final model-ready panel.

- Keeps only hospitals reporting >= 80% of weeks.
- Drops the 9 hospitals with zero total_beds data (as before).
- Reindexes each hospital to the full weekly date range, so every
  hospital has one row per week (missing weeks become NaN rows).
- Linearly interpolates small gaps in the target columns per hospital.
- Leaves edge NaNs (before a hospital started reporting, or after it
  stopped) as NaN, since interpolation can't guess beyond known data,
  these get handled explicitly when we build training windows later.

Saves the final panel to data/processed/texas_panel_final.csv
"""

import pandas as pd

INPUT_PATH = "data/processed/texas_hospitals_clean.csv"
OUTPUT_PATH = "data/processed/texas_panel_final.csv"

REPORTING_THRESHOLD_PCT = 80

TARGET_COLS = [
    "total_beds_7_day_avg",
    "inpatient_beds_used_7_day_avg",
    "total_icu_beds_7_day_avg",
    "staffed_adult_icu_bed_occupancy_7_day_avg",
    "inpatient_beds_used_covid_7_day_avg",
]

STATIC_COLS = [
    "hospital_name", "address", "city", "zip",
    "hospital_subtype", "fips_code", "is_metro_micro", "state",
]


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])

    # Drop hospitals with zero total_beds data (same 9 as before)
    fully_missing = df.groupby("hospital_pk")["total_beds_7_day_avg"].apply(lambda x: x.isna().all())
    df = df[~df["hospital_pk"].isin(fully_missing[fully_missing].index)]

    all_weeks = pd.date_range(df["collection_week"].min(), df["collection_week"].max(), freq="W-SUN")
    total_weeks = len(all_weeks)

    # Filter by reporting completeness
    weeks_reported = df.groupby("hospital_pk")["collection_week"].nunique()
    pct_reported = weeks_reported / total_weeks * 100
    keep_ids = pct_reported[pct_reported >= REPORTING_THRESHOLD_PCT].index
    df = df[df["hospital_pk"].isin(keep_ids)]
    print(f"Kept {df['hospital_pk'].nunique()} hospitals (>= {REPORTING_THRESHOLD_PCT}% reporting)")

    # Reindex each hospital to the full weekly range, then interpolate gaps
    print("Reindexing to full weekly range and interpolating gaps...")
    panels = []
    for hospital_id, group in df.groupby("hospital_pk"):
        group = group.set_index("collection_week").reindex(all_weeks)
        group["hospital_pk"] = hospital_id
        # Carry static (non-time-varying) fields forward across the gaps
        for col in STATIC_COLS:
            group[col] = group[col].ffill().bfill()
        # Interpolate the actual target values, don't extrapolate past known edges
        for col in TARGET_COLS:
            group[col] = group[col].interpolate(method="linear", limit_area="inside")
        panels.append(group)

    final_df = pd.concat(panels).rename_axis("collection_week").reset_index()

    print("\n" + "=" * 60)
    print("Remaining missing values after interpolation (edge gaps only)")
    print("=" * 60)
    for col in TARGET_COLS:
        missing_pct = final_df[col].isna().mean() * 100
        print(f"{col:50s} {missing_pct:5.1f}% missing")

    final_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved final panel: {final_df.shape} -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
