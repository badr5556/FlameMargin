"""Feature engineering for the FlameMargin Prediction Engine (Layer 1).

Model features (in this order):
    o2_pct            oxygen concentration, vol% (as reported in Table 7.1)
    log10_flow        log10 of the forced-flow velocity in cm/s
    log10_flow_sq     (log10 flow)^2: lets a linear model bend into a U-shaped
                      boundary (quenching branch at low flow, blowoff at high flow)
    sample_width_cm   SIBAL sample width (1.2 or 2.2 cm in the data)

Distance features (for the kNN out-of-distribution check) drop the squared term
so flow is not counted twice: o2_pct, log10_flow, sample_width_cm.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
POINTS_CSV = ROOT / "data" / "processed" / "flame_points.csv"
DISPLAY_CSV = ROOT / "data" / "processed" / "display_only_points.csv"
RAW_CSV = ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv"

FEATURES = ["o2_pct", "log10_flow", "log10_flow_sq", "sample_width_cm"]
DISTANCE_FEATURES = ["o2_pct", "log10_flow", "sample_width_cm"]
DEFAULT_SAMPLE_WIDTH_CM = 2.2  # the most common width in the data (2.2 cm)


def load_points(path: Path = POINTS_CSV) -> pd.DataFrame:
    """The derived training points (see src/data_pipeline/derive_points.py)."""
    return pd.read_csv(path, dtype={"test_id": "string", "point_id": "string"})


def load_display_points(path: Path = DISPLAY_CSV) -> pd.DataFrame:
    """Rows shown on the map only (reused samples, no definitive outcome)."""
    return pd.read_csv(path, dtype={"test_id": "string"}, keep_default_na=False)


def feature_frame(o2_pct, flow_cm_s, sample_width_cm=DEFAULT_SAMPLE_WIDTH_CM) -> pd.DataFrame:
    """Model features for scalars or arrays (broadcast together)."""
    o2, flow, width = np.broadcast_arrays(
        np.asarray(o2_pct, dtype=float), np.asarray(flow_cm_s, dtype=float), np.asarray(sample_width_cm, dtype=float)
    )
    if np.any(flow <= 0):
        raise ValueError("flow_cm_s must be > 0 (log scale)")
    lf = np.log10(flow.ravel())
    return pd.DataFrame({
        "o2_pct": o2.ravel(),
        "log10_flow": lf,
        "log10_flow_sq": lf**2,
        "sample_width_cm": width.ravel(),
    })


def training_matrix(points: pd.DataFrame | None = None) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """(X, y, groups) for the derived points; groups = test_id (both points of a test stay together)."""
    pts = load_points() if points is None else points
    X = feature_frame(pts["o2_pct"], pts["flow_cm_s"], pts["sample_width_cm"])[FEATURES]
    return X, pts["burn"].to_numpy(dtype=int), pts["test_id"].to_numpy(dtype=str)
