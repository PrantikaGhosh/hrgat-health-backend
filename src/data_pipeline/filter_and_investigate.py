"""
Step 2 of data pipeline: filter to Texas, and investigate why
total_beds_7_day_avg has 32% missing values nationally.

Saves a filtered Texas-only CSV to data/processed/ for the next step.
"""

import pandas as pd

RAW_PATH = "data/raw/hhs_hospital_capacity_raw_2020_2024.csv"
OUTPUT_PATH = "data/processed/texas_hospitals_raw.csv"

COLUMNS = [
    "hospital_pk",
    "collection_week",
    "state",
    "hospital_name",
    "address",
    "city",
    "zip",
    "hospital_subtype",
    "fips_code",
    "is_metro_micro",
    "total_beds_7_day_avg",
    "inpatient_beds_used_7_day_avg",
    "total_icu_beds_7_day_avg",
    "staffed_adult_icu_bed_occupancy_7_day_avg",
    "inpatient_beds_used_covid_7_day_avg",
]


def main():
    print("Loading full dataset (key columns only)...")
    df = pd.read_csv(RAW_PATH, usecols=COLUMNS, low_memory=False)

    print("\n" + "=" * 60)
    print("INVESTIGATION: total_beds_7_day_avg missingness by hospital_subtype")
    print("=" * 60)
    print("(national data, before filtering to Texas)\n")

    subtype_summary = df.groupby("hospital_subtype").agg(
        row_count=("hospital_pk", "count"),
        pct_missing_total_beds=("total_beds_7_day_avg", lambda x: x.isna().mean() * 100),
    ).sort_values("row_count", ascending=False)

    print(subtype_summary)

    print("\n" + "=" * 60)
    print("FILTERING to Texas")
    print("=" * 60)
    tx_df = df[df["state"] == "TX"].copy()
    print(f"Texas rows: {len(tx_df):,}")
    print(f"Texas unique hospitals: {tx_df['hospital_pk'].nunique()}")
    print("\nTexas hospital_subtype breakdown:")
    print(tx_df["hospital_subtype"].value_counts())

    print("\n" + "=" * 60)
    print(f"Saving filtered Texas data to {OUTPUT_PATH}")
    print("=" * 60)
    tx_df.to_csv(OUTPUT_PATH, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
