"""Prepare conservative ML subsets; never split repeated test measurements."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root
MAIN = ROOT / "data" / "processed" / "bass2_extracted_data.csv"
ML = ROOT / "data" / "ml_ready"
ML.mkdir(parents=True, exist_ok=True)

def main():
    if not MAIN.exists():
        raise FileNotFoundError(f"Run clean_data.py first: {MAIN}")
    df = pd.read_csv(MAIN)
    # Only explicit event labels in this extraction are eligible.
    # 'not_reported' is not a positive class; reused samples are excluded
    # from the primary classifier due to prior burning/sample alteration.
    eligible = {"quenched", "no_ignition", "blowoff"}
    mask = (~df["reused_sample"].fillna(False).astype(bool)
            & df["conservative_event_label"].isin(eligible))
    cls = df.loc[mask].copy()
    cls["classification_target_event"] = cls["conservative_event_label"]
    cls.to_csv(ML / "classification_dataset.csv", index=False)

    # No numeric flame spread rate exists in the supplied SIBAL extraction.
    # Create a schema-bearing empty file instead of fabricating target values.
    cols = ["record_id", "test_id", "material", "sample_width_cm",
            "sample_length_cm", "sample_thickness_mm_approx", "o2_vol_percent",
            "flow_start_cm_s", "flow_end_cm_s", "flow_configuration",
            "flame_spread_rate_mm_s", "source", "source_page",
            "source_verification_status"]
    pd.DataFrame(columns=cols).to_csv(ML / "regression_dataset.csv", index=False)
    print(f"Classification rows: {len(cls)}")
    print("Regression rows: 0 (no numerical spread-rate target in this extraction)")

if __name__ == "__main__":
    main()
