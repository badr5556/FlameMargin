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


@st.cache_data(show_spinner="Computing the flammability map…")
def _grid(width: float) -> dict:
    return _engine().boundary_grid(width)


@st.cache_data(show_spinner=False, max_entries=512)
def _predict(**kw) -> dict:
    return _engine().predict(**kw)


def _metrics() -> dict:
    return json.loads((ROOT / "models" / "metrics.json").read_text(encoding="utf-8"))


def _header() -> None:
    st.markdown("## 🔥 FlameMargin")
    st.caption(f"{TAGLINE}  ·  Team IGNISPHERE · NASA Space Apps Cairo 2026 · *Flame in Freefall*")
    m = _metrics()
    best = m["models"][m["chosen_model"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("NASA training points", f"{m['data']['n_points']}", help=f"from {m['data']['n_tests']} BASS-II tests, NASA/TM-20210011385 Table 7.1")
    c2.metric("Model Brier (LOTO)", f"{best['brier']:.3f}", delta=f"{best['brier'] - m['models']['baseline']['brier']:+.3f} vs baseline",
              delta_color="inverse", help="Leave-one-test-out Brier score; lower is better.")
    c3.metric("Material in data", "SIBAL fabric", help="SIBAL cotton-fiberglass fabric only; every other material is out of distribution.")
    c4.metric("Artemis EA (8.2 psia / 34%)", "OOD", help="Outside NASA's microgravity data in this dataset (pressure and O2).")


def _render_method_tab() -> None:
    from src.data_pipeline.derive_points import RULES
    from src.features import load_display_points, load_points

    m = _metrics()
    st.markdown("### Data")
    st.markdown(
        f"- **Source:** {m['data']['source']}.\n"
        f"- **31 raw rows** (SIBAL fabric, 1 atm, ISS microgravity, O2 16.4–21.0%), turned into **{m['data']['n_points']} "
        f"burn/extinguish points from {m['data']['n_tests']} tests** ({m['data']['class_balance']['burn']} burn, "
        f"{m['data']['class_balance']['extinguished']} extinguished). 19 rows (8 reused samples, 11 without a definitive outcome) "
        "are shown on the map in grey but not used for training.\n"
        "- **No flame spread-rate values** exist in this extraction, so spread rate is not predicted.\n"
        f"- **Row verification: {m['data']['row_verification']}.**"
    )
    st.markdown("### Derivation rules (stored per point in `derivation_rule`)")
    st.dataframe(pd.DataFrame({"rule": list(RULES.values())}), hide_index=True, use_container_width=True)
    st.markdown("### Leave-one-test-out validation vs baseline")
    rows = [{"model": r["label"] + (" ← shipped" if k == m["chosen_model"] else ""), "accuracy": r["accuracy"],
             "balanced accuracy": r["balanced_accuracy"], "Brier ↓": r["brier"], "log-loss ↓": r["log_loss"], "n points": r["n_points"]}
            for k, r in m["models"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(m["selection_note"] + " The baseline's accuracy is below 50% because holding out a test shifts the training "
               "majority against it; compare on Brier and log-loss.")
    mono = m["monotonicity_check"]["chosen"]
    st.markdown(
        "### Uncertainty, OOD and sanity checks\n"
        f"- 90% interval: {m['bootstrap']['n_resamples']} bootstrap resamples over tests; reported as [0, 1] wherever the kNN check flags an extrapolation.\n"
        f"- OOD: hard rules ({m['ood']['hard_rules']}), then kNN distance > {m['ood']['knn_threshold']} "
        f"(95th percentile of leave-one-test-out nearest-neighbour distances).\n"
        f"- Monotonicity in O2 at {mono['flow_cm_s']:g} cm/s: **{'violated' if mono['violated'] else 'respected'}** by the shipped model "
        f"(peak P(burn) {mono['p_peak']} at {mono['o2_at_peak']:g}% O2, the highest labelled O2; it falls back to {mono['p_at_o2_hi']} "
        "at 21% because a Gaussian process reverts to its prior far from data). Reported, not hidden."
    )
    st.markdown(
        "### Limits\n"
        "- One material, one pressure (1 atm), microgravity only; labelled O2 only 16.4–18.7%.\n"
        "- 21 points from 12 tests: the gain over the baseline is small. Proof of pipeline on real NASA data, **not a flight-qualification tool**.\n"
        "- Decision support only, not a replacement for NASA-STD-6001 material testing."
    )
    st.markdown(
        f"**Read more:** [Model card]({REPO_URL}/blob/main/docs/model_card.md) · "
        f"[Science claims sheet]({REPO_URL}/blob/main/docs/science/claims_sheet.md) · "
        f"[Data package]({REPO_URL}/blob/main/docs/data/README.md) · "
        f"[31-row verification checklist]({REPO_URL}/blob/main/docs/data/verification_checklist.md)"
    )
    with st.expander("The 21 training points and the 19 display-only rows (31 extracted tests)"):
        st.dataframe(load_points(), hide_index=True, use_container_width=True)
        st.dataframe(load_display_points(), hide_index=True, use_container_width=True)


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
