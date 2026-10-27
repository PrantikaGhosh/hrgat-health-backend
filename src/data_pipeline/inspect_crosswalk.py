"""
Step 6a of data pipeline: inspect the Dartmouth hospital-to-HSA-to-HRR
crosswalk file before merging it with our Texas panel.

We don't yet know the exact column names Dartmouth uses, so this
script just loads and prints structure first, no merging yet.
"""

import pandas as pd

CROSSWALK_PATH = "data/raw/hospital_hrr_crosswalk_2014.xls"


def main():
    df = pd.read_excel(CROSSWALK_PATH)

    print("=" * 60)
    print("Crosswalk file shape and columns")
    print("=" * 60)
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")

    print("\n" + "=" * 60)
    print("First 5 rows")
    print("=" * 60)
    print(df.head())

    print("\n" + "=" * 60)
    print("Data types")
    print("=" * 60)
    print(df.dtypes)


if __name__ == "__main__":
    main()
