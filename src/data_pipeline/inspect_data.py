"""
First-look inspection of the HHS hospital capacity dataset.
Run this once to understand size, coverage, and data quality
before deciding on filtering / cleaning strategy.
"""

import os
import pandas as pd

RAW_PATH = "data/raw/hhs_hospital_capacity_raw_2020_2024.csv"

KEY_COLUMNS = [
    "hospital_pk",
    "collection_week",
    "state",
    "hospital_name",
    "fips_code",
    "is_metro_micro",
    "total_beds_7_day_avg",
    "inpatient_beds_used_7_day_avg",
    "total_icu_beds_7_day_avg",
    "staffed_adult_icu_bed_occupancy_7_day_avg",
    "inpatient_beds_used_covid_7_day_avg",
]


def check_file_size():
    size_bytes = os.path.getsize(RAW_PATH)
    size_gb = size_bytes / (1024 ** 3)
    print(f"File size: {size_gb:.2f} GB")


def main():
    print("=" * 60)
    print("STEP 1: File size check")
    print("=" * 60)
    check_file_size()

    print("\n" + "=" * 60)
    print("STEP 2: Loading key columns only")
    print("=" * 60)
    df = pd.read_csv(RAW_PATH, usecols=KEY_COLUMNS, low_memory=False)
    print(f"Rows loaded: {len(df):,}")
    print(f"Columns: {list(df.columns)}")

    print("\n" + "=" * 60)
    print("STEP 3: Date / coverage range")
    print("=" * 60)
    print("Earliest week:", df["collection_week"].min())
    print("Latest week:  ", df["collection_week"].max())
    print("Unique weeks: ", df["collection_week"].nunique())

    print("\n" + "=" * 60)
    print("STEP 4: Hospital and state coverage")
    print("=" * 60)
    print("Unique hospitals (hospital_pk):", df["hospital_pk"].nunique())
    print("Unique states:", df["state"].nunique())
    print("\nTop 10 states by number of (hospital, week) rows:")
    print(df["state"].value_counts().head(10))

    print("\n" + "=" * 60)
    print("STEP 5: Missing value check on key numeric fields")
    print("=" * 60)
    numeric_cols = [
        "total_beds_7_day_avg",
        "inpatient_beds_used_7_day_avg",
        "total_icu_beds_7_day_avg",
        "staffed_adult_icu_bed_occupancy_7_day_avg",
        "inpatient_beds_used_covid_7_day_avg",
    ]
    for col in numeric_cols:
        missing_pct = df[col].isna().mean() * 100
        # HHS suppresses small values as -999999
        suppressed_pct = (df[col] == -999999).mean() * 100
        print(f"{col:50s} missing: {missing_pct:5.1f}%   suppressed(-999999): {suppressed_pct:5.1f}%")

    print("\n" + "=" * 60)
    print("STEP 6: fips_code coverage (needed for graph construction)")
    print("=" * 60)
    fips_missing_pct = df["fips_code"].isna().mean() * 100
    print(f"fips_code missing: {fips_missing_pct:.1f}%")

    print("\nDone. Use this summary to decide state/region filtering next.")


if __name__ == "__main__":
    main()
