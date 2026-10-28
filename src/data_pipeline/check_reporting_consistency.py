"""
Step 4 of data pipeline: build the hospital x week panel and check
reporting consistency (which hospitals report almost every week vs
sporadically).

This does NOT build the final model-ready tensor yet, it's a
diagnostic pass to decide which hospitals are reliable enough to
include as graph nodes.
"""

import pandas as pd

INPUT_PATH = "data/processed/texas_hospitals_clean.csv"

TARGET_COLS = [
    "inpatient_beds_used_7_day_avg",
    "total_icu_beds_7_day_avg",
    "staffed_adult_icu_bed_occupancy_7_day_avg",
    "total_beds_7_day_avg",
]


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])

    total_weeks = df["collection_week"].nunique()
    print(f"Total possible weeks in dataset: {total_weeks}")

    print("\n" + "=" * 60)
    print("Dropping the 9 hospitals with zero total_beds data")
    print("=" * 60)
    fully_missing = df.groupby("hospital_pk")["total_beds_7_day_avg"].apply(
        lambda x: x.isna().all()
    )
    drop_ids = fully_missing[fully_missing].index.tolist()
    df = df[~df["hospital_pk"].isin(drop_ids)]
    print(f"Dropped {len(drop_ids)} hospitals. Remaining: {df['hospital_pk'].nunique()}")

    print("\n" + "=" * 60)
    print("Reporting consistency per hospital (% of weeks reported)")
    print("=" * 60)
    weeks_reported = df.groupby("hospital_pk")["collection_week"].nunique()
    pct_reported = (weeks_reported / total_weeks * 100).sort_values()

    print("Distribution of reporting completeness across hospitals:")
    print(pct_reported.describe())

    print("\nHospitals reporting less than 50% of weeks:", (pct_reported < 50).sum())
    print("Hospitals reporting less than 80% of weeks:", (pct_reported < 80).sum())
    print("Hospitals reporting 95%+ of weeks:", (pct_reported >= 95).sum())

    print("\n" + "=" * 60)
    print("Sample of worst reporters")
    print("=" * 60)
    print(pct_reported.head(10))


if __name__ == "__main__":
    main()
