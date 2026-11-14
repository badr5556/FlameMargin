"""Flame spread rate for PMMA slabs from Table 5.1 (Miller, NASA/TM-20210011385 p. 57).

    python -m src.spread_rate      # writes data/processed/spread_rates_v1.csv and models/spread_rate_v1.json

Data: every velocity in Table 5.1 that has a measured spread rate (mm/s): 39 values from 18 tests (M6 and M12 are
"Not tracked"). Each row keeps the verbatim Table 5.1 row text as ``evidence_quote``. No value comes from a figure.

O2: Table 5.1 gives one initial and one final O2 per test, not one per velocity. The O2 during each measurement lies
between the two. The shipped model uses the **initial** O2 (the same convention as the burn points); a sensitivity
run with the final O2 is reported. Nothing is interpolated.

Model (pre-specified): ordinary least squares, log10(spread rate) ~ O2 + log10(flow) + log10(thickness).
Validation: leave-one-test-out against a baseline that predicts the training mean of log10(spread rate).
Interval: 90% interval from the 5th–95th percentiles of the leave-one-test-out residuals (log10 space).
Domain: PMMA slab, opposed flow, 1 atm, microgravity, inside the Table 5.1 ranges of O2, flow and thickness.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneGroupOut

from src.data_pipeline.report_tables import parse_table_5_1

ROOT = Path(__file__).resolve().parent.parent
SPREAD_CSV = ROOT / "data" / "processed" / "spread_rates_v1.csv"
SPREAD_JSON = ROOT / "models" / "spread_rate_v1.json"
FEATURES = ["o2_pct", "log10_flow", "log10_thickness"]
FAMILY = "PMMA_slab"
NOT_MODELLED = "spread rate is only modelled for PMMA slabs (Table 5.1); none is predicted for this material"


def build_table() -> pd.DataFrame:
    rows = []
    for _, r in parse_table_5_1().iterrows():
        if not r["spread_rate_tracked"]:
            continue
        for v, s in zip(r["velocities_cm_s"], r["spread_rates_mm_s"]):
            rows.append({
                "test_id": r["test_id"], "material_family": FAMILY, "flow_configuration": "opposed",
                "thickness_mm": r["thickness_mm"], "width_cm": r["width_cm"], "sides_burning": r["sides_burning"],
                "flow_cm_s": v, "spread_rate_mm_s": s, "o2_initial_pct": r["o2_initial"], "o2_final_pct": r["o2_final"],
                "burn_time_min": r["burn_time_min"], "evidence_quote": r["row_text"], "source_page": r["source_page"],
            })
    return pd.DataFrame(rows)


def _X(df: pd.DataFrame, o2_col: str) -> np.ndarray:
    return np.column_stack([df[o2_col], np.log10(df["flow_cm_s"]), np.log10(df["thickness_mm"])])


def _loto(df: pd.DataFrame, o2_col: str) -> tuple[np.ndarray, np.ndarray]:
    y = np.log10(df["spread_rate_mm_s"].to_numpy())
    X = _X(df, o2_col)
    groups = df["test_id"].to_numpy()
    pm, pb = np.zeros(len(y)), np.zeros(len(y))
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        pm[te] = LinearRegression().fit(X[tr], y[tr]).predict(X[te])
        pb[te] = y[tr].mean()
    return pm, pb


def _scores(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    res = y - p
    ss = float(((y - y.mean()) ** 2).sum())
    return {"rmse_log10": round(float(np.sqrt(np.mean(res ** 2))), 3), "mae_log10": round(float(np.mean(np.abs(res))), 3),
            "r2_loto": round(1 - float((res ** 2).sum()) / ss, 3),
            "median_abs_factor_error": round(float(10 ** np.median(np.abs(res))), 2)}


def train() -> tuple[pd.DataFrame, dict[str, Any]]:
    df = build_table()
    y = np.log10(df["spread_rate_mm_s"].to_numpy())
    pm, pb = _loto(df, "o2_initial_pct")
    pm_f, pb_f = _loto(df, "o2_final_pct")
    resid = y - pm
    fit = LinearRegression().fit(_X(df, "o2_initial_pct"), y)
    metrics = {
        "data": {"file": str(SPREAD_CSV.relative_to(ROOT)), "n_points": int(len(df)), "n_tests": int(df["test_id"].nunique()),
                 "source": "NASA/TM-20210011385, Table 5.1 (p. 57), Miller PMMA slabs; tests M6 and M12 'Not tracked'",
                 "ranges": {"o2_initial_pct": [float(df["o2_initial_pct"].min()), float(df["o2_initial_pct"].max())],
                            "flow_cm_s": [float(df["flow_cm_s"].min()), float(df["flow_cm_s"].max())],
                            "thickness_mm": [float(df["thickness_mm"].min()), float(df["thickness_mm"].max())],
                            "spread_rate_mm_s": [float(df["spread_rate_mm_s"].min()), float(df["spread_rate_mm_s"].max())]}},
        "model": "OLS log10(spread mm/s) ~ O2 (initial, %) + log10(flow cm/s) + log10(thickness mm)",
        "coefficients": {"intercept": round(float(fit.intercept_), 4), **{f: round(float(c), 4) for f, c in zip(FEATURES, fit.coef_)}},
        "validation": "leave-one-test-out (grouped by test_id)",
        "loto": {"model": _scores(y, pm), "baseline_mean": _scores(y, pb)},
        "sensitivity_final_o2": {"model": _scores(y, pm_f), "baseline_mean": _scores(y, pb_f)},
        "interval": {"level": 0.9, "method": "5th-95th percentile of LOTO residuals (log10)",
                     "residual_q05": round(float(np.quantile(resid, 0.05)), 4), "residual_q95": round(float(np.quantile(resid, 0.95)), 4)},
        "o2_note": "Table 5.1 gives initial and final O2 per test; the shipped fit uses the initial O2 (no interpolation).",
    }
    return df, metrics


def save() -> dict[str, Any]:
    df, m = train()
    SPREAD_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SPREAD_CSV, index=False)
    SPREAD_JSON.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    return m


@lru_cache(maxsize=1)
def _model() -> dict[str, Any] | None:
    try:
        return json.loads(SPREAD_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def predict_spread(family: str | None, o2: float, flow: float, resolved: dict[str, Any] | None) -> dict[str, Any]:
    """Spread rate (mm/s) with a 90% interval for PMMA slabs inside the Table 5.1 ranges; otherwise None + reason."""
    m = _model()
    if family != FAMILY or m is None:
        return {"spread_rate_mm_s": None, "spread_rate_reason": NOT_MODELLED}
    th = (resolved or {}).get("thickness_mm")
    rng = m["data"]["ranges"]
    out_of = []
    for name, val, key, unit in (("O2", o2, "o2_initial_pct", "%"), ("flow", flow, "flow_cm_s", " cm/s"),
                                 ("thickness", th, "thickness_mm", " mm")):
        lo, hi = rng[key]
        if val is None or not (lo <= float(val) <= hi):
            out_of.append(f"{name} {val}{unit} outside the Table 5.1 range {lo:g}–{hi:g}{unit}")
    if out_of:
        return {"spread_rate_mm_s": None, "spread_rate_reason": "no spread rate: " + "; ".join(out_of)}
    c = m["coefficients"]
    z = c["intercept"] + c["o2_pct"] * o2 + c["log10_flow"] * np.log10(flow) + c["log10_thickness"] * np.log10(th)
    q = m["interval"]
    return {
        "spread_rate_mm_s": round(float(10 ** z), 4),
        "spread_rate_interval_mm_s": [round(float(10 ** (z + q["residual_q05"])), 4), round(float(10 ** (z + q["residual_q95"])), 4)],
        "spread_rate_reason": None,
        "spread_rate_note": ("PMMA slab, opposed flow, if a flame spreads: OLS on 39 Table 5.1 spread rates (18 tests), "
                             f"LOTO RMSE {m['loto']['model']['rmse_log10']} log10 units vs baseline "
                             f"{m['loto']['baseline_mean']['rmse_log10']}; 90% interval from LOTO residuals"),
    }


if __name__ == "__main__":
    m = save()
    print(json.dumps({k: m[k] for k in ("data", "coefficients", "loto", "sensitivity_final_o2", "interval")}, indent=2))
