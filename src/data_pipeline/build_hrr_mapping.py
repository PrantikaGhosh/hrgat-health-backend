"""
Step 6b of data pipeline: build the hospital -> HRR mapping.

- Pulls the 'ccn' field back in from the raw national CSV (we didn't
  keep it in our earlier filtered columns).
- Normalizes both our ccn and the crosswalk's 'provider' field to
  the same 6-digit zero-padded string format.
- Merges to assign each of our 426 kept Texas hospitals an HRR.
- Reports match rate honestly, unmatched hospitals (likely temporary
  COVID-era facility codes) get flagged, not silently dropped.
"""

import pandas as pd

RAW_NATIONAL_PATH = "data/raw/hhs_hospital_capacity_raw_2020_2024.csv"
PANEL_PATH = "data/processed/texas_panel_final.csv"
CROSSWALK_PATH = "data/raw/hospital_hrr_crosswalk_2014.xls"
OUTPUT_PATH = "data/processed/hospital_to_hrr_mapping.csv"


def normalize_ccn(series):
    """Convert to 6-digit zero-padded string, e.g. 450001."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)  # strip float artifacts if any
        .str.zfill(6)
    )


def main():
    print("Loading kept hospital list from final panel...")
    panel = pd.read_csv(PANEL_PATH, usecols=["hospital_pk"], dtype={"hospital_pk": str})
    kept_hospital_ids = panel["hospital_pk"].unique()
    print(f"Kept hospitals: {len(kept_hospital_ids)}")

    print("\nPulling ccn from raw national file for these hospitals...")
    raw = pd.read_csv(
        RAW_NATIONAL_PATH,
        usecols=["hospital_pk", "ccn", "state"],
        dtype={"hospital_pk": str},
        low_memory=False,
    )
    raw = raw[raw["hospital_pk"].isin(kept_hospital_ids)]
    hospital_ccn_map = raw.drop_duplicates(subset="hospital_pk")[["hospital_pk", "ccn"]]
    print(f"hospital_pk -> ccn mapping built: {len(hospital_ccn_map)} rows")
    print(f"Missing/null ccn: {hospital_ccn_map['ccn'].isna().sum()}")

    print("\nLoading Dartmouth crosswalk...")
    crosswalk = pd.read_excel(CROSSWALK_PATH)
    crosswalk = crosswalk.rename(columns={"provider": "ccn"})

    print("\nNormalizing ccn formats on both sides...")
    hospital_ccn_map["ccn_norm"] = normalize_ccn(hospital_ccn_map["ccn"])
    crosswalk["ccn_norm"] = normalize_ccn(crosswalk["ccn"])

    print("\nMerging...")
    merged = hospital_ccn_map.merge(
        crosswalk[["ccn_norm", "hsanum", "hsacity", "hrrnum", "hrrcity"]],
        on="ccn_norm",
        how="left",
    )

    matched = merged["hrrnum"].notna().sum()
    unmatched = merged["hrrnum"].isna().sum()
    print(f"\nMatched: {matched} / {len(merged)} ({matched / len(merged) * 100:.1f}%)")
    print(f"Unmatched: {unmatched}")

    if unmatched > 0:
        print("\nSample of unmatched hospital_pk values (likely temp COVID facility codes):")
        print(merged[merged["hrrnum"].isna()]["hospital_pk"].head(10).tolist())

    print("\nUnique HRRs represented among matched Texas hospitals:")
    print(merged["hrrnum"].nunique())
    print("\nTop HRRs by hospital count:")
    print(merged["hrrcity"].value_counts().head(10))

    merged.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved mapping to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
