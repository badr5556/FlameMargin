# Copilot integration guide (Layer 3 → Layers 1 & 2)

Owner: Omar (Copilot). This file lists **every change the Copilot needs in files owned by
other teammates**. The Copilot never edits those files itself; please apply these diffs (or
tell Omar if you want a different shape).

## Current state (2026-11-14)

| Thing | Status on `main` | Copilot behaviour |
|---|---|---|
| `src/api.py` (Layer 1) | **real Prediction Engine** (SIBAL fabric, NASA BASS-II, `docs/model_card.md`) | used automatically; `backend = "real"` |
| `src/copilot_mock_api.py` | **test fixture only** (`COPILOT_FORCE_MOCK_API=1` in the unit tests) | never a silent fallback: if `src/api.py` cannot be imported, prediction tools return `engine_unavailable` |
| `app.py` (Layer 2) | full 4-tab app (evidence gap, map, Copilot, data & method); `src/copilot_ui.py` runs it on Streamlit Cloud | chat mounted in the Copilot tab |
| Mission presets | `api.MISSION_PRESETS` (ISS, Artemis EA, Lunar) | picked up automatically |
| "Fans OFF" flow value | **deliberately not defined**: no verified single fans-off number exists | `"fans off"` returns `fans_off_undefined`; the Copilot answers from the low-flow end of the boundary instead of guessing |
| Upgrades | per-session LLM budget (`COPILOT_SESSION_LLM_LIMIT`, default 15), backup key (`GEMINI_API_KEY_BACKUP`, tried before the backup model), claim-consistency check, assumption-line guard | see `src/copilot.py` |

The sections below are the original contract notes; parameter-name mapping still works the same way.

---

## 1. Teammate A: `src/api.py` contract the adapter expects

### 1.1 Functions (names are fixed; parameter names are flexible)

```python
def predict(material: str, o2_percent: float, pressure_psia: float,
            flow_velocity_cm_s: float, gravity: str = "micro") -> dict: ...

def flammability_boundary(material: str, pressure_psia: float, gravity: str = "micro",
                          flow_velocities_cm_s: list[float] | None = None) -> dict: ...

def compare_scenarios(scenarios: list[dict]) -> dict: ...
    # each scenario: {"label", "material", "o2_percent", "pressure_psia", "flow_velocity_cm_s", "gravity"}

def nearest_experiments(material: str | None, o2_percent: float, pressure_psia: float,
                        flow_velocity_cm_s: float | None = None, gravity: str = "micro",
                        k: int = 3) -> dict: ...
```

The adapter maps by parameter **name** (`inspect.signature`), so these alternatives also work and are unit-converted automatically:

| Quantity | Accepted parameter names | Unit sent |
|---|---|---|
| O2 | `o2_percent`, `o2_pct`, `oxygen_percent`, `o2`, `oxygen` | percent (21) |
| O2 | `o2_fraction`, `o2_frac`, `xo2`, `o2_mole_fraction` | fraction (0.21) |
| Pressure | `pressure_psia`, `pressure`, `p_psia` | psia |
| Pressure | `pressure_kpa`, `p_kpa` / `pressure_atm` | kPa / atm |
| Flow | `flow_velocity_cm_s`, `flow_cm_s`, `flow_velocity`, `flow`, `velocity_cm_s`, `u_cm_s` | cm/s |
| Flow | `flow_mm_s` / `flow_m_s` | mm/s / m/s |
| Gravity | `gravity`, `gravity_level`, `g_level` (label) or `gravity_g`, `g` (number) | `"micro"`/`"lunar"`/`"mars"`/`"earth"` or g |

If `predict` has **no gravity parameter**, that's fine: the Copilot still applies its hard rule
(any non-µg gravity → `ood_flag=True`, reason `no training data at this gravity level (the dataset is ISS microgravity only; ...)`).

### 1.2 Output keys (every function)

Required: `value`, `interval`, `ood_flag`, `ood_reason`, `evidence`.
(`ood` / `is_ood` and `ci` / `prediction_interval` are accepted as aliases.)

Strongly recommended for `predict` (the Copilot quotes these directly):

```python
{
  "label": "burn" | "extinguish",
  "burn_probability": 0.87, "burn_probability_interval": [0.78, 0.94],
  "value": 1.92, "unit": "mm/s", "interval": [1.41, 2.51], "interval_level": 0.9,
  "limiting_o2_percent": 24.1,
  "ood_flag": False, "ood_reason": None,
  "evidence": ["BASS-II-...", "SIBAL-..."],   # experiment IDs used by nearest_experiments
}
```

`flammability_boundary` → `value` = `[{"flow_velocity_cm_s": u, "o2_percent_limit": x}, ...]`,
`interval` = one `[lo, hi]` per point. Optional: `min_o2_percent_limit`, `flow_at_min_limit_cm_s`.

`nearest_experiments` → `value` = list of dicts with `id`, `campaign`, `material`, `o2_percent`,
`pressure_psia`, `flow_velocity_cm_s`, `outcome`, `distance`.

numpy / pandas types are converted automatically; NaN becomes `null`.

### 1.3 Optional module-level constants (picked up automatically)

```python
MATERIALS = ["PMMA", "Nomex", "Cotton-fiberglass", ...]   # or a dict keyed by name
TRAINING_ENVELOPE = {                                         # enables Copilot-side range checks
    "o2_percent": (lo, hi), "pressure_psia": (lo, hi), "flow_velocity_cm_s": (lo, hi),
}
MISSION_PRESETS = {"ISS cabin": {"pressure_psia": 14.7, "o2_percent": 21.0, "gravity": "micro"}, ...}
```

If `MATERIALS` is present, unknown materials are answered with "not in training data" instead of calling the model.

---

## 2. Teammate B: `app.py` changes

### 2.1 Define the "Fans OFF" flow value (needed for the Artemis + fans-off demo)

The Copilot finds this constant by **reading** `app.py` / `src/*.py` (it never imports `app.py`).
Name must start with `FANS_OFF` and contain `FLOW`/`VEL`/`SPEED`; suffix sets the unit (`_CM_S` default, `_MM_S`, `_M_S`).

```diff
+# Residual flow velocity used by the "Fans OFF" slider (cm/s). Shared with the Copilot.
+FANS_OFF_FLOW_CM_S = <agreed value>   # e.g. from SIBAL quench range; team to decide, not the Copilot
```

Until then, for a demo only, Omar can set it without touching code:

```bash
export FLAMEMARGIN_FANS_OFF_FLOW_CM_S=<agreed value>
```

### 2.2 Mount the chat (2–3 lines)

```diff
+from src.copilot_ui import render_copilot_chat
 ...
+with st.expander("🔥 Fire Safety Copilot", expanded=True):   # or inside a tab / st.sidebar
+    render_copilot_chat(key_prefix="copilot")
```

`render_copilot_chat` keeps its state under `st.session_state["copilot_*"]` and calls no `st.set_page_config`, so it is safe to mount anywhere.

---

## 3. Dependencies and secrets

`requirements.txt` needs these lines (added by the Copilot PR; append-only):

```
google-genai>=1.0
streamlit>=1.37
python-dotenv>=1.0
PyYAML>=6.0
pytest>=8.0
```

Gemini key lookup order: `GEMINI_API_KEY` env var → `st.secrets["GEMINI_API_KEY"]` (Streamlit Cloud) → `.env` (local).
Optional: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`), `GEMINI_FALLBACK_MODEL` (default `gemini-3.1-flash-lite`).
`.env` and `.streamlit/secrets.toml` are git-ignored. **Never commit a key.**

Streamlit Cloud → App settings → Secrets:

```toml
GEMINI_API_KEY = "..."
```

## 4. Smoke checks after integration

```bash
python -c "from src.copilot_tools import backend_name; print(backend_name())"   # expect: real
```

```bash
python -m src.copilot "Is Nomex safe in the Artemis atmosphere with fans off?"
```

```bash
pytest tests/test_copilot.py -q
```

```bash
python evals/run_evals.py --mode both
```
