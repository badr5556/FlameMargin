"""FlameMargin Prediction Engine API (Layer 1). The team contract used by the Map and the Copilot.

Functions: ``predict``, ``flammability_boundary``, ``compare_scenarios``, ``nearest_experiments``.
Every output carries ``value, interval, ood_flag, ood_reason, evidence`` plus ``label``,
``burn_probability``, ``burn_probability_interval`` and ``unit``.

What the numbers are
    P(burn): probability that a flame is sustained on SIBAL cotton-fiberglass fabric
    at the given O2 and forced-flow speed, from a model trained on 21 observation
    points derived from 12 NASA BASS-II tests (NASA/TM-20210011385, Table 7.1;
    ISS, 1 atm, concurrent flow). Interval = 90% bootstrap over tests.
    Flame spread rate: not predicted (no spread-rate values in the extraction).

Out-of-distribution (OOD), hard rules first:
    material other than SIBAL; pressure outside 14.7 ± 0.3 psia; gravity other than
    microgravity; O2 outside 16.4–21.0%; flow outside 2.0–53 cm/s; sample width
    outside 1.2–2.2 cm. Any hard rule -> ``ood_flag=True`` and NO number is returned.
    Then a kNN distance check in standardized (O2, log10 flow, width) space: farther
    than the 95th percentile of leave-one-test-out nearest-neighbour distances ->
    ``ood_flag=True`` with ``ood_level="extrapolation"``; the number is returned but
    must be read as an extrapolation.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from src.features import DEFAULT_SAMPLE_WIDTH_CM, DISTANCE_FEATURES, RAW_CSV, feature_frame

# --------------------------------------------------------------------------- #
# Public constants
# --------------------------------------------------------------------------- #
SOURCE = (
    "FlameMargin Prediction Engine: model trained on 21 points from 12 NASA BASS-II SIBAL tests "
    "(NASA/TM-20210011385, Table 7.1)"
)
SPREAD_RATE_REASON = "no spread-rate measurements in the current NASA extraction"
GRAVITY_OOD_REASON = (
    "no training data at this gravity level (the dataset is ISS microgravity only; no long-duration fire "
    "experiment has been done in actual lunar gravity yet, NASA FM2 is planned to be the first)"
)

MATERIALS: dict[str, dict[str, Any]] = {
    "SIBAL": {
        "description": "SIBAL cotton-fiberglass fabric (BASS-II), 10 cm long, about 0.32 mm thick, 1.2 or 2.2 cm wide",
        "source": "NASA/TM-20210011385, Section 7.1, Table 7.1",
        "sample_widths_cm": [1.2, 2.2],
    }
}
_MATERIAL_ALIASES = {
    "sibal", "sibal fabric", "sibal cotton-fiberglass fabric", "sibal cotton fiberglass fabric",
    "cotton-fiberglass", "cotton fiberglass", "cotton/fiberglass", "cotton-fiberglass fabric",
    "cotton fiberglass fabric", "cotton-fibreglass", "cotton fibreglass",
}

TRAINING_ENVELOPE: dict[str, Any] = {
    "material": ("SIBAL",),
    "o2_percent": (16.4, 21.0),
    "pressure_psia": (14.4, 15.0),  # 14.7 psia (1 atm) ± 0.3 psia
    "flow_velocity_cm_s": (2.0, 53.0),
    "sample_width_cm": (1.2, 2.2),
    "gravity": ("micro",),
}

MISSION_PRESETS: dict[str, dict[str, Any]] = {
    "ISS cabin": {
        "short": "ISS",
        "pressure_psia": 14.7, "o2_percent": 21.0, "gravity": "micro", "gravity_g": 0.0,
        "source": "ISS nominal cabin atmosphere (team brief); 14.7 psia = 1 atm, the pressure of every BASS-II test in the data",
        "data_status": "inside the tested conditions (hard rules pass), but no test at 21% O2 reports a definitive outcome "
                       "in the extraction, so the kNN check flags it as an extrapolation",
    },
    "Artemis Exploration Atmosphere": {
        "short": "Artemis EA",
        "pressure_psia": 8.2, "o2_percent": 34.0, "gravity": "micro", "gravity_g": 0.0,
        "source": "NASA recommended Exploration Atmosphere, 8.2 psia / 34% O2 (claim C4, NTRS 20240003211)",
        "data_status": "out of distribution: 8.2 psia and 34% O2 are both outside the NASA data in this dataset",
    },
    "Lunar surface habitat": {
        "short": "Lunar",
        "pressure_psia": 8.2, "o2_percent": 34.0, "gravity": "lunar", "gravity_g": 0.166,
        "source": "Exploration Atmosphere (C4) at lunar gravity, 1/6 g; no long-duration lunar-gravity fire data yet (C10)",
        "data_status": "out of distribution: pressure, O2 and gravity are all outside the data",
    },
}

DEFAULT_FLOWS = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 30.0, 40.0, 53.0]
O2_GRID_STEP = 0.05
MAP_O2_RANGE = (16.0, 21.0)
MAP_FLOW_RANGE = (1.0, 60.0)


# --------------------------------------------------------------------------- #
# Engine (loaded once)
# --------------------------------------------------------------------------- #
class _Engine:
    def __init__(self, art: dict[str, Any]):
        self.art = art
        self.model = art["final_model"]
        self.boots = art["bootstrap_models"]
        self.level = float(art["interval_level"])
        d = art["distance"]
        self.mu, self.sd = np.asarray(d["mean"]), np.asarray(d["std"])
        self.Z = np.asarray(d["train_z"])
        self.threshold = float(d["threshold"])
        pts = pd.DataFrame(art["points"])
        raw = pd.read_csv(RAW_CSV, dtype={"test_id": "string"}).set_index("test_id")
        pts["campaign"] = pts["test_id"].map(raw["campaign"])
        pts["event"] = pts["test_id"].map(raw["conservative_event_label"])
        pts["reported_comment"] = pts["test_id"].map(raw["reported_comment"]).fillna("")
        self.points = pts
        self.metrics = art["metrics"]

    # -- probabilities ---------------------------------------------------- #
    def proba(self, F: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(F[self.art["features"]])[:, 1]

    def proba_with_interval(self, F: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        from src.model import bootstrap_interval

        p = self.proba(F)
        lo, hi = bootstrap_interval(self.boots, F, self.level)
        # The full-data fit can sit just outside the bootstrap band; extend the band to contain it.
        return p, np.minimum(lo, p), np.maximum(hi, p)

    # -- distance --------------------------------------------------------- #
    def distance(self, o2, flow, width) -> np.ndarray:
        F = feature_frame(o2, flow, width)[DISTANCE_FEATURES].to_numpy()
        Zq = (F - self.mu) / self.sd
        return np.sqrt(((Zq[:, None, :] - self.Z[None, :, :]) ** 2).sum(-1)).min(axis=1)


@lru_cache(maxsize=1)
def get_engine() -> _Engine:
    from src.model import load_artifact

    return _Engine(load_artifact())


def model_info() -> dict[str, Any]:
    """Model name, LOTO metrics and settings (for the UI's Data & Method tab)."""
    e = get_engine()
    return {
        "chosen_model": e.art["chosen_model"], "model_label": e.art["model_label"],
        "interval_level": e.level, "knn_threshold": round(e.threshold, 3),
        "n_bootstrap": len(e.boots), "metrics": e.metrics,
        "retrained_at_load": bool(e.art.get("retrained_at_load")),
    }


# --------------------------------------------------------------------------- #
# Input normalization + hard OOD rules
# --------------------------------------------------------------------------- #
def canonical_material(material: Any) -> str | None:
    s = re.sub(r"\s+", " ", str(material or "").strip().lower())
    if s in _MATERIAL_ALIASES or s.startswith("sibal"):
        return "SIBAL"
    return None


def gravity_label(gravity: Any) -> str:
    if gravity is None or gravity == "":
        return "micro"
    if isinstance(gravity, (int, float)) and not isinstance(gravity, bool):
        g = float(gravity)
        if g < 1e-3:
            return "micro"
        for label, gv in (("lunar", 0.166), ("mars", 0.38), ("earth", 1.0)):
            if abs(g - gv) / gv < 0.05:
                return label
        return f"{g:g} g"
    s = str(gravity).strip().lower()
    for label, keys in (
        ("micro", ("micro", "µg", "μg", "ug", "zero", "0 g", "0g", "orbit", "iss", "weightless")),
        ("lunar", ("lunar", "moon", "1/6")),
        ("mars", ("mars", "martian")),
        ("earth", ("earth", "1 g", "1g", "ground", "normal gravity")),
    ):
        if any(k in s for k in keys):
            return label
    return s


def _range_reason(label: str, val: float, key: str, unit: str) -> str | None:
    lo, hi = TRAINING_ENVELOPE[key]
    if lo <= val <= hi:
        return None
    return f"{label} {val:g}{unit} outside training range {lo:g}–{hi:g}{unit}"


def hard_rule_reasons(material: Any = "SIBAL", o2_percent: float | None = None, pressure_psia: float | None = 14.7,
                      flow_velocity_cm_s: float | None = None, gravity: Any = "micro",
                      sample_width_cm: float | None = DEFAULT_SAMPLE_WIDTH_CM) -> list[str]:
    """Every hard rule that triggers, each with an explicit reason. Empty list = inside the envelope."""
    reasons: list[str] = []
    if canonical_material(material) is None:
        reasons.append(f"material '{material}' not in training data (only SIBAL cotton-fiberglass fabric was tested in this dataset)")
    if pressure_psia is not None:
        r = _range_reason("pressure", float(pressure_psia), "pressure_psia", " psia")
        if r:
            reasons.append(r)
    if gravity_label(gravity) != "micro":
        reasons.append(GRAVITY_OOD_REASON)
    if o2_percent is not None:
        r = _range_reason("O2", float(o2_percent), "o2_percent", "%")
        if r:
            reasons.append(r)
    if flow_velocity_cm_s is not None:
        r = _range_reason("flow", float(flow_velocity_cm_s), "flow_velocity_cm_s", " cm/s")
        if r:
            reasons.append(r)
    if sample_width_cm is not None:
        r = _range_reason("sample width", float(sample_width_cm), "sample_width_cm", " cm")
        if r:
            reasons.append(r)
    return reasons


def _knn_reason(dist: float, threshold: float) -> str:
    return (f"far from labelled NASA tests: kNN distance {dist:.2f} > threshold {threshold:.2f} "
            "(95th percentile of leave-one-test-out distances); treat P(burn) as an extrapolation")


def _ood_block(hard: list[str], knn_reasons: list[str]) -> dict[str, Any]:
    reasons = hard + knn_reasons
    level = "out_of_envelope" if hard else ("extrapolation" if knn_reasons else "in_distribution")
    return {
        "ood_flag": bool(reasons), "ood_reason": "; ".join(reasons) or None, "ood_reasons": reasons,
        "ood_level": level, "coverage": level, "hard_rule_reasons": hard,
    }


EXTRAPOLATION_INTERVAL_NOTE = (
    "extrapolation: the Gaussian process reverts to its prior (P(burn) = 0.5) far from the data, so 0.5 here means "
    "'no information', not '50% risk'; the interval is reported as [0, 1]"
)


def _label(p: float) -> str:
    """burn if P(burn) >= 0.5 at 2-decimal precision: an exact tie counts as burn (conservative for fire safety)."""
    return "burn" if round(float(p), 2) >= 0.5 else "extinguish"


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


# --------------------------------------------------------------------------- #
# nearest_experiments
# --------------------------------------------------------------------------- #
_OBSERVATION = {
    "R1": "flame present before the flow ramp", "R2": "flame present before the flow ramp",
    "R3": "flame survived the flow increase", "R4": "no ignition",
}


def _experiment_rows(o2: float, flow: float | None, width: float, k: int) -> list[dict[str, Any]]:
    e = get_engine()
    pts = e.points
    cols = [0, 2] if flow is None else [0, 1, 2]
    q = feature_frame(o2, flow if flow is not None else 10.0, width)[DISTANCE_FEATURES].to_numpy()[0]
    zq = ((q - e.mu) / e.sd)[cols]
    d = np.sqrt(((e.Z[:, cols] - zq) ** 2).sum(axis=1))
    order = np.argsort(d, kind="stable")
    rows, seen = [], set()
    for i in order:
        p = pts.iloc[int(i)]
        if p["test_id"] in seen:
            continue
        seen.add(p["test_id"])
        rule = str(p["derivation_rule"]).split(" ")[0]
        burn = int(p["burn"]) == 1
        event = str(p["event"]) if p["event"] != "not_reported" else str(p["reported_comment"]).lower() or "not reported"
        rows.append({
            "id": p["test_id"], "point_id": p["point_id"], "campaign": p["campaign"],
            "material": "SIBAL cotton-fiberglass fabric", "o2_percent": float(p["o2_pct"]), "pressure_psia": 14.7,
            "flow_velocity_cm_s": float(p["flow_cm_s"]), "sample_width_cm": float(p["sample_width_cm"]),
            "outcome": "burn" if burn else "extinguish",
            "observation": _OBSERVATION.get(rule, "") if burn or rule == "R4" else f"{event} at this flow",
            "test_event": event, "derivation_rule": p["derivation_rule"],
            "source": p["source"], "source_page": p["source_page"], "distance": round(float(d[i]), 2),
        })
        if len(rows) >= k:
            break
    return rows


def nearest_experiments(material: str | None = "SIBAL", o2_percent: float = 21.0, pressure_psia: float = 14.7,
                        flow_velocity_cm_s: float | None = None, gravity: str = "micro", k: int = 3,
                        sample_width_cm: float = DEFAULT_SAMPLE_WIDTH_CM) -> dict[str, Any]:
    """The k closest labelled NASA tests (one row per test) in standardized (O2, log10 flow, width) space."""
    k = max(1, min(int(k), 12))
    hard = hard_rule_reasons(material if material is not None else "SIBAL", o2_percent, pressure_psia,
                             flow_velocity_cm_s, gravity, sample_width_cm)
    flow = float(flow_velocity_cm_s) if flow_velocity_cm_s not in (None, "") and float(flow_velocity_cm_s) > 0 else None
    rows = _experiment_rows(float(o2_percent), flow, float(sample_width_cm), k)
    return {
        "value": rows, "interval": None, "unit": "standardized distance", "label": None,
        "burn_probability": None, "burn_probability_interval": None,
        **_ood_block(hard, []),
        "evidence": [r["id"] for r in rows],
        "note": "Distances use standardized O2, log10 flow and sample width" + ("" if flow else " (no flow given: O2 and width only)") + ".",
        "source": SOURCE,
    }


# --------------------------------------------------------------------------- #
# predict
# --------------------------------------------------------------------------- #
def _no_number(hard: list[str], evidence_rows: list[dict[str, Any]], inputs: dict[str, Any], why: str) -> dict[str, Any]:
    return {
        "label": None, "burn_probability": None, "burn_probability_interval": None, "interval_level": None,
        "value": None, "interval": None, "unit": "probability", "quantity": "P(burn)",
        "spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON,
        **_ood_block(hard, []),
        "note": why,
        "evidence": [r["id"] for r in evidence_rows], "nearest_experiments": evidence_rows,
        "inputs": inputs, "source": SOURCE,
    }


def predict(material: str = "SIBAL", o2_percent: float = 21.0, pressure_psia: float = 14.7,
            flow_velocity_cm_s: float | None = None, gravity: str = "micro",
            sample_width_cm: float = DEFAULT_SAMPLE_WIDTH_CM) -> dict[str, Any]:
    """P(burn) with a 90% bootstrap interval for one condition. Spread rate is not predicted."""
    inputs = {"material": material, "o2_percent": o2_percent, "pressure_psia": pressure_psia,
              "flow_velocity_cm_s": flow_velocity_cm_s, "gravity": gravity_label(gravity), "sample_width_cm": sample_width_cm}
    if flow_velocity_cm_s in (None, "") or float(flow_velocity_cm_s) <= 0:
        return _no_number([], [], inputs, "flow_velocity_cm_s (> 0 cm/s) is required for a prediction; use flammability_boundary to cover all flows")
    o2, flow, width = float(o2_percent), float(flow_velocity_cm_s), float(sample_width_cm)
    hard = hard_rule_reasons(material, o2, pressure_psia, flow, gravity, width)
    near = _experiment_rows(o2, flow, width, 3)
    if hard:
        return _no_number(hard, near, inputs, "No prediction outside the tested conditions: the model has no data there. Do not estimate one.")
    e = get_engine()
    F = feature_frame(o2, flow, width)
    p, lo, hi = (float(a[0]) for a in e.proba_with_interval(F))
    dist = float(e.distance(o2, flow, width)[0])
    knn = [_knn_reason(dist, e.threshold)] if dist > e.threshold else []
    raw_band = [_r(lo), _r(hi)]
    band = [0.0, 1.0] if knn else raw_band
    return {
        "label": "uncertain" if knn else _label(p),
        "burn_probability": _r(p), "burn_probability_interval": band, "interval_level": e.level,
        "value": _r(p), "interval": band, "unit": "probability",
        "interval_note": EXTRAPOLATION_INTERVAL_NOTE if knn else "90% bootstrap interval over NASA tests",
        "bootstrap_interval_raw": raw_band,
        "quantity": "P(burn): probability that a flame is sustained",
        "spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON,
        **_ood_block([], knn),
        "knn_distance": _r(dist), "knn_threshold": _r(e.threshold),
        "evidence": [r["id"] for r in near], "nearest_experiments": near,
        "model": e.art["model_label"], "inputs": inputs, "source": SOURCE,
    }


# --------------------------------------------------------------------------- #
# flammability_boundary
# --------------------------------------------------------------------------- #
def _lowest_burning_o2(o2_grid: np.ndarray, p: np.ndarray) -> float | None:
    idx = np.flatnonzero(p >= 0.5)
    return float(o2_grid[idx[0]]) if len(idx) else None


@lru_cache(maxsize=32)
def _boundary_surfaces(sample_width_cm: float, flows: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """P(burn), lower and upper band on the (O2 grid x flows) mesh; cached (the model is fixed)."""
    e = get_engine()
    lo_o2, hi_o2 = TRAINING_ENVELOPE["o2_percent"]
    o2_grid = np.round(np.arange(lo_o2, hi_o2 + 1e-9, O2_GRID_STEP), 3)
    OO, FF = np.meshgrid(o2_grid, flows, indexing="ij")
    p, lo, hi = e.proba_with_interval(feature_frame(OO.ravel(), FF.ravel(), sample_width_cm))
    return p.reshape(OO.shape), lo.reshape(OO.shape), hi.reshape(OO.shape)


@lru_cache(maxsize=4)
def _cached_grid(sample_width_cm: float) -> dict[str, Any]:
    return _boundary_grid_uncached(sample_width_cm)


def boundary_grid(sample_width_cm: float = DEFAULT_SAMPLE_WIDTH_CM) -> dict[str, Any]:
    """P(burn) grid over O2 16–21% x flow 1–60 cm/s (log) with bootstrap bands and in-distribution mask (cached)."""
    return _cached_grid(float(sample_width_cm))


def _boundary_grid_uncached(sample_width_cm: float = DEFAULT_SAMPLE_WIDTH_CM, n_o2: int = 51, n_flow: int = 61) -> dict[str, Any]:
    """P(burn) grid over O2 16–21% x flow 1–60 cm/s (log) with bootstrap bands and in-distribution mask."""
    e = get_engine()
    o2 = np.round(np.linspace(*MAP_O2_RANGE, n_o2), 3)
    flow = np.round(np.logspace(np.log10(MAP_FLOW_RANGE[0]), np.log10(MAP_FLOW_RANGE[1]), n_flow), 4)
    OO, FF = np.meshgrid(o2, flow, indexing="ij")
    F = feature_frame(OO.ravel(), FF.ravel(), sample_width_cm)
    p, lo, hi = e.proba_with_interval(F)
    dist = e.distance(OO.ravel(), FF.ravel(), sample_width_cm)
    (o2lo, o2hi), (flo, fhi) = TRAINING_ENVELOPE["o2_percent"], TRAINING_ENVELOPE["flow_velocity_cm_s"]
    hard_ok = (OO.ravel() >= o2lo) & (OO.ravel() <= o2hi) & (FF.ravel() >= flo) & (FF.ravel() <= fhi)
    shape = OO.shape
    return {
        "o2_percent": o2.tolist(), "flow_velocity_cm_s": flow.tolist(), "sample_width_cm": sample_width_cm,
        "p_burn": p.reshape(shape).round(4).tolist(), "p_lo": lo.reshape(shape).round(4).tolist(),
        "p_hi": hi.reshape(shape).round(4).tolist(),
        "knn_distance": dist.reshape(shape).round(3).tolist(),
        "inside_hard_envelope": hard_ok.reshape(shape).tolist(),
        "in_distribution": (hard_ok & (dist <= e.threshold)).reshape(shape).tolist(),
        "knn_threshold": e.threshold, "interval_level": e.level,
    }


def flammability_boundary(material: str = "SIBAL", pressure_psia: float = 14.7, gravity: str = "micro",
                          flow_velocities_cm_s: list[float] | None = None, o2_percent: float | None = None,
                          sample_width_cm: float = DEFAULT_SAMPLE_WIDTH_CM, include_grid: bool = False) -> dict[str, Any]:
    """The 0.5 contour of P(burn): lowest O2 (in 16.4–21.0%) at which P(burn) >= 0.5, per flow.

    ``value`` = [{"flow_velocity_cm_s", "o2_percent_limit", "limit_status", ...}], ``interval`` = one
    [lo, hi] O2 band per flow from the bootstrap. With ``o2_percent``, also P(burn) at that O2 per flow
    and the flows where it is >= 0.5. ``include_grid=True`` adds the full map grid (UI only).
    """
    hard = hard_rule_reasons(material, None, pressure_psia, None, gravity, sample_width_cm)
    o2_hard = _range_reason("O2", float(o2_percent), "o2_percent", "%") if o2_percent not in (None, "") else None
    if hard:
        out = _no_number(hard + ([o2_hard] if o2_hard else []), [], {"material": material, "pressure_psia": pressure_psia,
                         "gravity": gravity_label(gravity), "o2_percent": o2_percent}, "No boundary outside the tested conditions.")
        out["value"] = None
        return out
    e = get_engine()
    flows = [float(f) for f in (flow_velocities_cm_s or DEFAULT_FLOWS) if float(f) > 0]
    lo_o2, hi_o2 = TRAINING_ENVELOPE["o2_percent"]
    o2_grid = np.round(np.arange(lo_o2, hi_o2 + 1e-9, O2_GRID_STEP), 3)
    pts, band, flow_reasons = [], [], []
    P_all, LO_all, HI_all = _boundary_surfaces(float(sample_width_cm), tuple(flows))
    for j, f in enumerate(flows):
        p, plo, phi = P_all[:, j], LO_all[:, j], HI_all[:, j]
        lim = _lowest_burning_o2(o2_grid, p)
        status = ("burns_at_all_tested_o2" if lim == o2_grid[0] else "crossing") if lim is not None else "no_burn_in_tested_o2"
        f_reason = _range_reason("flow", f, "flow_velocity_cm_s", " cm/s")
        if f_reason:
            flow_reasons.append(f_reason)
        point = {"flow_velocity_cm_s": f, "o2_percent_limit": lim, "limit_status": status, "inside_hard_envelope": f_reason is None}
        if lim is not None:
            point["in_distribution_at_limit"] = bool(e.distance(lim, f, sample_width_cm)[0] <= e.threshold) and f_reason is None
        pts.append(point)
        band.append([_lowest_burning_o2(o2_grid, phi), _lowest_burning_o2(o2_grid, plo)])
    crossing = [p for p in pts if p["o2_percent_limit"] is not None]
    best = min(crossing, key=lambda p: p["o2_percent_limit"]) if crossing else None
    knn: list[str] = []
    res: dict[str, Any] = {
        "value": pts, "interval": band, "interval_level": e.level, "unit": "O2 %",
        "quantity": "lowest O2 (%) in 16.4–21.0% where P(burn) >= 0.5, per flow",
        "label": None, "burn_probability": None, "burn_probability_interval": None,
        "min_o2_percent_limit": best["o2_percent_limit"] if best else None,
        "flow_at_min_limit_cm_s": best["flow_velocity_cm_s"] if best else None,
        "spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON,
        "note": "o2_percent_limit = None means P(burn) < 0.5 at every O2 from 16.4% to 21.0% at that flow. "
                "Limit statuses: crossing | burns_at_all_tested_o2 | no_burn_in_tested_o2.",
    }
    if o2_percent not in (None, ""):
        o2 = float(o2_percent)
        res["at_o2_percent"] = o2
        if o2_hard:
            res.update({"flows_where_flammable_cm_s": None, "flows_where_not_flammable_cm_s": None, "flammable_at_some_flow": None})
        else:
            F = feature_frame(o2, flows, sample_width_cm)
            p, plo, phi = e.proba_with_interval(F)
            d = e.distance(o2, flows, sample_width_cm)
            for pt, pi, li, hi_, di in zip(pts, p, plo, phi, d):
                far_here = di > e.threshold
                pt.update({"p_burn_at_o2": _r(pi), "p_burn_interval_at_o2": [0.0, 1.0] if far_here else [_r(li), _r(hi_)],
                           "knn_distance_at_o2": _r(di), "extrapolation_at_o2": bool(far_here)})
            near_ok = [(f, pi) for f, pi, di in zip(flows, p, d) if di <= e.threshold]
            far = [f for f, di in zip(flows, d) if di > e.threshold]
            res["flows_where_flammable_cm_s"] = [f for f, pi in near_ok if _label(pi) == "burn"]
            res["flows_where_not_flammable_cm_s"] = [f for f, pi in near_ok if _label(pi) == "extinguish"]
            res["flows_extrapolated_cm_s"] = far
            # No verdict from extrapolated flows: if every flow is far from the data, the answer is "unknown".
            res["flammable_at_some_flow"] = bool(res["flows_where_flammable_cm_s"]) if near_ok else None
            if far:
                knn.append(f"far from labelled NASA tests at {o2:g}% O2 for flows {', '.join(f'{f:g}' for f in far)} cm/s "
                           f"(kNN distance > threshold {e.threshold:.2f}); treat those P(burn) values as extrapolations")
            res["comparison_note"] = (f"At {o2:g}% O2, P(burn) >= 0.5 at the flows in flows_where_flammable_cm_s and < 0.5 at the "
                                      "flows in flows_where_not_flammable_cm_s; flows in flows_extrapolated_cm_s are too far from "
                                      "the labelled NASA tests for a verdict (computed in code).")
    res.update(_ood_block(([o2_hard] if o2_hard else []) + flow_reasons, knn))
    res["evidence"] = [r["id"] for r in _experiment_rows(float(o2_percent) if o2_percent not in (None, "") and not o2_hard else 18.0,
                                                         res["flow_at_min_limit_cm_s"] or 10.0, float(sample_width_cm), 3)]
    res["model"], res["source"] = e.art["model_label"], SOURCE
    if include_grid:
        res["grid"] = boundary_grid(sample_width_cm)
    return res


# --------------------------------------------------------------------------- #
# compare_scenarios
# --------------------------------------------------------------------------- #
def _resolve_preset(name: str) -> dict[str, Any] | None:
    low = (name or "").strip().lower()
    for k, v in MISSION_PRESETS.items():
        if low in (k.lower(), v["short"].lower()) or (low and low.split()[0] in k.lower()):
            return {"preset": k, **v}
    return None


def compare_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """predict() for each scenario (presets allowed via "preset") + P(burn) deltas vs the first."""
    results = []
    for i, s in enumerate(scenarios):
        s = dict(s)
        if s.get("preset"):
            p = _resolve_preset(s["preset"]) or {}
            for key in ("o2_percent", "pressure_psia", "gravity"):
                s.setdefault(key, p.get(key))
        r = predict(s.get("material", "SIBAL"), s.get("o2_percent", 21.0), s.get("pressure_psia", 14.7),
                    s.get("flow_velocity_cm_s"), s.get("gravity", "micro"), s.get("sample_width_cm", DEFAULT_SAMPLE_WIDTH_CM))
        results.append({"scenario": s.get("label") or s.get("preset") or f"scenario {i + 1}", **r})
    base = results[0]
    deltas = []
    for r in results[1:]:
        d: dict[str, Any] = {"vs": base["scenario"], "scenario": r["scenario"]}
        if base.get("burn_probability") is not None and r.get("burn_probability") is not None:
            d["burn_probability_delta"] = round(r["burn_probability"] - base["burn_probability"], 2)
        else:
            d["note"] = "no delta: at least one scenario has no prediction (out of the tested conditions)"
        deltas.append(d)
    reasons = [f"{r['scenario']}: {x}" for r in results for x in r.get("ood_reasons", [])]
    hard = [f"{r['scenario']}: {x}" for r in results for x in r.get("hard_rule_reasons", [])]
    knn = [x for x in reasons if x not in hard]
    return {
        "value": results, "interval": [r.get("interval") for r in results], "deltas": deltas,
        "label": None, "burn_probability": None, "burn_probability_interval": None, "unit": "probability",
        **_ood_block(hard, knn),
        "evidence": sorted({e for r in results for e in r.get("evidence", [])}), "source": SOURCE,
    }
