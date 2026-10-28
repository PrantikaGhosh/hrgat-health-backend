"""
Step 3 of data pipeline: clean the Texas dataset.

- Confirms whether total_beds missingness is temporal (varies by week)
  rather than subtype-driven.
- Converts HHS suppression code (-999999) to proper missing values,
  then imputes suppressed counts as 2 (the midpoint of the suppressed
  range 0-3, since HHS suppresses any true count under 4).
- Forward/backward-fills total_beds_7_day_avg per hospital, since a
  hospital's total bed capacity rarely changes week to week even when
  a given week's report is missing.
- Saves a cleaned file ready for building the weekly time series matrix.
"""

import pandas as pd

INPUT_PATH = "data/processed/texas_hospitals_raw.csv"
OUTPUT_PATH = "data/processed/texas_hospitals_clean.csv"

SUPPRESSION_CODE = -999999
SUPPRESSION_IMPUTE_VALUE = 2  # midpoint of the true suppressed range (0-3)

NUMERIC_COLS = [
    "total_beds_7_day_avg",
    "inpatient_beds_used_7_day_avg",
    "total_icu_beds_7_day_avg",
    "staffed_adult_icu_bed_occupancy_7_day_avg",
    "inpatient_beds_used_covid_7_day_avg",
]


def main():
    df = pd.read_csv(INPUT_PATH, low_memory=False)
    df["collection_week"] = pd.to_datetime(df["collection_week"])

    print("=" * 60)
    print("CHECK: is total_beds missingness temporal?")
    print("=" * 60)
    df["year"] = df["collection_week"].dt.year
    yearly_missing = df.groupby("year")["total_beds_7_day_avg"].apply(
        lambda x: x.isna().mean() * 100
    )
    print(yearly_missing)

    print("\n" + "=" * 60)
    print("STEP: replacing suppression code with proper missing, then imputing")
    print("=" * 60)
    for col in NUMERIC_COLS:
        suppressed_count = (df[col] == SUPPRESSION_CODE).sum()
        print(f"{col}: {suppressed_count} suppressed rows -> imputed as {SUPPRESSION_IMPUTE_VALUE}")
        df[col] = df[col].replace(SUPPRESSION_CODE, SUPPRESSION_IMPUTE_VALUE)

    print("\n" + "=" * 60)
    print("STEP: forward/backward-filling total_beds_7_day_avg per hospital")
    print("=" * 60)
    before_missing = df["total_beds_7_day_avg"].isna().sum()
    df = df.sort_values(["hospital_pk", "collection_week"])
    df["total_beds_7_day_avg"] = df.groupby("hospital_pk")["total_beds_7_day_avg"].transform(
        lambda x: x.ffill().bfill()
    )
    after_missing = df["total_beds_7_day_avg"].isna().sum()
    print(f"Missing before fill: {before_missing:,}")
    print(f"Missing after fill:  {after_missing:,}")
    if after_missing > 0:
        remaining_hospitals = df[df["total_beds_7_day_avg"].isna()]["hospital_pk"].nunique()
        print(f"({remaining_hospitals} hospitals have NO total_beds data in any week, likely drop these later)")

    print("\n" + "=" * 60)
    print(f"Saving cleaned data to {OUTPUT_PATH}")
    print("=" * 60)
    df = df.drop(columns=["year"])
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Final shape: {df.shape}")
    print("Done.")


if __name__ == "__main__":
    main()
