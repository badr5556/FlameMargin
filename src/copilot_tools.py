"""Tool layer for the FlameMargin Copilot.

Responsibilities
  1. Adapter: use the real ``src/api.py`` (Layer 1) when it is importable and
     exposes the contract functions, otherwise ``src/copilot_mock_api.py``.
  2. Normalization: units ("34%", 0.34, "56.5 kPa", "5 mm/s", "fans off",
     "1/6 g"...), material aliases and mission presets are converted here. The
     LLM never does unit math itself.
  3. Validation: physically impossible inputs become a structured tool error.
     Inputs outside the training envelope are NOT clamped; they are passed
     through and the result is flagged OOD.
  4. Hard OOD rule: any gravity other than microgravity is OOD, whatever the
     model returns ("no training data at this gravity level (FM2 not yet flown)").
  5. Tool declarations (JSON schema) + ``dispatch(name, args)``.

Every tool result is a plain JSON-serializable dict. Errors are returned as
``{"error": {"type": ..., "message": ..., "hint": ...}}``, never raised.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
import os
import re
from pathlib import Path
from typing import Any, Callable

from src import copilot_facts
from src import copilot_mock_api

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAVITY_OOD_REASON = "no training data at this gravity level (FM2 not yet flown)"
CONTRACT_FUNCTIONS = ("predict", "flammability_boundary", "compare_scenarios", "nearest_experiments")

# Physically valid input ranges (NOT the training envelope). Outside -> tool error.
PHYSICAL_LIMITS = {
    "o2_percent": (0.0, 100.0),
    "pressure_psia": (0.0, 50.0),
    "flow_velocity_cm_s": (0.0, 500.0),
}


class ToolInputError(ValueError):
    """Bad tool input. ``kind`` becomes the error type returned to the LLM."""

    def __init__(self, message: str, kind: str = "invalid_input", hint: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.hint = hint


# =========================================================================== #
# Mission presets
# =========================================================================== #
# No preset module exists in the repo yet (checked: no app.py / src/api.py /
# presets file on main when this was written). These mirror the team brief.
# If Layer 1/2 later exposes MISSION_PRESETS (see _load_repo_presets), it wins.
BRIEF_PRESETS: dict[str, dict[str, Any]] = {
    "ISS cabin": {
        "pressure_psia": 14.7,
        "o2_percent": 21.0,
        "gravity": "micro",
        "gravity_g": 0.0,
        "data_status": "in-distribution",
    },
    "Artemis Exploration Atmosphere": {
        "pressure_psia": 8.2,
        "o2_percent": 34.0,
        "gravity": "micro",
        "gravity_g": 0.0,
        "data_status": "partial coverage",
    },
    "Lunar surface habitat": {
        "pressure_psia": 8.2,
        "o2_percent": 34.0,
        "gravity": "lunar",
        "gravity_g": 0.166,
        "data_status": "OOD, always flagged",
    },
}
PRESET_ALIASES = {
    "ISS cabin": ["iss", "space station", "international space station", "station", "محطة الفضاء", "المحطة"],
    "Artemis Exploration Atmosphere": [
        "artemis", "exploration atmosphere", "exploration", "orion", "transit", "ea", "أرتميس", "ارتميس",
    ],
    "Lunar surface habitat": ["lunar", "moon", "lunar habitat", "habitat", "lunar surface", "القمر", "قمر"],
}

# =========================================================================== #
# Materials
# =========================================================================== #
MATERIAL_ALIASES = {
    "PMMA": ["pmma", "acrylic", "plexiglass", "plexiglas", "perspex", "lucite", "polymethyl methacrylate", "أكريليك", "اكريليك"],
    "Nomex": ["nomex", "nomex ht90-40", "aramid", "meta-aramid", "نومكس", "نوميكس"],
    "Cotton-fiberglass": [
        "cotton-fiberglass", "cotton fiberglass", "cotton/fiberglass", "cotton", "sibal fabric", "fabric", "قطن",
    ],
    "Delrin": ["delrin", "pom", "acetal", "polyoxymethylene", "دلرين"],
}

# =========================================================================== #
# Unit parsing
# =========================================================================== #
_NUM = r"[-+]?\d+(?:[.,٫]\d+)?"
PRESSURE_TO_PSIA = {
    "psia": 1.0, "psi": 1.0, "psig": None,  # gauge pressure is ambiguous -> error
    "kpa": 0.1450377, "pa": 0.0001450377, "atm": 14.69595, "bar": 14.50377, "mbar": 0.01450377,
    "hpa": 0.01450377, "mmhg": 0.01933678, "torr": 0.01933678,
}
FLOW_TO_CM_S = {"cm/s": 1.0, "cms": 1.0, "cm s-1": 1.0, "mm/s": 0.1, "m/s": 100.0, "ft/s": 30.48, "ft/min": 0.508, "m/min": 1.6666667}
FANS_OFF_PATTERNS = [
    r"fans?\s*(?:are\s*)?off", r"ventilation\s*(?:is\s*)?off", r"no\s+ventilation", r"ventilation\s+shut\s*down",
    r"no\s+fans?", r"quiescent", r"fans?_off", r"المراوح\s*(?:مقفولة|مطفية|متوقفة|off)", r"بدون\s*(?:مراوح|تهوية)",
    r"(?:قفل|إطفاء|اطفاء)\s*(?:المراوح|التهوية)",
]


def _to_float(s: str) -> float:
    s = s.replace("٫", ".")
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    return float(s)


def _first_number(text: str) -> float | None:
    m = re.search(_NUM, text)
    return _to_float(m.group(0)) if m else None


def is_fans_off(value: Any) -> bool:
    return isinstance(value, str) and any(re.search(p, value.lower()) for p in FANS_OFF_PATTERNS)


def parse_o2_percent(value: Any) -> tuple[float, str | None]:
    """Return O2 in percent. Accepts 34, '34', '34%', '34 ٪', 0.34 (fraction), '0.34'."""
    if isinstance(value, bool) or value is None:
        raise ToolInputError("o2_percent is required (a number in percent, e.g. 21).")
    note = None
    if isinstance(value, (int, float)):
        x = float(value)
        explicit_pct = False
    else:
        s = str(value).strip().lower()
        x = _first_number(s)
        if x is None:
            raise ToolInputError(f"Could not read an O2 value from '{value}'.")
        explicit_pct = "%" in s or "٪" in s or "percent" in s
    if not explicit_pct and 0 < x <= 1.0:
        note = f"O2 {x:g} interpreted as a fraction -> {x * 100:g}%"
        x = x * 100.0
    lo, hi = PHYSICAL_LIMITS["o2_percent"]
    if not lo < x <= hi:
        raise ToolInputError(f"O2 {x:g}% is physically invalid (must be >0 and <=100%).")
    return round(x, 3), note


def parse_pressure_psia(value: Any) -> tuple[float, str | None]:
    """Return pressure in psia. Bare numbers are psia; strings may carry kPa/atm/bar/psi/mmHg/torr."""
    if isinstance(value, bool) or value is None:
        raise ToolInputError("pressure_psia is required.")
    note = None
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        s = str(value).strip().lower().replace(" ", "")
        x = _first_number(s)
        if x is None:
            raise ToolInputError(f"Could not read a pressure from '{value}'.")
        unit = None
        for u in sorted(PRESSURE_TO_PSIA, key=len, reverse=True):
            if s.endswith(u) or re.search(re.escape(u) + r"(?![a-z])", s):
                unit = u
                break
        if unit == "psig":
            raise ToolInputError("Gauge pressure (psig) is ambiguous; give absolute pressure (psia).")
        if unit and unit not in ("psia", "psi"):
            psia = x * PRESSURE_TO_PSIA[unit]
            note = f"{x:g} {unit} -> {psia:.2f} psia"
            x = psia
    lo, hi = PHYSICAL_LIMITS["pressure_psia"]
    if not lo < x <= hi:
        raise ToolInputError(f"Pressure {x:g} psia is physically invalid for a crewed cabin (0–{hi:g} psia).")
    return round(x, 3), note


def parse_flow_cm_s(value: Any) -> tuple[float, str | None]:
    """Return flow velocity in cm/s. Accepts numbers (cm/s), '5 mm/s', '0.1 m/s', 'fans off'."""
    if isinstance(value, bool) or value is None:
        raise ToolInputError(
            "flow_velocity_cm_s is required for this tool.",
            kind="missing_flow",
            hint="If the operator gave no flow, call flammability_boundary (covers all flows) or state an assumption.",
        )
    note = None
    if is_fans_off(value):
        x, src = resolve_fans_off_flow()
        note = f"'fans off' -> {x:g} cm/s ({src})"
        return x, note
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        s = str(value).strip().lower().replace(" ", "")
        x = _first_number(s)
        if x is None:
            raise ToolInputError(f"Could not read a flow velocity from '{value}'.")
        for u in sorted(FLOW_TO_CM_S, key=len, reverse=True):
            if u.replace(" ", "") in s:
                if FLOW_TO_CM_S[u] != 1.0:
                    cm = x * FLOW_TO_CM_S[u]
                    note = f"{x:g} {u} -> {cm:g} cm/s"
                    x = cm
                break
    lo, hi = PHYSICAL_LIMITS["flow_velocity_cm_s"]
    if not lo <= x <= hi:
        raise ToolInputError(f"Flow {x:g} cm/s is physically invalid for a cabin (0–{hi:g} cm/s).")
    return round(x, 4), note


def parse_gravity(value: Any) -> tuple[str, float]:
    """Return (label, g). Labels: micro | lunar | mars | earth | custom."""
    if value is None or value == "":
        return "micro", 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        g = float(value)
    else:
        s = str(value).strip().lower()
        frac = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s*g?", s)
        num = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)\s*(?:g|g0|gee)?", s)
        if frac and int(frac.group(2)) != 0:
            g = int(frac.group(1)) / int(frac.group(2))
        elif num:
            g = float(num.group(1))
        else:
            table = [
                ("micro", ["micro", "µg", "ug", "μg", "zero", "orbit", "iss", "transit", "weightless", "انعدام"]),
                ("lunar", ["lunar", "moon", "قمر", "القمر"]),
                ("mars", ["mars", "martian", "المريخ", "مريخ"]),
                ("earth", ["earth", "ground", "terrestrial", "normal gravity", "الأرض", "الارض"]),
            ]
            for label, keys in table:
                if any(k in s for k in keys):
                    return label, copilot_mock_api.GRAVITY_G[label]
            raise ToolInputError(f"Unknown gravity '{value}'. Use micro, lunar, mars, earth or a number in g.")
    if g < 0 or g > 3:
        raise ToolInputError(f"Gravity {g:g} g is out of the physical range for this tool (0–3 g).")
    if g < 1e-3:
        return "micro", 0.0
    for label, gv in copilot_mock_api.GRAVITY_G.items():
        if gv and abs(g - gv) / gv < 0.05:
            return label, gv
    return "custom", round(g, 3)


def resolve_material(name: Any, known: list[str]) -> tuple[str | None, str]:
    """Return (canonical name or None if unknown, cleaned input)."""
    raw = str(name or "").strip()
    if not raw:
        raise ToolInputError("material is required.", hint=f"Known materials: {', '.join(known)}")
    low = raw.lower()
    for k in known:
        if k.lower() == low:
            return k, raw
    for canonical, aliases in MATERIAL_ALIASES.items():
        if low == canonical.lower() or low in aliases or any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", low) for a in aliases):
            for k in known:
                if k.lower() == canonical.lower():
                    return k, raw
    return None, raw


def find_material_in_text(text: str, known: list[str]) -> str | None:
    low = text.lower()
    for canonical, aliases in MATERIAL_ALIASES.items():
        for a in [canonical.lower(), *aliases]:
            if re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", low):
                hit = [k for k in known if k.lower() == canonical.lower()]
                if hit:
                    return hit[0]
    for k in known:
        if k.lower() in low:
            return k
    return None


# =========================================================================== #
# "Fans off" flow value
# =========================================================================== #
_FANS_CONST_RE = re.compile(r"^FANS?_OFF.*(FLOW|VEL|SPEED)", re.IGNORECASE)


def _scan_repo_for_fans_off() -> tuple[float, str] | None:
    """Look for a constant like FANS_OFF_FLOW_CM_S in app.py / src/*.py without executing them."""
    candidates = [REPO_ROOT / "app.py", *sorted((REPO_ROOT / "src").glob("*.py"))]
    for path in candidates:
        if not path.exists() or path.name.startswith("copilot_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
                val = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets, val = [node.target], node.value
            for t in targets:
                if _FANS_CONST_RE.match(t.id) and isinstance(val, ast.Constant) and isinstance(val.value, (int, float)):
                    x = float(val.value)
                    name = t.id.upper()
                    if name.endswith("_MM_S"):
                        x *= 0.1
                    elif name.endswith("_M_S"):
                        x *= 100.0
                    return x, f"{path.relative_to(REPO_ROOT)}:{t.id}"
    return None


def resolve_fans_off_flow() -> tuple[float, str]:
    found = _scan_repo_for_fans_off()
    if found:
        return found
    env = os.environ.get("FLAMEMARGIN_FANS_OFF_FLOW_CM_S", "").strip()
    if env:
        try:
            return float(env), "env FLAMEMARGIN_FANS_OFF_FLOW_CM_S"
        except ValueError:
            pass
    raise ToolInputError(
        "'fans off' has no agreed flow value yet: the Flammability Map does not define FANS_OFF_FLOW_CM_S.",
        kind="fans_off_undefined",
        hint="Do not guess a flow. Call flammability_boundary to show the limit across low flows, "
        "or ask the operator for the residual flow in cm/s.",
    )


# =========================================================================== #
# API adapter
# =========================================================================== #
_PARAM_ALIASES = {
    "material": ["material", "material_name", "sample", "fuel"],
    "o2": ["o2_percent", "o2_pct", "oxygen_percent", "o2", "oxygen", "o2_fraction", "o2_frac", "xo2", "o2_mole_fraction"],
    "pressure": ["pressure_psia", "pressure", "p_psia", "pressure_kpa", "p_kpa", "pressure_atm"],
    "flow": ["flow_velocity_cm_s", "flow_cm_s", "flow_velocity", "flow", "velocity_cm_s", "flow_mm_s", "flow_m_s", "u_cm_s"],
    "gravity": ["gravity", "gravity_level", "g_level", "gravity_g", "g"],
    "flows": ["flow_velocities_cm_s", "flow_velocities", "flows", "flow_grid"],
    "k": ["k", "n", "top_k", "n_neighbors"],
    "scenarios": ["scenarios", "scenario_list", "cases"],
}


class _Backend:
    def __init__(self) -> None:
        self.module: Any = None
        self.name = "unresolved"
        self.load_error: str | None = None

    def load(self) -> Any:
        if self.module is not None:
            return self.module
        if os.environ.get("COPILOT_FORCE_MOCK_API") == "1":
            self.module, self.name = copilot_mock_api, "mock"
            return self.module
        errors = []
        for modname in ("src.api", "api"):
            try:
                mod = importlib.import_module(modname)
            except Exception as e:  # noqa: BLE001 - any import failure means "not ready"
                errors.append(f"{modname}: {type(e).__name__}: {e}")
                continue
            missing = [f for f in CONTRACT_FUNCTIONS if not callable(getattr(mod, f, None))]
            if missing:
                errors.append(f"{modname}: missing {missing}")
                continue
            self.module, self.name = mod, "real"
            return mod
        self.load_error = "; ".join(errors)
        self.module, self.name = copilot_mock_api, "mock"
        return self.module

    def reset(self) -> None:
        self.__init__()


BACKEND = _Backend()


def backend_name() -> str:
    BACKEND.load()
    return BACKEND.name


def known_materials() -> list[str]:
    mod = BACKEND.load()
    mats = getattr(mod, "MATERIALS", None) or getattr(mod, "KNOWN_MATERIALS", None)
    if isinstance(mats, dict):
        return list(mats)
    if isinstance(mats, (list, tuple, set)):
        return [str(m) for m in mats]
    return list(copilot_mock_api.MATERIALS) if BACKEND.name == "mock" else []


def training_envelope() -> dict[str, Any] | None:
    mod = BACKEND.load()
    env = getattr(mod, "TRAINING_ENVELOPE", None) or getattr(mod, "TRAINING_RANGES", None)
    return env if isinstance(env, dict) else None


def _call_api(func_name: str, canonical: dict[str, Any]) -> dict[str, Any]:
    """Map canonical args onto the real function's parameter names (and units), then call it."""
    mod = BACKEND.load()
    fn: Callable[..., Any] = getattr(mod, func_name)
    sig = inspect.signature(fn)
    kwargs: dict[str, Any] = {}
    accepts_var_kw = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
    for key, val in canonical.items():
        pname = next((a for a in _PARAM_ALIASES.get(key, [key]) if a in sig.parameters), None)
        if val is None:
            # Pass an explicit None only where the function insists on the parameter (e.g. optional material).
            if pname is not None and sig.parameters[pname].default is inspect.Parameter.empty:
                kwargs[pname] = None
            continue
        if pname is None:
            if accepts_var_kw:
                kwargs[_PARAM_ALIASES.get(key, [key])[0]] = val
            continue  # e.g. real API has no gravity parameter: hard OOD rule still applies afterwards
        v = val
        if key == "o2" and any(t in pname for t in ("fraction", "frac", "xo2")):
            v = val / 100.0
        elif key == "pressure" and pname.endswith("kpa"):
            v = val / PRESSURE_TO_PSIA["kpa"]
        elif key == "pressure" and pname.endswith("atm"):
            v = val / PRESSURE_TO_PSIA["atm"]
        elif key == "flow" and pname.endswith("mm_s"):
            v = val * 10.0
        elif key == "flow" and pname.endswith("m_s") and not pname.endswith("cm_s"):
            v = val / 100.0
        elif key == "gravity" and pname in ("gravity_g", "g"):
            v = copilot_mock_api.GRAVITY_G.get(val, val)
        kwargs[pname] = v
    missing = [
        p.name for p in sig.parameters.values()
        if p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name not in kwargs
    ]
    if missing:
        raise ToolInputError(
            f"api.{func_name} requires parameters the Copilot cannot map: {missing}",
            kind="api_contract_mismatch",
            hint="See docs/copilot_integration.md",
        )
    out = fn(**kwargs)
    if not isinstance(out, dict):
        out = {"value": out}
    return _standardize(out)


def _standardize(out: dict[str, Any]) -> dict[str, Any]:
    """Guarantee the contract keys exist, accepting a few likely alternative names."""
    res = dict(out)
    if "ood_flag" not in res:
        res["ood_flag"] = bool(res.get("ood", res.get("is_ood", False)))
    if "ood_reason" not in res:
        res["ood_reason"] = res.get("ood_reasons") if isinstance(res.get("ood_reasons"), str) else None
    res.setdefault("value", None)
    res.setdefault("interval", res.get("ci", res.get("prediction_interval")))
    res.setdefault("evidence", [])
    return _jsonable(res)


def _jsonable(x: Any) -> Any:
    """Convert numpy / pandas scalars and containers into plain JSON types."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "tolist"):
        return _jsonable(x.tolist())
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            return x.item()
        except Exception:  # noqa: BLE001
            return str(x)
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


# =========================================================================== #
# Normalization + OOD helpers
# =========================================================================== #
def _envelope_reasons(o2: float | None, pressure: float | None, flow: float | None) -> list[str]:
    """Training-envelope check done by the Copilot itself (independent of the model's own flag)."""
    env = training_envelope()
    if not env:
        return []
    reasons = []
    for key, val, label, unit in (
        ("o2_percent", o2, "O2", "%"),
        ("pressure_psia", pressure, "pressure", " psia"),
        ("flow_velocity_cm_s", flow, "flow", " cm/s"),
    ):
        rng = env.get(key)
        if val is None or not (isinstance(rng, (list, tuple)) and len(rng) == 2):
            continue
        lo, hi = float(rng[0]), float(rng[1])
        if not lo <= val <= hi:
            reasons.append(f"{label} {val:g}{unit} outside training range {lo:g}–{hi:g}{unit}")
    return reasons


def _merge_ood(result: dict[str, Any], extra_reasons: list[str], gravity: str | None) -> dict[str, Any]:
    reasons: list[str] = []
    if gravity is not None and gravity != "micro":
        reasons.append(GRAVITY_OOD_REASON)
    raw = result.get("ood_reason")
    if isinstance(raw, list):
        reasons.extend(str(r) for r in raw)
    elif raw:
        reasons.extend(r.strip() for r in str(raw).split(";") if r.strip())
    elif result.get("ood_flag"):
        reasons.append("model flagged this input as out of distribution")
    reasons.extend(extra_reasons)
    seen, uniq = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    result["ood_flag"] = bool(uniq)
    result["ood_reasons"] = uniq
    result["ood_reason"] = "; ".join(uniq) or None
    return result


def _apply_preset(args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    preset_name = args.get("preset")
    if not preset_name:
        return args, None
    p = get_mission_preset(preset_name)
    if "error" in p:
        raise ToolInputError(p["error"]["message"], kind="unknown_preset", hint=p["error"].get("hint"))
    merged = {"o2_percent": p["o2_percent"], "pressure_psia": p["pressure_psia"], "gravity": p["gravity"]}
    merged.update({k: v for k, v in args.items() if v not in (None, "")})
    return merged, p["name"]


def _normalize_scenario(args: dict[str, Any], need_flow: bool, need_o2: bool = True) -> dict[str, Any]:
    args, preset = _apply_preset(dict(args))
    notes: list[str] = []
    out: dict[str, Any] = {"preset": preset}
    known = known_materials()
    if "material" in args or need_o2:
        canonical, raw = resolve_material(args.get("material"), known)
        out["material"], out["material_input"] = canonical, raw
        if canonical and canonical != raw:
            notes.append(f"material '{raw}' -> {canonical}")
    if need_o2 or args.get("o2_percent") is not None:
        out["o2"], n = parse_o2_percent(args.get("o2_percent"))
        notes += [n] if n else []
    out["pressure"], n = parse_pressure_psia(args.get("pressure_psia"))
    notes += [n] if n else []
    flow_arg = args.get("flow_velocity_cm_s")
    if need_flow or flow_arg not in (None, ""):
        out["flow"], n = parse_flow_cm_s(flow_arg)
        notes += [n] if n else []
    else:
        out["flow"] = None
    out["gravity"], out["gravity_g"] = parse_gravity(args.get("gravity"))
    out["notes"] = notes
    return out


def _inputs_view(n: dict[str, Any]) -> dict[str, Any]:
    v = {
        "material": n.get("material") or n.get("material_input"),
        "o2_percent": n.get("o2"),
        "pressure_psia": n.get("pressure"),
        "pressure_kpa": round(n["pressure"] / PRESSURE_TO_PSIA["kpa"], 1) if n.get("pressure") else None,
        "flow_velocity_cm_s": n.get("flow"),
        "gravity": n.get("gravity"),
        "gravity_g": n.get("gravity_g"),
    }
    if n.get("preset"):
        v["preset"] = n["preset"]
    return {k: val for k, val in v.items() if val is not None}


def _unknown_material_result(n: dict[str, Any], known: list[str]) -> dict[str, Any]:
    res = {
        "value": None,
        "interval": None,
        "evidence": [],
        "ood_flag": True,
        "ood_reason": f"material '{n['material_input']}' not in training data",
        "known_materials": known,
        "note": "No prediction is available for this material. Do not estimate one.",
    }
    return res


def _finish(result: dict[str, Any], n: dict[str, Any], extra: list[str]) -> dict[str, Any]:
    result = _merge_ood(result, extra, n.get("gravity"))
    result["inputs_normalized"] = _inputs_view(n)
    if n.get("notes"):
        result["unit_conversions"] = n["notes"]
    result["backend"] = BACKEND.name
    return result


# =========================================================================== #
# Tools
# =========================================================================== #
def tool_predict(args: dict[str, Any]) -> dict[str, Any]:
    n = _normalize_scenario(args, need_flow=True)
    known = known_materials()
    if n["material"] is None and known:
        return _finish(_unknown_material_result(n, known), n, [])
    res = _call_api(
        "predict",
        {"material": n["material"] or n["material_input"], "o2": n["o2"], "pressure": n["pressure"], "flow": n["flow"], "gravity": n["gravity"]},
    )
    return _finish(res, n, _envelope_reasons(n["o2"], n["pressure"], n["flow"]))


def tool_flammability_boundary(args: dict[str, Any]) -> dict[str, Any]:
    n = _normalize_scenario(args, need_flow=False, need_o2=False)
    known = known_materials()
    if n["material"] is None and known:
        return _finish(_unknown_material_result(n, known), n, [])
    flows = args.get("flow_velocities_cm_s")
    if flows:
        flows = [parse_flow_cm_s(f)[0] for f in flows]
    res = _call_api(
        "flammability_boundary",
        {"material": n["material"] or n["material_input"], "pressure": n["pressure"], "gravity": n["gravity"], "flows": flows},
    )
    # Where does the cabin O2 sit relative to the curve? Done in code so the LLM never compares numbers itself.
    # O2 comes from the explicit argument, else from the preset.
    o2_arg = args.get("o2_percent")
    if o2_arg in (None, "") and n.get("preset"):
        o2_arg = get_mission_preset(n["preset"]).get("o2_percent")
    if o2_arg not in (None, "") and isinstance(res.get("value"), list):
        o2, note = parse_o2_percent(o2_arg)
        n["o2"] = o2
        if note:
            n["notes"].append(note)
        pts = [p for p in res["value"] if isinstance(p, dict) and p.get("o2_percent_limit") is not None]
        res["at_o2_percent"] = o2
        res["flows_where_flammable_cm_s"] = [p.get("flow_velocity_cm_s") for p in pts if o2 > p["o2_percent_limit"]]
        res["flows_where_not_flammable_cm_s"] = [p.get("flow_velocity_cm_s") for p in pts if o2 <= p["o2_percent_limit"]]
        res["flammable_at_some_flow"] = bool(res["flows_where_flammable_cm_s"])
        res["comparison_note"] = (
            f"At {o2:g}% O2 the material burns at the flows listed in flows_where_flammable_cm_s and "
            "self-extinguishes at the flows in flows_where_not_flammable_cm_s (computed in code)."
        )
    return _finish(res, n, _envelope_reasons(n.get("o2"), n["pressure"], None))


def tool_nearest_experiments(args: dict[str, Any]) -> dict[str, Any]:
    a = dict(args)
    k = max(1, min(int(a.pop("k", 3) or 3), 10))
    notes: list[str] = []
    # Flow is optional here: an undefined "fans off" just removes the flow constraint.
    if is_fans_off(a.get("flow_velocity_cm_s")):
        try:
            resolve_fans_off_flow()
        except ToolInputError:
            a.pop("flow_velocity_cm_s")
            notes.append("'fans off' flow undefined: neighbours searched without a flow constraint")
    if a.get("material"):
        n = _normalize_scenario(a, need_flow=False, need_o2=True)
    else:
        a, preset = _apply_preset(a)
        n = {"material": None, "material_input": None, "preset": preset, "notes": []}
        n["o2"], o2_note = parse_o2_percent(a.get("o2_percent"))
        n["pressure"], p_note = parse_pressure_psia(a.get("pressure_psia"))
        n["flow"], f_note = parse_flow_cm_s(a["flow_velocity_cm_s"]) if a.get("flow_velocity_cm_s") not in (None, "") else (None, None)
        n["gravity"], n["gravity_g"] = parse_gravity(a.get("gravity"))
        n["notes"] += [x for x in (o2_note, p_note, f_note) if x]
    n["notes"] += notes
    res = _call_api(
        "nearest_experiments",
        {"material": n["material"] or n.get("material_input"), "o2": n["o2"], "pressure": n["pressure"], "flow": n["flow"], "gravity": n["gravity"], "k": k},
    )
    return _finish(res, n, _envelope_reasons(n["o2"], n["pressure"], n["flow"]))


def tool_compare_scenarios(args: dict[str, Any]) -> dict[str, Any]:
    scenarios = args.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise ToolInputError("compare_scenarios needs a list of at least 2 scenarios.")
    if len(scenarios) > 6:
        raise ToolInputError("compare_scenarios accepts at most 6 scenarios.")
    known = known_materials()
    normalized, api_scenarios, notes, extra, gravities = [], [], [], [], []
    shared_material = args.get("material")
    for i, s in enumerate(scenarios):
        if not isinstance(s, dict):
            raise ToolInputError(f"scenario {i + 1} must be an object.")
        s = {**({"material": shared_material} if shared_material and not s.get("material") else {}), **s}
        n = _normalize_scenario(s, need_flow=True)
        label = s.get("label") or n.get("preset") or f"scenario {i + 1}"
        if n["material"] is None and known:
            return _finish(_unknown_material_result(n, known), n, [])
        normalized.append({"label": label, **_inputs_view(n)})
        api_scenarios.append({
            "label": label, "material": n["material"], "o2_percent": n["o2"], "pressure_psia": n["pressure"],
            "flow_velocity_cm_s": n["flow"], "gravity": n["gravity"],
        })
        notes += [f"{label}: {x}" for x in n["notes"]]
        extra += [f"{label}: {r}" for r in _envelope_reasons(n["o2"], n["pressure"], n["flow"])]
        if n["gravity"] != "micro":
            extra.append(f"{label}: {GRAVITY_OOD_REASON}")
        gravities.append(n["gravity"])
    res = _call_api("compare_scenarios", {"scenarios": api_scenarios})
    # Hard rule per scenario, inside the per-scenario results too.
    if isinstance(res.get("value"), list):
        for r, g in zip(res["value"], gravities):
            if isinstance(r, dict):
                _merge_ood(r, [], g)
    res = _merge_ood(res, extra, None)
    res["inputs_normalized"] = normalized
    if notes:
        res["unit_conversions"] = notes
    res["backend"] = BACKEND.name
    return res


def _load_repo_presets() -> dict[str, dict[str, Any]] | None:
    mod = BACKEND.load()
    for holder in (mod,):
        p = getattr(holder, "MISSION_PRESETS", None) or getattr(holder, "PRESETS", None)
        if isinstance(p, dict) and p:
            return p
    return None


def _match_preset(name: str, presets: dict[str, Any]) -> str | None:
    low = (name or "").strip().lower()
    for k in presets:
        if k.lower() == low:
            return k
    for canonical, aliases in PRESET_ALIASES.items():
        if canonical in presets and (low == canonical.lower() or any(a == low or re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", low) for a in aliases)):
            return canonical
    for k in presets:
        if low and (low in k.lower() or k.lower() in low):
            return k
    return None


def get_mission_preset(name: str) -> dict[str, Any]:
    repo = _load_repo_presets()
    presets = repo or BRIEF_PRESETS
    source = "Layer 1 API presets" if repo else "team brief (mirrored in src/copilot_tools.py; no preset module in repo yet)"
    key = _match_preset(name, presets)
    if key is None:
        return {"error": {"type": "unknown_preset", "message": f"No mission preset matches '{name}'.", "hint": f"Available: {', '.join(presets)}"}}
    p = dict(presets[key])
    if "gravity" in p:
        label, g = parse_gravity(p["gravity"])
        p["gravity"], p["gravity_g"] = label, g
    out = {"name": key, **p, "source": source,
           "note": "Presets do not include a ventilation flow. Ask for it, or use flammability_boundary to cover all flows."}
    return _merge_ood(out, [], p.get("gravity"))


def tool_get_mission_preset(args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    if not name:
        raise ToolInputError("name is required.", hint=f"Available: {', '.join(_load_repo_presets() or BRIEF_PRESETS)}")
    return get_mission_preset(str(name))


def tool_get_background_fact(args: dict[str, Any]) -> dict[str, Any]:
    out = copilot_facts.get_fact(str(args.get("topic") or ""))
    if "matches" in out:
        out["usage_note"] = "Background context only. Never use as a substitute for model predictions. Cite the source."
    return out


TOOL_IMPLS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "predict": tool_predict,
    "flammability_boundary": tool_flammability_boundary,
    "compare_scenarios": tool_compare_scenarios,
    "nearest_experiments": tool_nearest_experiments,
    "get_mission_preset": tool_get_mission_preset,
    "get_background_fact": tool_get_background_fact,
}


def dispatch(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    """Run one tool. Never raises: failures come back as {"error": {...}}."""
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"error": {"type": "unknown_tool", "message": f"No tool named '{name}'.", "available": list(TOOL_IMPLS)}}
    try:
        return _jsonable(impl(dict(args or {})))
    except ToolInputError as e:
        err: dict[str, Any] = {"type": e.kind, "message": str(e)}
        if e.hint:
            err["hint"] = e.hint
        return {"error": err}
    except Exception as e:  # noqa: BLE001 - the agent must never crash on a tool
        return {"error": {"type": "tool_exception", "message": f"{type(e).__name__}: {e}"}}


# =========================================================================== #
# Declarations (JSON schema, provider-agnostic)
# =========================================================================== #
_NUM_OR_STR = {"anyOf": [{"type": "number"}, {"type": "string"}]}
_GRAVITY = {
    "type": "string",
    "description": "Gravity level: 'micro' (orbit/transit, default), 'lunar' (1/6 g), 'mars', 'earth' (1 g). "
    "Anything other than micro has NO training data and will be flagged OOD.",
}


def _material_desc() -> str:
    mats = known_materials()
    listed = f" Known: {', '.join(mats)}." if mats else ""
    return "Material name. Aliases like 'acrylic' (PMMA) or 'cotton' (Cotton-fiberglass) are resolved automatically." + listed


def _scenario_props() -> dict[str, Any]:
    return {
        "preset": {"type": "string", "description": "Optional mission preset ('ISS cabin', 'Artemis Exploration Atmosphere', "
                   "'Lunar surface habitat'). Fills O2, pressure and gravity; explicit fields override it."},
        "material": {"type": "string", "description": _material_desc()},
        "o2_percent": {**_NUM_OR_STR, "description": "Oxygen concentration in PERCENT (21 = 21%). '34%' or a fraction like 0.34 are also accepted."},
        "pressure_psia": {**_NUM_OR_STR, "description": "Absolute cabin pressure. A bare number is psia. Strings with units are converted: '56.5 kPa', '0.56 atm', '8.2 psi'."},
        "flow_velocity_cm_s": {**_NUM_OR_STR, "description": "Ventilation flow velocity at the sample in cm/s. Strings like '5 mm/s', '0.1 m/s' are converted. "
                               "Pass the literal string 'fans off' for ventilation shutdown (resolved to the Flammability Map's value, or an error if undefined)."},
        "gravity": _GRAVITY,
    }


def get_tool_declarations() -> list[dict[str, Any]]:
    sp = _scenario_props()
    return [
        {
            "name": "predict",
            "description": "Model prediction for ONE condition: burn vs. extinguish (with burn probability and its interval) and flame "
            "spread rate in mm/s with a 90% interval, plus OOD flag/reason and supporting experiment IDs. Needs a flow velocity; "
            "if the operator gave none, use flammability_boundary instead or state your assumption.",
            "parameters": {"type": "object", "properties": sp, "required": ["material"]},
        },
        {
            "name": "flammability_boundary",
            "description": "Limiting O2 (%) vs. flow velocity for a material at a pressure: above the curve it burns. Use this when no flow "
            "is given (e.g. 'is X safe on the ISS?') or for 'fans off' questions. If o2_percent is given, the result also lists the "
            "flows at which that O2 level is flammable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preset": sp["preset"], "material": sp["material"], "pressure_psia": sp["pressure_psia"], "gravity": sp["gravity"],
                    "o2_percent": {**sp["o2_percent"], "description": sp["o2_percent"]["description"] + " Optional: the cabin O2 to compare against the curve."},
                    "flow_velocities_cm_s": {"type": "array", "items": _NUM_OR_STR, "description": "Optional flow grid in cm/s."},
                },
                "required": ["material"],
            },
        },
        {
            "name": "compare_scenarios",
            "description": "Run predict() on 2–6 scenarios and return per-scenario results plus deltas/ratios vs. the first scenario. "
            "Every scenario needs a flow velocity (or 'fans off'). Use this for 'compare X vs Y' questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "material": {"type": "string", "description": "Optional material shared by all scenarios. " + _material_desc()},
                    "scenarios": {
                        "type": "array",
                        "items": {"type": "object", "properties": {"label": {"type": "string", "description": "Short scenario name."}, **sp}},
                        "description": "List of scenarios; the first is the baseline.",
                    },
                },
                "required": ["scenarios"],
            },
        },
        {
            "name": "nearest_experiments",
            "description": "The k closest experiments in the training data to a condition (IDs, campaign, conditions, outcome, distance). "
            "Call this to cite evidence for any safety verdict.",
            "parameters": {
                "type": "object",
                "properties": {**sp, "k": {"type": "integer", "description": "How many experiments (1–10, default 3)."}},
                "required": [],
            },
        },
        {
            "name": "get_mission_preset",
            "description": "Look up a mission preset (pressure, O2, gravity, data coverage status). Presets: ISS cabin, Artemis Exploration "
            "Atmosphere, Lunar surface habitat.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "Preset name or alias (e.g. 'ISS', 'Artemis', 'lunar')."}}, "required": ["name"]},
        },
        {
            "name": "get_background_fact",
            "description": "Curated, sourced background fact for 'why' questions (physics of microgravity flames, past experiments, "
            "atmosphere standards). Background only, never a substitute for predictions. Always cite the returned source.",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string", "description": "A topic key or free-text keywords. Keys: " + ", ".join(copilot_facts.TOPICS)}},
                "required": ["topic"],
            },
        },
    ]
