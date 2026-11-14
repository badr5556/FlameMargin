"""FlameMargin Prediction Engine API v2 (Layer 1). The team contract used by the Map and the Copilot.

Functions: ``predict``, ``flammability_boundary``, ``compare_scenarios``, ``nearest_experiments``.
Every output carries ``value, interval, ood_flag, ood_reason, evidence`` plus ``label``,
``burn_probability``, ``burn_probability_interval`` and ``unit``.

What the numbers are
    P(burn): probability that a flame is sustained at the given material, O2 and forced-flow speed, in ISS
    microgravity at 1 atm, from a model trained on observation points derived from all BASS-II tests of
    NASA/TM-20210011385 (Appendix A Tables A.1-A.6, Table 7.1, Table 5.1). Five material families:
    SIBAL fabric, PMMA film, PMMA slab, PMMA rod, Nomex. Interval = 90% bootstrap over tests.

Out-of-distribution (OOD), hard rules first (each adds its own reason; any hard rule -> NO number):
    material not in the data; pressure outside 14.7 ± 0.3 psia; gravity other than microgravity;
    flow configuration never tested for that material; O2, flow, thickness or size outside that material's
    tested ranges. Then a kNN check against the same material's training points: farther than the 95th
    percentile of leave-one-test-out nearest-neighbour distances -> ``ood_level="extrapolation"``, the number is
    returned with the interval [0, 1] and label "uncertain".
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.model_v2 import (CONFIGS, FAMILIES, FAMILY_LABELS, METRICS_V2, SIZE_KIND, bootstrap_interval, feature_frame_v2,
                          load_artifact_v2)

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Public constants
# --------------------------------------------------------------------------- #
def _metrics_v2() -> dict[str, Any]:
    try:
        return json.loads(METRICS_V2.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"data": {"n_points": None, "n_tests": None}}


_M = _metrics_v2()
SOURCE = (f"FlameMargin Prediction Engine v2: model trained on {_M['data']['n_points']} points from {_M['data']['n_tests']} "
          "NASA BASS-II tests (NASA/TM-20210011385, Appendix A Tables A.1-A.6, Table 7.1, Table 5.1)")
SPREAD_RATE_REASON = "spread rate is only modelled for PMMA slabs (Table 5.1); none is predicted for this material or condition"
GRAVITY_OOD_REASON = (
    "no training data at this gravity level (the dataset is ISS microgravity only; no long-duration fire "
    "experiment has been done in actual lunar gravity yet, NASA FM2 is planned to be the first)"
)

# Display name -> family, description, defaults (defaults are the most common value in the training points).
MATERIALS: dict[str, dict[str, Any]] = {
    "SIBAL fabric": {"family": "SIBAL_fabric", "description": "SIBAL cotton-fiberglass fabric (75% cotton, 25% fiberglass), "
                     "about 0.32 mm thick, 1.2 or 2.2 cm wide; concurrent flow", "source": "Table 7.1 (p. 96) and Table A.6"},
    "PMMA film": {"family": "PMMA_film", "description": "thin PMMA film, 0.1–0.4 mm, 1 or 2 cm wide; opposed flow",
                  "source": "Table A.1 (Bhattacharjee, pp. 103–104)"},
    "PMMA slab": {"family": "PMMA_slab", "description": "PMMA slab, 1–5 mm thick, 1.2 or 2.2 cm wide; opposed flow",
                  "source": "Table A.4 and Table 5.1 (Miller, pp. 57, 108–109)"},
    "PMMA rod": {"family": "PMMA_rod", "description": "cast PMMA rod, 6.35–12.7 mm diameter, black or clear; opposed, "
                 "concurrent or stagnation flow", "source": "Tables A.3 and A.5 (Fernandez-Pello, Olson, pp. 106–107, 110–111)"},
    "Nomex": {"family": "Nomex", "description": "Nomex III (DuPont) natural fabric; concurrent flow; 3 tests, none sustained a flame",
              "source": "Table A.2 (Ferkul, p. 105)"},
}
FAMILY_TO_NAME = {v["family"]: k for k, v in MATERIALS.items()}

_ALIASES: list[tuple[str, list[str]]] = [  # order matters: specific before generic
    ("SIBAL fabric", ["sibal", "sibal fabric", "sibal cotton-fiberglass fabric", "sibal cotton fiberglass fabric",
                      "cotton-fiberglass", "cotton fiberglass", "cotton/fiberglass", "cotton-fiberglass fabric",
                      "cotton fiberglass fabric", "cotton-fibreglass", "cotton fibreglass", "sibal_fabric"]),
    ("PMMA film", ["pmma film", "pmma_film", "thin pmma", "thin pmma film", "acrylic film", "pmma thin film", "thin film pmma"]),
    ("PMMA rod", ["pmma rod", "pmma_rod", "acrylic rod", "pmma cylinder", "pmma rods", "cast pmma rod"]),
    ("PMMA slab", ["pmma slab", "pmma_slab", "pmma sheet", "pmma plate", "acrylic slab", "acrylic sheet", "pmma", "acrylic",
                   "plexiglass", "plexiglas", "perspex", "lucite", "polymethyl methacrylate", "polymethylmethacrylate",
                   "cast pmma", "black pmma", "clear pmma"]),
    ("Nomex", ["nomex", "nomex iii", "nomex 3", "nomex®", "nomex(r)", "nomex natural", "nomex iii fabric", "nomex fabric"]),
]
GENERIC_PMMA = {"pmma", "acrylic", "plexiglass", "plexiglas", "perspex", "lucite", "polymethyl methacrylate",
                "polymethylmethacrylate", "cast pmma", "black pmma", "clear pmma"}
GENERIC_PMMA_NOTE = ("generic 'PMMA'/'acrylic' is mapped to PMMA slab (1–5 mm); give thickness_mm < 1 for film or a "
                     "diameter_mm for rod")

MISSION_PRESETS: dict[str, dict[str, Any]] = {
    "ISS cabin": {
        "short": "ISS",
        "pressure_psia": 14.7, "o2_percent": 21.0, "gravity": "micro", "gravity_g": 0.0,
        "source": "ISS nominal cabin atmosphere (team brief); 14.7 psia = 1 atm, the pressure of the BASS-II tests",
        "data_status": "in distribution for SIBAL fabric, PMMA film, PMMA slab and Nomex near their tested flows "
                       "(O2 21% is inside their tested ranges); out of distribution for PMMA rods (tested only up to 20.8% O2)",
    },
    "Artemis Exploration Atmosphere": {
        "short": "Artemis EA",
        "pressure_psia": 8.2, "o2_percent": 34.0, "gravity": "micro", "gravity_g": 0.0,
        "source": "NASA recommended Exploration Atmosphere, 8.2 psia / 34% O2 (claim C4, NTRS 20240003211)",
        "data_status": "out of distribution for every material: 8.2 psia and 34% O2 are both outside the BASS-II data",
    },
    "Lunar surface habitat": {
        "short": "Lunar",
        "pressure_psia": 8.2, "o2_percent": 34.0, "gravity": "lunar", "gravity_g": 0.166,
        "source": "Exploration Atmosphere (C4) at lunar gravity, 1/6 g; no long-duration lunar-gravity fire data yet (C10)",
        "data_status": "out of distribution: pressure, O2 and gravity are all outside the data",
    },
}

PRESSURE_RANGE = (14.4, 15.0)  # 14.7 psia (1 atm) ± 0.3 psia
DEFAULT_FLOWS = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0, 53.0]
O2_GRID_STEP = 0.05
MAP_O2_RANGE = (13.0, 23.0)
MAP_FLOW_RANGE = (0.4, 60.0)


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
        self.Zfam = np.asarray(d["family"])
        self.threshold = float(d["threshold"])
        self.env = art["envelopes"]
        self.stats = art["size_stats"]
        self.points = pd.DataFrame(art["points"])
        self.metrics = art["metrics"]
        self.defaults = self._defaults()

    def _defaults(self) -> dict[str, dict[str, Any]]:
        out = {}
        for fam in FAMILIES:
            f = self.points[self.points["material_family"] == fam]
            th = pd.to_numeric(f["thickness_mm"], errors="coerce").dropna()
            kind = SIZE_KIND[fam]
            sz = pd.to_numeric(f[kind], errors="coerce").dropna() if kind else pd.Series(dtype=float)
            out[fam] = {
                "flow_configuration": f["flow_configuration"].mode().iloc[0],
                "thickness_mm": float(th.mode().iloc[0]) if len(th) else None,
                "size": float(sz.mode().iloc[0]) if len(sz) else None, "size_kind": kind,
            }
        return out

    def frame(self, o2, flow, fam, cfg, th, size) -> pd.DataFrame:
        return feature_frame_v2(o2, flow, fam, cfg, th, size, self.stats)

    def proba_with_interval(self, F: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        p = self.model.proba(F)
        lo, hi = bootstrap_interval(self.boots, F, self.level)
        return p, np.minimum(lo, p), np.maximum(hi, p)

    def distance(self, F: pd.DataFrame, fam: str) -> np.ndarray:
        Zq = (F[["o2_pct", "log10_flow", "size_z", "log10_thickness"]].to_numpy() - self.mu) / self.sd
        Zf = self.Z[self.Zfam == fam]
        if len(Zf) == 0:
            return np.full(len(Zq), np.inf)
        return np.sqrt(((Zq[:, None, :] - Zf[None, :, :]) ** 2).sum(-1)).min(axis=1)


@lru_cache(maxsize=1)
def get_engine() -> _Engine:
    return _Engine(load_artifact_v2())


def model_info() -> dict[str, Any]:
    """Model name, LOTO metrics and settings (for the UI's Data & Method tab)."""
    e = get_engine()
    return {
        "chosen_model": e.art["chosen_model"], "model_label": e.art["model_label"], "interval_level": e.level,
        "knn_threshold": round(e.threshold, 3), "n_bootstrap": len(e.boots), "metrics": e.metrics,
        "retrained_at_load": bool(e.art.get("retrained_at_load")), "envelopes": e.env,
    }


# --------------------------------------------------------------------------- #
# Input normalization
# --------------------------------------------------------------------------- #
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def canonical_material(material: Any, thickness_mm: float | None = None, diameter_mm: float | None = None) -> str | None:
    """Display name of the material ("SIBAL fabric", "PMMA film", "PMMA slab", "PMMA rod", "Nomex") or None."""
    s = _norm(material)
    if not s:
        return None
    for name in MATERIALS:
        if s == name.lower():
            return name
    for name, aliases in _ALIASES:
        if s in aliases or (name == "SIBAL fabric" and s.startswith("sibal")):
            if name == "PMMA slab" and s in GENERIC_PMMA:
                if diameter_mm not in (None, ""):
                    return "PMMA rod"
                if thickness_mm not in (None, "") and float(thickness_mm) < 1.0:
                    return "PMMA film"
            return name
    for name, aliases in _ALIASES:  # alias as a whole word inside a longer phrase ("black PMMA rods 6 mm")
        if any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", s) for a in aliases):
            return name
    return None


def family_of(material: Any, thickness_mm: float | None = None, diameter_mm: float | None = None) -> str | None:
    name = canonical_material(material, thickness_mm, diameter_mm)
    return MATERIALS[name]["family"] if name else None


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


def _union(key: str) -> tuple[float, float]:
    env = get_engine().env
    vals = [env[f][key] for f in FAMILIES if env.get(f, {}).get(key)]
    return (min(v[0] for v in vals), max(v[1] for v in vals))


class _Envelope(dict):
    """TRAINING_ENVELOPE, filled lazily from the artifact (union over materials; per-material ranges in ``by_material``)."""

    def _fill(self) -> None:
        if not super().__len__():
            e = get_engine()
            super().update({
                "material": tuple(MATERIALS), "o2_percent": _union("o2_percent"), "pressure_psia": PRESSURE_RANGE,
                "flow_velocity_cm_s": _union("flow_velocity_cm_s"), "gravity": ("micro",),
                "by_material": {FAMILY_TO_NAME[f]: e.env[f] for f in FAMILIES},
            })

    def __getitem__(self, k):
        self._fill()
        return super().__getitem__(k)

    def get(self, k, default=None):
        self._fill()
        return super().get(k, default)

    def __contains__(self, k):
        self._fill()
        return super().__contains__(k)

    def __iter__(self):
        self._fill()
        return super().__iter__()

    def __len__(self):
        self._fill()
        return super().__len__()

    def keys(self):
        self._fill()
        return super().keys()

    def items(self):
        self._fill()
        return super().items()


TRAINING_ENVELOPE: dict[str, Any] = _Envelope()


def _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration) -> dict[str, Any]:
    """Family, configuration, thickness and size, with the defaults used (reported back to the caller)."""
    name = canonical_material(material, thickness_mm, diameter_mm)
    fam = MATERIALS[name]["family"] if name else None
    out: dict[str, Any] = {"material_name": name, "material_family": fam, "assumed_defaults": {}, "notes": []}
    if fam is None:
        return out
    d = get_engine().defaults[fam]
    if _norm(material) in GENERIC_PMMA:
        out["notes"].append(GENERIC_PMMA_NOTE)
    cfg = _norm(flow_configuration) or None
    if cfg is None:
        cfg = d["flow_configuration"]
        out["assumed_defaults"]["flow_configuration"] = cfg
    th = None if thickness_mm in (None, "") else float(thickness_mm)
    if th is None and d["thickness_mm"] is not None:
        th = d["thickness_mm"]
        out["assumed_defaults"]["thickness_mm"] = th
    kind = SIZE_KIND[fam]
    size = None
    if kind == "width_cm":
        size = None if sample_width_cm in (None, "") else float(sample_width_cm)
    elif kind == "diameter_mm":
        size = None if diameter_mm in (None, "") else float(diameter_mm)
    if size is None and d["size"] is not None:
        size = d["size"]
        out["assumed_defaults"][kind] = size
    out.update({"flow_configuration": cfg, "thickness_mm": th, "size": size, "size_kind": kind})
    return out


def _range_reason(label: str, val: float, rng: list[float] | tuple[float, float] | None, unit: str, who: str) -> str | None:
    if rng is None:
        return None
    lo, hi = rng
    if lo - 1e-9 <= val <= hi + 1e-9:
        return None
    return f"{label} {val:g}{unit} outside the tested range for {who} ({lo:g}–{hi:g}{unit})"


def hard_rule_reasons(material: Any = "SIBAL fabric", o2_percent: float | None = None, pressure_psia: float | None = 14.7,
                      flow_velocity_cm_s: float | None = None, gravity: Any = "micro", sample_width_cm: float | None = None,
                      thickness_mm: float | None = None, diameter_mm: float | None = None,
                      flow_configuration: str | None = None) -> list[str]:
    """Every hard rule that triggers, each with an explicit reason. Empty list = inside the material's envelope."""
    reasons: list[str] = []
    r = _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    fam = r["material_family"]
    if fam is None:
        reasons.append(f"material '{material}' not in training data (BASS-II materials in the data: {', '.join(MATERIALS)})")
    if pressure_psia is not None:
        x = _range_reason("pressure", float(pressure_psia), PRESSURE_RANGE, " psia", "every material (1 atm ± 0.3 psia)")
        if x:
            reasons.append(x.replace("outside the tested range for every material (1 atm ± 0.3 psia)",
                                     f"outside training range {PRESSURE_RANGE[0]:g}–{PRESSURE_RANGE[1]:g} psia (1 atm ± 0.3 psia)"))
    if gravity_label(gravity) != "micro":
        reasons.append(GRAVITY_OOD_REASON)
    if fam is None:
        if o2_percent is not None:
            x = _range_reason("O2", float(o2_percent), _union("o2_percent"), "%", "any material")
            if x:
                reasons.append(x)
        return reasons
    env = get_engine().env[fam]
    who = r["material_name"]
    if r["flow_configuration"] not in env["configurations"]:
        reasons.append(f"{r['flow_configuration']} flow was not tested for {who} (tested: {', '.join(env['configurations'])})")
    if o2_percent is not None:
        x = _range_reason("O2", float(o2_percent), env["o2_percent"], "%", who)
        if x:
            reasons.append(x)
    if flow_velocity_cm_s is not None:
        x = _range_reason("flow", float(flow_velocity_cm_s), env["flow_velocity_cm_s"], " cm/s", who)
        if x:
            reasons.append(x)
    if r["thickness_mm"] is not None and env["thickness_mm"]:
        x = _range_reason("thickness", r["thickness_mm"], env["thickness_mm"], " mm", who)
        if x:
            reasons.append(x)
    if r["size"] is not None and env["size"]:
        unit = " cm" if r["size_kind"] == "width_cm" else " mm"
        x = _range_reason("width" if r["size_kind"] == "width_cm" else "diameter", r["size"], env["size"], unit, who)
        if x:
            reasons.append(x)
    return reasons


def _knn_reason(dist: float, threshold: float, who: str) -> str:
    return (f"far from labelled NASA tests of {who}: kNN distance {dist:.2f} > threshold {threshold:.2f} "
            "(95th percentile of leave-one-test-out distances); treat P(burn) as an extrapolation")


def _ood_block(hard: list[str], knn_reasons: list[str]) -> dict[str, Any]:
    reasons = hard + knn_reasons
    level = "out_of_envelope" if hard else ("extrapolation" if knn_reasons else "in_distribution")
    return {"ood_flag": bool(reasons), "ood_reason": "; ".join(reasons) or None, "ood_reasons": reasons,
            "ood_level": level, "coverage": level, "hard_rule_reasons": hard}


EXTRAPOLATION_INTERVAL_NOTE = ("extrapolation: far from this material's labelled tests the model has no local evidence; "
                               "the interval is reported as [0, 1]")


def _label(p: float) -> str:
    """burn if P(burn) >= 0.5 at 2-decimal precision: an exact tie counts as burn (conservative for fire safety)."""
    return "burn" if round(float(p), 2) >= 0.5 else "extinguish"


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


# --------------------------------------------------------------------------- #
# nearest_experiments
# --------------------------------------------------------------------------- #
def _experiment_rows(fam: str | None, o2: float, flow: float | None, r: dict[str, Any] | None, k: int) -> list[dict[str, Any]]:
    e = get_engine()
    pts = e.points if fam is None else e.points[e.points["material_family"] == fam]
    if pts.empty:
        return []
    cfg = (r or {}).get("flow_configuration") or e.defaults.get(fam or "", {}).get("flow_configuration") or "opposed"
    th = (r or {}).get("thickness_mm")
    size = (r or {}).get("size")
    q = e.frame(o2, flow if flow else 10.0, fam or pts["material_family"].iloc[0], cfg, th, size)
    Zq = (q[["o2_pct", "log10_flow", "size_z", "log10_thickness"]].to_numpy()[0] - e.mu) / e.sd
    idx = np.flatnonzero((e.Zfam == fam) if fam else np.ones(len(e.Z), bool))
    cols = [0, 1, 2, 3] if flow else [0, 2, 3]
    d = np.sqrt(((e.Z[idx][:, cols] - Zq[cols]) ** 2).sum(axis=1))
    order = idx[np.argsort(d, kind="stable")]
    dist = dict(zip(idx, d))
    rows, seen = [], set()
    for i in order:
        p = e.points.iloc[int(i)]
        if p["test_id"] in seen:
            continue
        seen.add(p["test_id"])
        rows.append({
            "id": p["test_id"], "point_id": p["point_id"], "pi": p["pi"], "pi_table": p["pi_table"],
            "appendix_test_id": p.get("appendix_test_id") if isinstance(p.get("appendix_test_id"), str) else "",
            "material": FAMILY_TO_NAME[p["material_family"]], "material_family": p["material_family"],
            "flow_configuration": p["flow_configuration"], "o2_percent": float(p["o2_pct"]), "pressure_psia": 14.7,
            "flow_velocity_cm_s": float(p["flow_cm_s"]),
            "sample_width_cm": None if pd.isna(p["width_cm"]) else float(p["width_cm"]),
            "thickness_mm": None if pd.isna(p["thickness_mm"]) else float(p["thickness_mm"]),
            "diameter_mm": None if pd.isna(p["diameter_mm"]) else float(p["diameter_mm"]),
            "outcome": "burn" if int(p["burn"]) == 1 else "extinguish",
            "derivation_rule": p["derivation_rule"], "label_confidence": p["label_confidence"],
            "evidence_quote": p["evidence_quote"], "source_page": int(p["source_page"]),
            "source": "NASA/TM-20210011385, " + ("Table 7.1 / Table A.6" if p["pi_table"] == "7.1/A.6" else f"Table {p['pi_table']}"),
            "distance": round(float(dist[i]), 2),
        })
        if len(rows) >= k:
            break
    return rows


def nearest_experiments(material: str | None = "SIBAL fabric", o2_percent: float = 21.0, pressure_psia: float = 14.7,
                        flow_velocity_cm_s: float | None = None, gravity: str = "micro", k: int = 3,
                        sample_width_cm: float | None = None, thickness_mm: float | None = None,
                        diameter_mm: float | None = None, flow_configuration: str | None = None) -> dict[str, Any]:
    """The k closest labelled NASA tests (one row per test) of the same material, with quote and page."""
    k = max(1, min(int(k), 12))
    flow = float(flow_velocity_cm_s) if flow_velocity_cm_s not in (None, "") and float(flow_velocity_cm_s) > 0 else None
    r = _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration) if material else None
    fam = r["material_family"] if r else None
    hard = hard_rule_reasons(material if material is not None else "SIBAL fabric", o2_percent, pressure_psia, flow, gravity,
                             sample_width_cm, thickness_mm, diameter_mm, flow_configuration) if material else []
    rows = [] if (material and fam is None) else _experiment_rows(fam, float(o2_percent), flow, r, k)
    return {
        "value": rows, "interval": None, "unit": "standardized distance", "label": None,
        "burn_probability": None, "burn_probability_interval": None,
        **_ood_block(hard, []), "evidence": [x["id"] for x in rows],
        "material_family": fam,
        "note": ("Nearest labelled tests of the same material in standardized O2, log10 flow, size and thickness"
                 + ("" if flow else " (no flow given: O2, size and thickness only)") + "."
                 + (" Material not in the data: no tests to show." if material and fam is None else "")),
        "source": SOURCE,
    }


# --------------------------------------------------------------------------- #
# Spread rate (Task C hook; filled by src/spread_rate.py when available)
# --------------------------------------------------------------------------- #
def _spread_rate(fam: str | None, o2: float, flow: float, r: dict[str, Any] | None) -> dict[str, Any]:
    try:
        from src import spread_rate
    except Exception:  # noqa: BLE001
        return {"spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON}
    return spread_rate.predict_spread(fam, o2, flow, r)


# --------------------------------------------------------------------------- #
# predict
# --------------------------------------------------------------------------- #
def _no_number(hard: list[str], evidence_rows: list[dict[str, Any]], inputs: dict[str, Any], why: str,
               resolved: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "label": None, "burn_probability": None, "burn_probability_interval": None, "interval_level": None,
        "value": None, "interval": None, "unit": "probability", "quantity": "P(burn)",
        "spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON,
        **_ood_block(hard, []), "note": why,
        "material_family": (resolved or {}).get("material_family"),
        "evidence": [r["id"] for r in evidence_rows], "nearest_experiments": evidence_rows,
        "inputs": inputs, "source": SOURCE,
    }


def predict(material: str = "SIBAL fabric", o2_percent: float = 21.0, pressure_psia: float = 14.7,
            flow_velocity_cm_s: float | None = None, gravity: str = "micro", sample_width_cm: float | None = None,
            thickness_mm: float | None = None, diameter_mm: float | None = None,
            flow_configuration: str | None = None) -> dict[str, Any]:
    """P(burn) with a 90% bootstrap interval for one condition."""
    inputs = {"material": material, "o2_percent": o2_percent, "pressure_psia": pressure_psia,
              "flow_velocity_cm_s": flow_velocity_cm_s, "gravity": gravity_label(gravity), "sample_width_cm": sample_width_cm,
              "thickness_mm": thickness_mm, "diameter_mm": diameter_mm, "flow_configuration": flow_configuration}
    if flow_velocity_cm_s in (None, "") or float(flow_velocity_cm_s) <= 0:
        return _no_number([], [], inputs, "flow_velocity_cm_s (> 0 cm/s) is required for a prediction; use flammability_boundary to cover all flows")
    o2, flow = float(o2_percent), float(flow_velocity_cm_s)
    r = _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    fam = r["material_family"]
    hard = hard_rule_reasons(material, o2, pressure_psia, flow, gravity, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    near = _experiment_rows(fam, o2, flow, r, 3) if fam else []
    inputs.update({"material_name": r["material_name"], "material_family": fam, "assumed_defaults": r["assumed_defaults"]})
    if hard:
        out = _no_number(hard, near, inputs, "No prediction outside the tested conditions: the model has no data there. "
                                             "Do not estimate one.", r)
        return out
    e = get_engine()
    F = e.frame(o2, flow, fam, r["flow_configuration"], r["thickness_mm"], r["size"])
    p, lo, hi = (float(a[0]) for a in e.proba_with_interval(F))
    dist = float(e.distance(F, fam)[0])
    knn = [_knn_reason(dist, e.threshold, r["material_name"])] if dist > e.threshold else []
    raw_band = [_r(lo), _r(hi)]
    band = [0.0, 1.0] if knn else raw_band
    env = e.env[fam]
    out = {
        "label": "uncertain" if knn else _label(p),
        "burn_probability": _r(p), "burn_probability_interval": band, "interval_level": e.level,
        "value": _r(p), "interval": band, "unit": "probability",
        "interval_note": EXTRAPOLATION_INTERVAL_NOTE if knn else "90% bootstrap interval over NASA tests",
        "bootstrap_interval_raw": raw_band,
        "quantity": "P(burn): probability that a flame is sustained",
        **_spread_rate(fam, o2, flow, r),
        **_ood_block([], knn),
        "knn_distance": _r(dist), "knn_threshold": _r(e.threshold),
        "material_family": fam, "material_name": r["material_name"],
        "material_data": {"n_points": env["n_points"], "n_tests": env["n_tests"], "n_burn": env["n_burn"],
                          "n_extinguished": env["n_extinguished"]},
        "notes": r["notes"],
        "evidence": [x["id"] for x in near], "nearest_experiments": near,
        "model": e.art["model_label"], "inputs": inputs, "source": SOURCE,
    }
    if env["n_burn"] == 0 or env["n_extinguished"] == 0:
        one = "burn" if env["n_extinguished"] == 0 else "non-sustained"
        out["notes"] = out["notes"] + [f"every labelled {r['material_name']} point in the data is {one}: the model cannot "
                                       f"locate a boundary for this material, only repeat what its tests showed"]
    return out


# --------------------------------------------------------------------------- #
# flammability_boundary + map grid
# --------------------------------------------------------------------------- #
def _lowest_burning_o2(o2_grid: np.ndarray, p: np.ndarray) -> float | None:
    idx = np.flatnonzero(p >= 0.5)
    return float(o2_grid[idx[0]]) if len(idx) else None


def boundary_grid(material: str = "SIBAL fabric", sample_width_cm: float | None = None, thickness_mm: float | None = None,
                  diameter_mm: float | None = None, flow_configuration: str | None = None) -> dict[str, Any]:
    """P(burn) grid over O2 13–23% x flow 0.4–60 cm/s (log) with bootstrap bands and in-distribution mask (cached)."""
    if isinstance(material, (int, float)) and not isinstance(material, bool):  # v1 call style: boundary_grid(width)
        material, sample_width_cm = "SIBAL fabric", float(material)
    r = _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    if r["material_family"] is None:
        raise ValueError(f"material '{material}' not in training data")
    return _cached_grid(r["material_family"], r["flow_configuration"], r["thickness_mm"], r["size"])


@lru_cache(maxsize=32)
def _cached_grid(fam: str, cfg: str, th: float | None, size: float | None, n_o2: int = 81, n_flow: int = 61) -> dict[str, Any]:
    e = get_engine()
    o2 = np.round(np.linspace(*MAP_O2_RANGE, n_o2), 3)
    flow = np.round(np.logspace(np.log10(MAP_FLOW_RANGE[0]), np.log10(MAP_FLOW_RANGE[1]), n_flow), 4)
    OO, FF = np.meshgrid(o2, flow, indexing="ij")
    F = e.frame(OO.ravel(), FF.ravel(), fam, cfg, th, size)
    p, lo, hi = e.proba_with_interval(F)
    dist = e.distance(F, fam)
    env = e.env[fam]
    (o2lo, o2hi), (flo, fhi) = env["o2_percent"], env["flow_velocity_cm_s"]
    hard_ok = (OO.ravel() >= o2lo - 1e-9) & (OO.ravel() <= o2hi + 1e-9) & (FF.ravel() >= flo - 1e-9) & (FF.ravel() <= fhi + 1e-9)
    cfg_ok = cfg in env["configurations"]
    shape = OO.shape
    return {
        "material": FAMILY_TO_NAME[fam], "material_family": fam, "flow_configuration": cfg, "thickness_mm": th, "size": size,
        "size_kind": SIZE_KIND[fam], "o2_percent": o2.tolist(), "flow_velocity_cm_s": flow.tolist(),
        "sample_width_cm": size if SIZE_KIND[fam] == "width_cm" else None,
        "p_burn": p.reshape(shape).round(4).tolist(), "p_lo": lo.reshape(shape).round(4).tolist(),
        "p_hi": hi.reshape(shape).round(4).tolist(), "knn_distance": dist.reshape(shape).round(3).tolist(),
        "inside_hard_envelope": (hard_ok & cfg_ok).reshape(shape).tolist(),
        "in_distribution": (hard_ok & cfg_ok & (dist <= e.threshold)).reshape(shape).tolist(),
        "knn_threshold": e.threshold, "interval_level": e.level, "envelope": env,
    }


@lru_cache(maxsize=64)
def _boundary_surfaces(fam: str, cfg: str, th: float | None, size: float | None, flows: tuple[float, ...]):
    e = get_engine()
    lo_o2, hi_o2 = e.env[fam]["o2_percent"]
    o2_grid = np.round(np.arange(lo_o2, hi_o2 + 1e-9, O2_GRID_STEP), 3)
    OO, FF = np.meshgrid(o2_grid, flows, indexing="ij")
    p, lo, hi = e.proba_with_interval(e.frame(OO.ravel(), FF.ravel(), fam, cfg, th, size))
    return o2_grid, p.reshape(OO.shape), lo.reshape(OO.shape), hi.reshape(OO.shape)


def flammability_boundary(material: str = "SIBAL fabric", pressure_psia: float = 14.7, gravity: str = "micro",
                          flow_velocities_cm_s: list[float] | None = None, o2_percent: float | None = None,
                          sample_width_cm: float | None = None, include_grid: bool = False, thickness_mm: float | None = None,
                          diameter_mm: float | None = None, flow_configuration: str | None = None) -> dict[str, Any]:
    """The 0.5 contour of P(burn): lowest O2 (inside the material's tested O2 range) where P(burn) >= 0.5, per flow.

    ``value`` = [{"flow_velocity_cm_s", "o2_percent_limit", "limit_status", ...}], ``interval`` = one [lo, hi] O2 band per
    flow from the bootstrap. With ``o2_percent``, also P(burn) at that O2 per flow and the flows where it is >= 0.5.
    """
    r = _resolve_inputs(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    fam = r["material_family"]
    hard = hard_rule_reasons(material, None, pressure_psia, None, gravity, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
    if hard:
        out = _no_number(hard, [], {"material": material, "pressure_psia": pressure_psia, "gravity": gravity_label(gravity),
                                    "o2_percent": o2_percent}, "No boundary outside the tested conditions.", r)
        out["value"] = None
        return out
    e = get_engine()
    env = e.env[fam]
    who = r["material_name"]
    o2_hard = _range_reason("O2", float(o2_percent), env["o2_percent"], "%", who) if o2_percent not in (None, "") else None
    if flow_velocities_cm_s:
        flows = [float(f) for f in flow_velocities_cm_s if float(f) > 0]
    else:  # default flows: the standard list, restricted to this material's tested flows
        flo, fhi = env["flow_velocity_cm_s"]
        flows = [f for f in DEFAULT_FLOWS if flo <= f <= fhi] or [flo, fhi]
    o2_grid, P_all, LO_all, HI_all = _boundary_surfaces(fam, r["flow_configuration"], r["thickness_mm"], r["size"], tuple(flows))
    pts, band, flow_reasons = [], [], []
    for j, f in enumerate(flows):
        p, plo, phi = P_all[:, j], LO_all[:, j], HI_all[:, j]
        lim = _lowest_burning_o2(o2_grid, p)
        status = ("burns_at_all_tested_o2" if lim == o2_grid[0] else "crossing") if lim is not None else "no_burn_in_tested_o2"
        f_reason = _range_reason("flow", f, env["flow_velocity_cm_s"], " cm/s", who)
        if f_reason:
            flow_reasons.append(f_reason)
        point = {"flow_velocity_cm_s": f, "o2_percent_limit": lim, "limit_status": status, "inside_hard_envelope": f_reason is None}
        if lim is not None:
            Fl = e.frame(lim, f, fam, r["flow_configuration"], r["thickness_mm"], r["size"])
            point["in_distribution_at_limit"] = bool(e.distance(Fl, fam)[0] <= e.threshold) and f_reason is None
        pts.append(point)
        band.append([_lowest_burning_o2(o2_grid, phi), _lowest_burning_o2(o2_grid, plo)])
    crossing = [p for p in pts if p["o2_percent_limit"] is not None and p["inside_hard_envelope"]]
    best = min(crossing, key=lambda p: p["o2_percent_limit"]) if crossing else None
    knn: list[str] = []
    res: dict[str, Any] = {
        "value": pts, "interval": band, "interval_level": e.level, "unit": "O2 %",
        "quantity": f"lowest O2 (%) in {env['o2_percent'][0]:g}–{env['o2_percent'][1]:g}% where P(burn) >= 0.5, per flow",
        "label": None, "burn_probability": None, "burn_probability_interval": None,
        "material_family": fam, "material_name": who, "assumed_defaults": r["assumed_defaults"], "notes": r["notes"],
        "min_o2_percent_limit": best["o2_percent_limit"] if best else None,
        "flow_at_min_limit_cm_s": best["flow_velocity_cm_s"] if best else None,
        "spread_rate_mm_s": None, "spread_rate_reason": SPREAD_RATE_REASON,
        "note": f"o2_percent_limit = None means P(burn) < 0.5 at every O2 from {env['o2_percent'][0]:g}% to "
                f"{env['o2_percent'][1]:g}% at that flow. Limit statuses: crossing | burns_at_all_tested_o2 | no_burn_in_tested_o2.",
    }
    if o2_percent not in (None, ""):
        o2 = float(o2_percent)
        res["at_o2_percent"] = o2
        if o2_hard:
            res.update({"flows_where_flammable_cm_s": None, "flows_where_not_flammable_cm_s": None, "flammable_at_some_flow": None})
        else:
            F = e.frame(o2, flows, fam, r["flow_configuration"], r["thickness_mm"], r["size"])
            p, plo, phi = e.proba_with_interval(F)
            d = e.distance(F, fam)
            in_flow = np.array([pt["inside_hard_envelope"] for pt in pts])
            far = (d > e.threshold) | ~in_flow
            for pt, pi, li, hi_, di, fi in zip(pts, p, plo, phi, d, far):
                pt.update({"p_burn_at_o2": _r(pi), "p_burn_interval_at_o2": [0.0, 1.0] if fi else [_r(li), _r(hi_)],
                           "knn_distance_at_o2": _r(di), "extrapolation_at_o2": bool(fi)})
            near_ok = [(f, pi) for f, pi, fi in zip(flows, p, far) if not fi]
            res["flows_where_flammable_cm_s"] = [f for f, pi in near_ok if _label(pi) == "burn"]
            res["flows_where_not_flammable_cm_s"] = [f for f, pi in near_ok if _label(pi) == "extinguish"]
            res["flows_extrapolated_cm_s"] = [f for f, fi in zip(flows, far) if fi]
            res["flammable_at_some_flow"] = bool(res["flows_where_flammable_cm_s"]) if near_ok else None
            if res["flows_extrapolated_cm_s"]:
                msg = (f"no verdict at {o2:g}% O2 for flows {', '.join(f'{f:g}' for f in res['flows_extrapolated_cm_s'])} cm/s: "
                       f"outside the tested flows or far from labelled {who} tests (kNN distance > {e.threshold:.2f})")
                if near_ok:  # some flows are supported: the answer is in distribution, the rest is listed as such
                    res["extrapolation_note"] = msg
                else:
                    knn.append(msg)
            res["comparison_note"] = (f"At {o2:g}% O2, P(burn) >= 0.5 at the flows in flows_where_flammable_cm_s and < 0.5 at the "
                                      "flows in flows_where_not_flammable_cm_s; flows in flows_extrapolated_cm_s have no verdict "
                                      "(computed in code).")
    res.update(_ood_block(([o2_hard] if o2_hard else []), knn))
    if flow_reasons and not knn:
        res["flow_range_note"] = "; ".join(flow_reasons)
    ref_o2 = float(o2_percent) if o2_percent not in (None, "") and not o2_hard else float(np.mean(env["o2_percent"]))
    res["evidence"] = [x["id"] for x in _experiment_rows(fam, ref_o2, res["flow_at_min_limit_cm_s"] or 10.0, r, 3)]
    res["model"], res["source"] = e.art["model_label"], SOURCE
    if include_grid:
        res["grid"] = boundary_grid(material, sample_width_cm, thickness_mm, diameter_mm, flow_configuration)
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
        r = predict(s.get("material", "SIBAL fabric"), s.get("o2_percent", 21.0), s.get("pressure_psia", 14.7),
                    s.get("flow_velocity_cm_s"), s.get("gravity", "micro"), s.get("sample_width_cm"),
                    s.get("thickness_mm"), s.get("diameter_mm"), s.get("flow_configuration"))
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
