"""Inspect the raw BASS-II extraction without modifying it."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root
INPUT = ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv"

def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Raw input not found: {INPUT}")
    df = pd.read_csv(INPUT)
    print(f"File: {INPUT.name}")
    print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"Unique test_id: {df['test_id'].nunique() if 'test_id' in df else 'N/A'}")
    print(f"Duplicate complete rows: {df.duplicated().sum()}")
    if "test_id" in df:
        print(f"Duplicate test_id rows: {df['test_id'].duplicated().sum()}")
    print("\nDtypes:\n", df.dtypes.to_string())
    print("\nMissing values:\n", df.isna().sum().to_string())
    for col in ("conservative_event_label", "reused_sample", "flow_configuration"):
        if col in df:
            print(f"\n{col}:\n{df[col].value_counts(dropna=False).to_string()}")
    print("\nPreview:\n", df.head().to_string(index=False))

if __name__ == "__main__":
    main()
