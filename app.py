"""FlameMargin: the full app (Flammability Map + Fire Safety Copilot + Data & Method).

    streamlit run app.py

The deployed entry point (Streamlit Cloud) is src/copilot_ui.py, whose __main__ block calls app.main(),
so both commands serve this same 3-tab app.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

REPO_URL = "https://github.com/badr5556/FlameMargin"
TAGLINE = "How close is a material to burning in a spacecraft cabin, and does NASA's data actually cover that cabin?"


@st.cache_resource(show_spinner="Loading the Prediction Engine…")
def _engine():
    from src import api

    api.get_engine()
    return api


@st.cache_data(show_spinner="Computing the flammability map…", max_entries=64)
def _grid(**kw) -> dict:
    return _engine().boundary_grid(**kw)


@st.cache_data(show_spinner=False, max_entries=512)
def _predict(**kw) -> dict:
    return _engine().predict(**kw)


def _metrics() -> dict:
    return json.loads((ROOT / "models" / "metrics_v2.json").read_text(encoding="utf-8"))


def _history() -> dict:
    return json.loads((ROOT / "models" / "metrics_history.json").read_text(encoding="utf-8"))


def _header() -> None:
    st.markdown("## 🔥 FlameMargin")
    st.caption(f"{TAGLINE}  ·  Team IGNISPHERE · NASA Space Apps Cairo 2026 · *Flame in Freefall*")
    m = _metrics()
    best = m["models"][m["chosen_model"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NASA training points", f"{m['data']['n_points']}",
              help=f"from {m['data']['n_tests']} BASS-II tests (all 126 tests of NASA/TM-20210011385 Appendix A were transcribed)")
    c2.metric("Model Brier (LOTO)", f"{best['brier']:.3f}", delta=f"{best['brier'] - m['models']['baseline']['brier']:+.3f} vs baseline",
              delta_color="inverse", help="Leave-one-test-out Brier score; lower is better.")
    c3.metric("Materials in data", f"{len(m['data']['families'])}",
              help="SIBAL fabric, PMMA film, PMMA slab, PMMA rod, Nomex. Any other material is out of distribution.")
    c4.metric("Artemis EA (8.2 psia / 34%)", "OOD", help="Outside NASA's BASS-II microgravity data for every material (pressure and O2).")


def _render_method_tab() -> None:
    from src.model_v2 import load_points_v2

    m, h = _metrics(), _history()
    fams = m["data"]["families"]
    st.markdown("### Data")
    st.markdown(
        f"- **Source:** {m['data']['source']}.\n"
        "- **All 126 BASS-II tests transcribed** from Appendix A (Tables A.1–A.6), every row compared with the PDF; "
        "an independent 20% re-check with a second extractor passed 26/26 rows.\n"
        f"- Turned by written rules into **{m['data']['n_points']} training points from {m['data']['n_tests']} tests** "
        f"({m['data']['class_balance']['burn']} burn, {m['data']['class_balance']['extinguished']} extinguished; "
        f"{m['data']['label_confidence'].get('high', 0)} high- and {m['data']['label_confidence'].get('medium', 0)} medium-confidence). "
        "Every point carries a verbatim quote from the report and its page.\n"
        "- Calibrated O2 everywhere (the report's MCA-based daily offset). No value is read off a figure."
    )
    st.dataframe(pd.DataFrame([{"material": k, "points": v["n_points"], "tests": v["n_tests"], "burn": v["n_burn"],
                                "extinguished": v["n_extinguished"], "O2 % tested": f"{v['o2_percent'][0]:g}–{v['o2_percent'][1]:g}",
                                "flow cm/s tested": f"{v['flow_velocity_cm_s'][0]:g}–{v['flow_velocity_cm_s'][1]:g}",
                                "configurations": ", ".join(v["configurations"])} for k, v in fams.items()]),
                 hide_index=True, use_container_width=True)
    st.markdown("### Leave-one-test-out validation (v2) vs baseline")
    rows = [{"model": r["label"] + (" ← shipped" if k == m["chosen_model"] else ""), "accuracy": r["accuracy"],
             "balanced accuracy": r["balanced_accuracy"], "Brier ↓": r["brier"], "log-loss ↓": r["log_loss"], "AUC": r["auc"],
             "n points": r["n_points"]} for k, r in m["models"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(m["selection_note"] + " Accuracy is high for every model because 86% of the points are burns; "
               "compare on Brier, log-loss and AUC.")
    v1, v2o = h["v1"]["chosen"], h["v2_on_v1_points"]["chosen"]
    st.markdown(
        "### Before / after (v1 → v2)\n"
        f"- v1: {h['v1']['n_points']} SIBAL points from {h['v1']['n_tests']} tests, {h['v1']['chosen_model']}, LOTO Brier {v1['brier']}.\n"
        f"- v2: {h['v2']['n_points']} points from {h['v2']['n_tests']} tests, 5 materials, {h['v2']['chosen_model']}, "
        f"LOTO Brier {h['v2']['chosen']['brier']} (baseline {h['v2']['baseline']['brier']}).\n"
        f"- On the same 21 v1 points, v2's out-of-fold Brier is {v2o['brier']} (v1: {v1['brier']})."
    )
    mono = m["monotonicity_check"][m["chosen_model"]]
    st.markdown(
        "### Uncertainty, OOD and sanity checks\n"
        f"- 90% interval: {m['bootstrap']['n_resamples']} bootstrap resamples over tests; [0, 1] wherever the kNN check flags an extrapolation.\n"
        f"- OOD: hard rules ({m['ood']['hard_rules']}), then kNN distance to the same material's tests > {m['ood']['knn_threshold']} "
        "(95th percentile of leave-one-test-out nearest-neighbour distances).\n"
        f"- Monotonicity in O2 (shipped model): {mono['violated']} of {mono['curves']} O2 curves decrease somewhere "
        f"(largest drop {mono['max_drop']}). Reported, not hidden."
    )
    st.markdown(
        "### Limits\n"
        "- 1 atm and ISS microgravity only: no pressure or gravity dependence can be learned from BASS-II.\n"
        "- PMMA film points are all burns and Nomex points all non-sustained: the model repeats those tests, it cannot "
        "locate a boundary for them. PMMA rods were tested only up to 20.8% O2.\n"
        "- Proof of pipeline on real NASA data, **not a flight-qualification tool**; not a replacement for NASA-STD-6001 testing."
    )
    st.markdown(
        f"**Read more:** [Model card]({REPO_URL}/blob/main/docs/model_card.md) · "
        f"[Science claims sheet]({REPO_URL}/blob/main/docs/science/claims_sheet.md) · "
        f"[Extraction audit]({REPO_URL}/blob/main/docs/data/extraction_audit.md) · "
        f"[Data dictionary v2]({REPO_URL}/blob/main/docs/data/data_dictionary_v2.md)"
    )
    with st.expander("All labelled points (with rule, quote and page)"):
        st.dataframe(load_points_v2(training_only=False), hide_index=True, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="FlameMargin", page_icon="🔥", layout="wide")
    from src.copilot_ui import render_copilot_chat
    from src.map_ui import render_map_tab

    _header()
    tab_map, tab_copilot, tab_method = st.tabs(["🔥 Flammability Map", "🤖 Copilot", "📚 Data & Method"])
    with tab_map:
        try:
            _engine()
            render_map_tab(st, _grid, _predict)
        except Exception as e:  # noqa: BLE001 - one failing tab must not take the demo down
            st.error(f"The map could not be drawn ({type(e).__name__}). The Copilot and Data tabs still work.")
    with tab_copilot:
        render_copilot_chat(key_prefix="copilot")
    with tab_method:
        _render_method_tab()
    st.caption("Decision support only, not a replacement for NASA-STD-6001 material testing. "
               "Data: NASA Glenn Research Center, NASA/TM-20210011385 (BASS-II).")


if __name__ == "__main__":
    main()
