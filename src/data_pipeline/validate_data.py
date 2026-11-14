"""Validate structural and scientific guardrails for the processed extraction."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root
MAIN = ROOT / "data" / "processed" / "bass2_extracted_data.csv"

def main():
    if not MAIN.exists():
        raise FileNotFoundError(f"Missing {MAIN}; run clean_data.py")
    df = pd.read_csv(MAIN)
    errors = []
    if df["test_id"].isna().any():
        errors.append("Missing test_id values")
    if df["record_id"].duplicated().any():
        errors.append("Duplicate record_id values")
    # Repeated test IDs are allowed in principle but must be grouped for ML.
    print(f"Rows={len(df)}; unique_test_ids={df['test_id'].nunique()}")
    print(f"Duplicate rows={df.duplicated().sum()}")
    print(f"Duplicate test_id rows={df['test_id'].duplicated().sum()}")
    print("Missing values by column:")
    print(df.isna().sum().to_string())
    if "airflow_velocity_cm_s" in df and df["airflow_velocity_cm_s"].notna().any():
        errors.append("Scalar airflow_velocity_cm_s populated without a documented derivation")
    if "flame_spread_rate_mm_s" in df and df["flame_spread_rate_mm_s"].notna().any():
        print("Note: verify each non-null spread-rate against a direct source location.")
    if errors:
        raise ValueError("Validation failed:\n- " + "\n- ".join(errors))
    print("Structural validation passed. Scientific row-level verification remains incomplete.")

if __name__ == "__main__":
    main()
