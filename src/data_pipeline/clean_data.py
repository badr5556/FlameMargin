"""Create a non-destructive structured table from the raw extraction."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root
RAW = ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv"
OUT = ROOT / "data" / "processed" / "bass2_extracted_data.csv"

def main():
    if not RAW.exists():
        raise FileNotFoundError(f"Expected raw CSV at {RAW}")
    df = pd.read_csv(RAW, dtype={"test_id": "string"})
    # Preserve every source column and add explicit provenance/ML placeholders.
    df.insert(0, "record_id", range(1, len(df) + 1))
    df["source_verification_status"] = "secondary_extraction_not_independently_verified_row_by_row"
    df["measurement_type"] = "test_level_summary_with_start_end_flow"
    # Start and end velocities are not collapsed into one invented scalar.
    df["airflow_velocity_cm_s"] = pd.NA
    df["ignition_outcome"] = pd.NA
    df["sustained_combustion"] = pd.NA
    df["flame_spread_rate_mm_s"] = pd.NA
    df["flow_start_cm_s_original"] = df["flow_start_cm_s"]
    df["flow_end_cm_s_original"] = df["flow_end_cm_s"]
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} records to {OUT}")

if __name__ == "__main__":
    main()
