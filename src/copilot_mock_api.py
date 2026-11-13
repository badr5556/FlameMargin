"""Mock Prediction Engine for the FlameMargin Copilot (Layer 3).

WHY THIS FILE EXISTS
    When this was written, ``src/api.py`` (teammate A, Layer 1) did not exist yet.
    This module implements the agreed API contract with the same function
    names, so the Copilot can be built, tested and demoed end to end.
    ``src/copilot_tools.py`` uses the real ``src/api.py`` automatically as soon
    as it is importable and exposes the four contract functions.

HONESTY NOTE
    Every number produced here is SYNTHETIC. The formulas are only meant to
    behave plausibly: a U-shaped flammability boundary vs. flow, the limit
    rising at lower pressure, and wider uncertainty near the edge of the data.
    The experiment catalog uses ``MOCK-`` IDs and is NOT NASA data. Every
    result carries ``source = MOCK_SOURCE`` so the UI and the answers can say so.

CONTRACT (every function returns a dict with at least)
    value, interval, ood_flag, ood_reason, evidence
Units: O2 in percent (21 = 21 %), pressure in psia, flow in cm/s, spread rate
in mm/s. Gravity is a label: "micro" | "lunar" | "mars" | "earth".
"""

from __future__ import annotations

import math
from typing import Any

MOCK_SOURCE = "mock_api (synthetic placeholder, NOT NASA data)"

# Training envelope of the (mock) model. Inside CORE -> in-distribution,
# inside ENVELOPE but outside CORE -> partial coverage, outside -> OOD.
TRAINING_ENVELOPE = {
    "o2_percent": (15.0, 40.0),
    "pressure_psia": (7.5, 15.5),
    "flow_velocity_cm_s": (0.5, 50.0),
    "gravity": ("micro",),
}
CORE_REGION = {
    "o2_percent": (16.0, 30.0),
    "pressure_psia": (10.0, 15.5),
    "flow_velocity_cm_s": (1.0, 40.0),
}

# Synthetic per-material parameters.
#   loc_min: minimum limiting O2 (%) at 14.7 psia and the optimal flow, in µg.
#   rate:    spread-rate scale (mm/s).
MATERIALS: dict[str, dict[str, float]] = {
    "PMMA": {"loc_min": 16.5, "rate": 2.0},
    "Nomex": {"loc_min": 24.0, "rate": 1.0},
    "Cotton-fiberglass": {"loc_min": 15.5, "rate": 4.0},
    "Delrin": {"loc_min": 15.0, "rate": 1.5},
}

GRAVITY_G = {"micro": 0.0, "lunar": 0.166, "mars": 0.38, "earth": 1.0}

# Synthetic experiment catalog (IDs prefixed MOCK- on purpose).
_EXPERIMENTS: list[dict[str, Any]] = [
    {"id": "MOCK-BASS-II-03", "campaign": "BASS-II", "material": "PMMA", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 10.0, "outcome": "burn", "spread_rate_mm_s": 0.9},
    {"id": "MOCK-BASS-II-07", "campaign": "BASS-II", "material": "PMMA", "o2_percent": 17.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 5.0, "outcome": "extinguish", "spread_rate_mm_s": 0.0},
    {"id": "MOCK-BASS-II-12", "campaign": "BASS-II", "material": "PMMA", "o2_percent": 30.0, "pressure_psia": 10.2, "flow_velocity_cm_s": 15.0, "outcome": "burn", "spread_rate_mm_s": 2.6},
    {"id": "MOCK-BASS-II-15", "campaign": "BASS-II", "material": "Delrin", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 8.0, "outcome": "burn", "spread_rate_mm_s": 0.7},
    {"id": "MOCK-BASS-II-18", "campaign": "BASS-II", "material": "Nomex", "o2_percent": 30.0, "pressure_psia": 10.2, "flow_velocity_cm_s": 10.0, "outcome": "burn", "spread_rate_mm_s": 0.3},
    {"id": "MOCK-BASS-II-21", "campaign": "BASS-II", "material": "Nomex", "o2_percent": 24.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 10.0, "outcome": "extinguish", "spread_rate_mm_s": 0.0},
    {"id": "MOCK-BASS-II-24", "campaign": "BASS-II", "material": "Nomex", "o2_percent": 34.0, "pressure_psia": 8.2, "flow_velocity_cm_s": 5.0, "outcome": "burn", "spread_rate_mm_s": 0.6},
    {"id": "MOCK-SIBAL-02", "campaign": "SIBAL", "material": "Cotton-fiberglass", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 1.5, "outcome": "extinguish", "spread_rate_mm_s": 0.0},
    {"id": "MOCK-SIBAL-05", "campaign": "SIBAL", "material": "Cotton-fiberglass", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 5.0, "outcome": "burn", "spread_rate_mm_s": 1.2},
    {"id": "MOCK-SIBAL-09", "campaign": "SIBAL", "material": "Cotton-fiberglass", "o2_percent": 24.0, "pressure_psia": 10.2, "flow_velocity_cm_s": 3.0, "outcome": "burn", "spread_rate_mm_s": 1.6},
    {"id": "MOCK-SAFFIRE-01", "campaign": "Saffire", "material": "Cotton-fiberglass", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 20.0, "outcome": "burn", "spread_rate_mm_s": 1.9},
    {"id": "MOCK-SAFFIRE-04", "campaign": "Saffire", "material": "PMMA", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 20.0, "outcome": "burn", "spread_rate_mm_s": 0.8},
    {"id": "MOCK-SAFFIRE-06", "campaign": "Saffire", "material": "Nomex", "o2_percent": 21.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 20.0, "outcome": "extinguish", "spread_rate_mm_s": 0.0},
]

DEFAULT_FLOW_GRID = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0]


# --------------------------------------------------------------------------- #
# Internal synthetic physics
# --------------------------------------------------------------------------- #
def _loc(material: str, pressure_psia: float, flow: float) -> float:
    """Synthetic limiting O2 (%) vs. flow: quench branch at low flow, blow-off at high flow."""
    p = MATERIALS[material]
    u = max(flow, 0.05)
    pressure_term = 3.0 * math.log(14.7 / max(pressure_psia, 0.5))
    quench_term = 6.0 * (1.0 / u) ** 0.8
    blowoff_term = 0.004 * u**2
    return p["loc_min"] + pressure_term + quench_term + blowoff_term - 1.3


def _coverage(o2: float, pressure: float, flow: float | None, gravity: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if gravity not in TRAINING_ENVELOPE["gravity"]:
        reasons.append("no training data at this gravity level (FM2 not yet flown)")
    checks = [("o2_percent", o2, "O2", "%"), ("pressure_psia", pressure, "pressure", " psia")]
    if flow is not None:
        checks.append(("flow_velocity_cm_s", flow, "flow", " cm/s"))
    for key, val, label, unit in checks:
        lo, hi = TRAINING_ENVELOPE[key]
        if not lo <= val <= hi:
            reasons.append(f"{label} {val:g}{unit} outside training range {lo:g}–{hi:g}{unit}")
    if reasons:
        return "ood", reasons
    partial = False
    for key, val, *_ in checks:
        lo, hi = CORE_REGION[key]
        if not lo <= val <= hi:
            partial = True
    return ("partial" if partial else "in_distribution"), []


def _unknown_material(material: str) -> dict[str, Any]:
    return {
        "value": None,
        "interval": None,
        "ood_flag": True,
        "ood_reason": f"material '{material}' not in training data (known: {', '.join(MATERIALS)})",
        "evidence": [],
        "source": MOCK_SOURCE,
    }


def _nearest(material: str | None, o2: float, pressure: float, flow: float | None, k: int) -> list[dict[str, Any]]:
    rows = []
    for e in _EXPERIMENTS:
        d = ((e["o2_percent"] - o2) / 5.0) ** 2 + ((e["pressure_psia"] - pressure) / 3.0) ** 2
        if flow is not None:
            d += (math.log1p(e["flow_velocity_cm_s"]) - math.log1p(flow)) ** 2
        if material is not None and e["material"] != material:
            d += 4.0
        rows.append({**e, "distance": round(math.sqrt(d), 2), "synthetic": True})
    rows.sort(key=lambda r: r["distance"])
    return rows[:k]


# --------------------------------------------------------------------------- #
# Contract functions
# --------------------------------------------------------------------------- #
def predict(
    material: str,
    o2_percent: float,
    pressure_psia: float,
    flow_velocity_cm_s: float,
    gravity: str = "micro",
) -> dict[str, Any]:
    """Burn/extinguish classification + flame spread rate (mm/s) with a 90% interval."""
    if material not in MATERIALS:
        return _unknown_material(material)
    coverage, reasons = _coverage(o2_percent, pressure_psia, flow_velocity_cm_s, gravity)
    loc = _loc(material, pressure_psia, flow_velocity_cm_s)
    margin = o2_percent - loc
    scale = {"in_distribution": 1.2, "partial": 2.0, "ood": 3.5}[coverage]
    p_burn = 1.0 / (1.0 + math.exp(-margin / scale))
    half = {"in_distribution": 0.05, "partial": 0.12, "ood": 0.25}[coverage]
    p_lo, p_hi = max(0.0, p_burn - half), min(1.0, p_burn + half)

    label = "burn" if p_burn >= 0.5 else "extinguish"
    if label == "burn":
        u = flow_velocity_cm_s
        rate = MATERIALS[material]["rate"] * (max(margin, 0.5) / 10.0) * (pressure_psia / 14.7) ** 0.3 * (u / (u + 3.0))
        w = {"in_distribution": 0.25, "partial": 0.45, "ood": 0.8}[coverage]
        value, interval = round(rate, 2), [round(rate * (1 - w), 2), round(rate * (1 + w), 2)]
    else:
        value, interval = 0.0, [0.0, 0.0]

    near = _nearest(material, o2_percent, pressure_psia, flow_velocity_cm_s, k=3)
    return {
        "label": label,
        "burn_probability": round(p_burn, 2),
        "burn_probability_interval": [round(p_lo, 2), round(p_hi, 2)],
        "value": value,
        "unit": "mm/s",
        "quantity": "flame spread rate",
        "interval": interval,
        "interval_level": 0.9,
        "limiting_o2_percent": round(loc, 1),
        "o2_margin_percent_points": round(margin, 1),
        "coverage": coverage,
        "ood_flag": coverage == "ood",
        "ood_reason": "; ".join(reasons) or None,
        "evidence": [e["id"] for e in near],
        "source": MOCK_SOURCE,
    }


def flammability_boundary(
    material: str,
    pressure_psia: float,
    gravity: str = "micro",
    flow_velocities_cm_s: list[float] | None = None,
) -> dict[str, Any]:
    """Limiting O2 (%) vs. flow velocity. Above the curve the material burns."""
    if material not in MATERIALS:
        return _unknown_material(material)
    flows = flow_velocities_cm_s or DEFAULT_FLOW_GRID
    coverage, reasons = _coverage(25.0, pressure_psia, None, gravity)
    w = {"in_distribution": 0.8, "partial": 1.6, "ood": 3.0}[coverage]
    pts, band = [], []
    for u in flows:
        loc = round(_loc(material, pressure_psia, u), 1)
        pts.append({"flow_velocity_cm_s": u, "o2_percent_limit": loc})
        band.append([round(loc - w, 1), round(loc + w, 1)])
    best = min(pts, key=lambda p: p["o2_percent_limit"])
    return {
        "value": pts,
        "interval": band,
        "interval_level": 0.9,
        "min_o2_percent_limit": best["o2_percent_limit"],
        "flow_at_min_limit_cm_s": best["flow_velocity_cm_s"],
        "coverage": coverage,
        "ood_flag": coverage == "ood",
        "ood_reason": "; ".join(reasons) or None,
        "evidence": [e["id"] for e in _nearest(material, 25.0, pressure_psia, None, k=3)],
        "source": MOCK_SOURCE,
    }


def compare_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Run predict() on each scenario and report pairwise differences vs. the first."""
    results = []
    for s in scenarios:
        r = predict(
            s["material"], s["o2_percent"], s["pressure_psia"], s["flow_velocity_cm_s"], s.get("gravity", "micro")
        )
        results.append({"scenario": s.get("label") or f"scenario {len(results) + 1}", **r})
    base = results[0]
    deltas = []
    for r in results[1:]:
        d: dict[str, Any] = {"vs": base["scenario"], "scenario": r["scenario"]}
        if base.get("value") is not None and r.get("value") is not None:
            d["spread_rate_delta_mm_s"] = round(r["value"] - base["value"], 2)
            if base["value"] > 0:
                d["spread_rate_ratio"] = round(r["value"] / base["value"], 2)
        if base.get("burn_probability") is not None and r.get("burn_probability") is not None:
            d["burn_probability_delta"] = round(r["burn_probability"] - base["burn_probability"], 2)
        deltas.append(d)
    ood = [f"{r['scenario']}: {r['ood_reason']}" for r in results if r.get("ood_flag")]
    return {
        "value": results,
        "interval": [r.get("interval") for r in results],
        "deltas": deltas,
        "ood_flag": bool(ood),
        "ood_reason": "; ".join(ood) or None,
        "evidence": sorted({e for r in results for e in r.get("evidence", [])}),
        "source": MOCK_SOURCE,
    }


def nearest_experiments(
    material: str | None,
    o2_percent: float,
    pressure_psia: float,
    flow_velocity_cm_s: float | None = None,
    gravity: str = "micro",
    k: int = 3,
) -> dict[str, Any]:
    """The k closest experiments in the training set (normalized distance)."""
    coverage, reasons = _coverage(o2_percent, pressure_psia, flow_velocity_cm_s, gravity)
    rows = _nearest(material if material in MATERIALS else None, o2_percent, pressure_psia, flow_velocity_cm_s, k)
    if material is not None and material not in MATERIALS:
        reasons.append(f"material '{material}' not in training data")
    return {
        "value": rows,
        "interval": None,
        "ood_flag": bool(reasons),
        "ood_reason": "; ".join(reasons) or None,
        "evidence": [r["id"] for r in rows],
        "source": MOCK_SOURCE,
    }
