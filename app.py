"""FlameMargin: the full app (Evidence Gap + Flammability Map + Fire Safety Copilot + Data & Method).

    streamlit run app.py

The deployed entry point (Streamlit Cloud) is src/copilot_ui.py, whose __main__ block calls app.main(),
so both commands serve this same 4-tab app.
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


def _safety() -> dict | None:
    p = ROOT / "models" / "safety_operating_point.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _history() -> dict:
    return json.loads((ROOT / "models" / "metrics_history.json").read_text(encoding="utf-8"))


def _header() -> None:
    st.markdown("## 🔥 FlameMargin")
    st.caption(f"{TAGLINE}  ·  Team IGNISPHERE · NASA Space Apps Cairo 2026 · *Flame in Freefall*")
    m = _metrics()
    best, base = m["models"][m["chosen_model"]], m["models"]["baseline"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Leave-one-test-out AUC", f"{best['auc']:.2f}",
              help="How well the model ranks burns above extinctions on NASA tests it never saw (every point of a test held "
                   "out together). 0.5 = coin flip, 1 = perfect ranking.")
    c2.metric("Brier skill vs baseline", f"{brier_skill(best['brier'], base['brier']):+.0%}",
              help=f"1 − Brier(model) / Brier(baseline) = 1 − {best['brier']} / {base['brier']} (leave-one-test-out, "
                   "models/metrics_v2.json). The baseline always predicts the training burn rate; positive = better than it.")
    c3.metric("NASA training points", f"{m['data']['n_points']}",
              help=f"from {m['data']['n_tests']} BASS-II tests (all 126 tests of NASA/TM-20210011385 Appendix A were transcribed)")
    c4.metric("Materials in data", f"{len(m['data']['families'])}",
              help="SIBAL fabric, PMMA film, PMMA slab, PMMA rod, Nomex. Any other material is out of distribution.")
    c5.metric("Artemis EA (8.2 psia / 34%)", "OOD", help="Outside NASA's BASS-II microgravity data for every material (pressure and O2).")


AUC_FOOTNOTE = ("AUC note: the prior baseline and the GP are near-constant predictors under leave-one-test-out; their AUC is "
                "degenerate (<0.5) because the held-out test shifts the training prior. Compare on Brier and log-loss.")


def brier_skill(model_brier: float, baseline_brier: float) -> float:
    """Brier skill score vs the prior baseline: 1 - Brier(model) / Brier(baseline)."""
    return 1.0 - model_brier / baseline_brier


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
             "balanced accuracy": r["balanced_accuracy"], "Brier ↓": r["brier"], "log-loss ↓": r["log_loss"], "AUC¹": r["auc"],
             "n points": r["n_points"]} for k, r in m["models"].items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(m["selection_note"] + " Accuracy is high for every model because 86% of the points are burns; "
               "compare on Brier, log-loss and AUC.")
    st.caption("¹ " + AUC_FOOTNOTE)
    v1, v2o = h["v1"]["chosen"], h["v2_on_v1_points"]["chosen"]
    st.markdown(
        "### Before / after (v1 → v2)\n"
        f"- v1: {h['v1']['n_points']} SIBAL points from {h['v1']['n_tests']} tests, {h['v1']['chosen_model']}, LOTO Brier {v1['brier']}.\n"
        f"- v2: {h['v2']['n_points']} points from {h['v2']['n_tests']} tests, 5 materials, {h['v2']['chosen_model']}, "
        f"LOTO Brier {h['v2']['chosen']['brier']} (baseline {h['v2']['baseline']['brier']}).\n"
        f"- On the same 21 v1 points, v2's out-of-fold Brier is {v2o['brier']} (v1: {v1['brier']})."
    )
    _render_v21_section(m, h)
    _render_safety_section()
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


def _render_v21_section(m: dict, h: dict) -> None:
    """Engine v2.1: the single pre-registered experiment, reported next to the production v2 whether or not it shipped."""
    pre = m.get("v21_preregistered")
    if not pre:
        return
    v2, v21 = m["models"][pre["v2_model"]], m["models"]["logreg21"]
    ext = pre["extinguished_points_below_p_0_5"]
    pf2, pf21 = m["per_family"][pre["v2_model"]], m["per_family"]["logreg21"]
    on1 = m["on_v1_points"]["models"]
    rows = [
        ("Brier ↓ (unrounded, 5 decimals: the ship metric)", f"{pre.get('v2_brier_5dp', 0):.5f}", f"{pre.get('v21_brier_5dp', 0):.5f}"),
        ("Brier ↓ (3 decimals)", v2["brier"], v21["brier"]),
        ("Log-loss ↓", v2["log_loss"], v21["log_loss"]),
        ("AUC", v2["auc"], v21["auc"]),
        ("Brier on SIBAL fabric", pf2["SIBAL_fabric"]["brier"], pf21["SIBAL_fabric"]["brier"]),
        ("Brier on PMMA slab", pf2["PMMA_slab"]["brier"], pf21["PMMA_slab"]["brier"]),
        (f"Brier on the 21 v1 points (v1: {h['v1']['chosen']['brier']})", on1[pre["v2_model"]]["brier"], on1["logreg21"]["brier"]),
        ("O2 curves that decrease", f"{m['monotonicity_check'][pre['v2_model']]['violated']} / {m['monotonicity_check'][pre['v2_model']]['curves']}",
         f"{m['monotonicity_check']['logreg21']['violated']} / {m['monotonicity_check']['logreg21']['curves']}"),
        ("Extinguished NASA points with P(burn) < 0.5 (final model / out of fold)",
         f"{ext['logreg']['in_sample_final_model']} / {ext['logreg']['out_of_fold']} of {ext['logreg']['n_extinguished']}",
         f"{ext['logreg21']['in_sample_final_model']} / {ext['logreg21']['out_of_fold']} of {ext['logreg21']['n_extinguished']}"),
    ]
    st.markdown("### Engine v2.1: a pre-registered experiment that did not beat v2")
    st.markdown(
        f"Written and committed before fitting: add `material × log10(flow)` and `× log10(flow)²` terms only for SIBAL fabric "
        f"and PMMA slab (both classes, ≥ 8 extinctions), same C = 1.0, same leave-one-test-out protocol. Ship rule: "
        f"*{pre['ship_rule']}*. Result: **{'shipped' if pre['shipped'] else 'not shipped: v2 stays in production'}**. "
        f"Rule note: {pre.get('rule_amendment', '')}"
    )
    st.dataframe(pd.DataFrame([{"leave-one-test-out": r[0], "v2 (production)": str(r[1]), "v2.1 (experiment)": str(r[2])}
                               for r in rows]),
                 hide_index=True, use_container_width=True)
    st.caption("v2.1 loses on the ship metric (unrounded Brier) and on log-loss and AUC. It is slightly better on SIBAL and "
               "the v1 points, slightly worse on PMMA slab, and moves no extra extinguished NASA point below P = 0.5. "
               "No other variant was fitted.")


def _render_safety_section() -> None:
    """Safety operating point (a missed burn is the costly error) + reliability plot, both leave-one-test-out."""
    sf = _safety()
    if not sf:
        return
    from src.safety_eval import reliability_figure

    v, t = sf["verdict_threshold"], sf["safety_threshold"]
    st.markdown("### Safety operating point (leave-one-test-out)")
    st.markdown(
        "For fire safety the costly error is a **missed burn**: saying *won't burn* where NASA saw a flame. "
        f"Burn recall = share of NASA burn points called *burn*; false-*safe* rate = share of *won't burn* calls that were burns."
    )
    rows = [{"threshold on P(burn)": f"{r['threshold']:.2f}" + note, "burn recall": r["burn_recall"],
             "missed burns": f"{r['missed_burns']} of {r['n_burn']}", "false-safe rate": r["false_safe_rate"],
             "'won't burn' calls": r["n_safe_calls"], "extinguished recall": r["extinguished_recall"]}
            for r, note in ((v, " (verdict, used by the readout)"),
                            (t, f" (largest with burn recall ≥ {sf['target_burn_recall']:g})"))]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        f"The readout keeps the {v['threshold']:.1f} verdict line (an exact tie counts as burn). It is already more conservative "
        f"than the ≥ {sf['target_burn_recall']:g} recall target needs: the largest threshold meeting that target, "
        f"{t['threshold']:.2f}, would catch more extinctions ({t['extinguished_recall']} vs {v['extinguished_recall']}) but miss "
        f"{t['missed_burns']} NASA burns instead of {v['missed_burns']}. The price of 0.5: the model rarely says *won't burn* "
        f"({v['n_safe_calls']} of {sf['n_points']} points), and only {v['extinguished_recall']:.0%} of NASA extinctions are called."
    )
    st.markdown("### Reliability (calibration)")
    st.plotly_chart(reliability_figure(sf["reliability"], sf["model"]), use_container_width=True, key="reliability",
                    config={"displayModeBar": False})
    st.caption("Out-of-fold P(burn) binned by 0.2; marker size and label = number of points in the bin. Points on the dotted "
               "diagonal are perfectly calibrated. The 0.2–0.4 bin is empty; the 0.6–0.8 bin is under-confident.")


def main() -> None:
    st.set_page_config(page_title="FlameMargin", page_icon="🔥", layout="wide")
    from src.copilot_ui import render_copilot_chat
    from src.evidence_gap import render_evidence_tab
    from src.map_ui import render_map_tab

    _header()
    tab_gap, tab_map, tab_copilot, tab_method = st.tabs(["🧭 Evidence Gap", "🔥 Flammability Map", "🤖 Copilot", "📚 Data & Method"])
    with tab_gap:
        try:
            render_evidence_tab(st)
        except Exception as e:  # noqa: BLE001 - one failing tab must not take the demo down
            st.error(f"The Evidence Gap view could not be drawn ({type(e).__name__}). The other tabs still work.")
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
