"""Layer 2: the Flammability Map v2 (Plotly figure + Streamlit tab), one material at a time.

The figure is built by ``build_map_figure`` (pure function, testable without Streamlit);
``render_map_tab`` adds the controls (material, thickness / size / configuration where relevant,
mission preset, ventilation) and the live readout card.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import api
from src.model_v2 import SIZE_KIND, load_points_v2

# Fire palette for P(burn): cool (extinguish) -> hot (burn).
P_COLORSCALE = [
    [0.0, "#1b3a5c"], [0.25, "#3f6e8c"], [0.45, "#9fb3bf"], [0.5, "#f2e6c9"],
    [0.6, "#f7b267"], [0.8, "#f4743b"], [1.0, "#c0261b"],
]
OOD_FILL = "rgba(70,70,78,0.78)"
EXTRAP_FILL = "rgba(40,40,48,0.55)"

FLOW_SLIDER_HELP = (
    "Forced-flow speed at the sample. Context only (verified claims): typical spacecraft air circulation is about "
    "20–25 cm/s (Saffire, claim C8b), and SIBAL flames were quenched at 1–5 cm/s in microgravity (claim C3). "
    "The low end of this slider means 'Fans OFF / near-quiescent'. We do not assign a single fans-off number: "
    "residual flow with fans off is not measured in our data."
)
MATERIAL_HELP = {
    "SIBAL fabric": "SIBAL cotton-fiberglass fabric, concurrent flow (Table 7.1 + Table A.6).",
    "PMMA film": "Thin PMMA film 0.1–0.4 mm, opposed flow (Table A.1). Every labelled point is a burn: the extinctions "
                 "happened at fan-potentiometer settings with no cm/s value.",
    "PMMA slab": "PMMA slab 1–5 mm, opposed flow (Table A.4 + Table 5.1). Has burn and extinction points and measured spread rates.",
    "PMMA rod": "Cast PMMA rods 6.35–12.7 mm in opposed, concurrent or stagnation flow (Tables A.3, A.5). Tested only up to 20.8% O2.",
    "Nomex": "Nomex III fabric, concurrent flow (Table A.2). Only 3 tests, none sustained a flame (F1, F2, F3).",
}


@lru_cache(maxsize=1)
def all_points() -> pd.DataFrame:
    """Every v2 point (training and display-only), read once."""
    return load_points_v2(training_only=False)


def _short(q: str, n: int = 150) -> str:
    q = str(q)
    return q if len(q) <= n else q[: n - 1] + "…"


def _hover_point(r: pd.Series) -> str:
    out = "burn" if int(r["burn"]) == 1 else "extinguished"
    used = "" if bool(r["include_in_training"]) else f"<br><i>not used for training: {r['exclusion_reason']}</i>"
    return (f"<b>{r['test_id']}</b> · {r['pi']} (Table {r['pi_table']})<br>O2 {r['o2_pct']:g}% · flow {r['flow_cm_s']:g} cm/s"
            f" · {r['flow_configuration']}<br>Outcome: <b>{out}</b> ({r['label_confidence']}, {r['derivation_rule']})"
            f"<br>“{_short(r['evidence_quote'])}”<br>NASA/TM-20210011385 p. {int(r['source_page'])}{used}")


def build_map_figure(grid: dict[str, Any], marker: dict[str, Any] | None = None, y_range: tuple[float, float] = (13.0, 23.0)) -> go.Figure:
    """Heatmap of P(burn) over O2 x flow (log), 0.5 contour, band edges, OOD shading and the material's NASA points."""
    o2 = np.asarray(grid["o2_percent"])
    flow = np.asarray(grid["flow_velocity_cm_s"])
    P = np.asarray(grid["p_burn"])
    LO, HI = np.asarray(grid["p_lo"]), np.asarray(grid["p_hi"])
    in_dist = np.asarray(grid["in_distribution"])
    inside_hard = np.asarray(grid["inside_hard_envelope"])
    fam, env = grid["material_family"], grid["envelope"]
    y0, y1 = y_range
    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        x=flow, y=o2, z=P, zmin=0, zmax=1, colorscale=P_COLORSCALE, name="P(burn)",
        colorbar=dict(title="P(burn)", thickness=14, len=0.75),
        hovertemplate="flow %{x:.1f} cm/s<br>O2 %{y:.1f}%<br>P(burn) %{z:.2f}<extra></extra>",
    ))
    extrap = np.where(inside_hard & ~in_dist, 1.0, np.nan)
    fig.add_trace(go.Heatmap(
        x=flow, y=o2, z=extrap, zmin=0, zmax=1, colorscale=[[0, EXTRAP_FILL], [1, EXTRAP_FILL]], showscale=False,
        name="Extrapolation", hovertemplate="Far from labelled NASA tests of this material (extrapolation)<extra></extra>",
    ))
    for z, name, dash, width in ((P, "P(burn) = 0.5 boundary", "solid", 3), (HI, "90% band edge (upper P = 0.5)", "dash", 1.5),
                                 (LO, "90% band edge (lower P = 0.5)", "dot", 1.5)):
        fig.add_trace(go.Contour(
            x=flow, y=o2, z=np.where(in_dist, z, np.nan), showscale=False, connectgaps=False,
            contours=dict(start=0.5, end=0.5, size=1, coloring="lines"), colorscale=[[0, "white"], [1, "white"]],
            line=dict(width=width, dash=dash), name=name, showlegend=True, hoverinfo="skip",
        ))

    # Outside this material's tested O2 x flow box: "Out of distribution".
    (o2lo, o2hi), (flo, fhi) = env["o2_percent"], env["flow_velocity_cm_s"]
    x0, x1 = float(flow.min()), float(flow.max())
    for (xa, xb, ya, yb) in ((x0, flo, y0, y1), (fhi, x1, y0, y1), (flo, fhi, o2hi, y1), (flo, fhi, y0, o2lo)):
        if xb > xa and yb > ya:
            fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=OOD_FILL, line_width=0, layer="above")
    if y1 > o2hi:
        fig.add_annotation(x=math.log10(math.sqrt(flo * fhi)), y=min(y1, o2hi + (y1 - o2hi) / 2), xref="x", yref="y",
                           text=f"Out of distribution: no NASA {grid['material']} data", showarrow=False,
                           font=dict(color="#e8e8e8", size=13))

    pts = all_points()
    pts = pts[pts["material_family"] == fam]
    for test_id, g in pts[pts["include_in_training"]].groupby("test_id"):
        if len(g) >= 2 and g["o2_pct"].nunique() == 1:  # the flow ramp of one test
            g = g.sort_values("flow_cm_s")
            fig.add_trace(go.Scatter(x=g["flow_cm_s"], y=g["o2_pct"], mode="lines", line=dict(color="rgba(255,255,255,0.25)", width=1),
                                     hoverinfo="skip", showlegend=False))
    for burn, name, symbol, color in ((1, "NASA test: burn", "circle", "#ff8c1a"), (0, "NASA test: extinguished", "x", "#7fd3ff")):
        g = pts[(pts["burn"] == burn) & pts["include_in_training"]]
        fig.add_trace(go.Scatter(
            x=g["flow_cm_s"], y=g["o2_pct"], mode="markers", name=name,
            marker=dict(symbol=symbol, size=11 if burn else 11, color=color, line=dict(color="white" if burn else color, width=1.5)),
            text=[_hover_point(r) for _, r in g.iterrows()], hovertemplate="%{text}<extra></extra>",
        ))
    ex = pts[~pts["include_in_training"]]
    fig.add_trace(go.Scatter(
        x=ex["flow_cm_s"], y=ex["o2_pct"], mode="markers", name="NASA test: excluded (reused sample, flagged O2…)",
        marker=dict(symbol=["circle-open" if b else "x-open" for b in ex["burn"]], size=10, color="#a0a0a0", line=dict(width=2)),
        text=[_hover_point(r) for _, r in ex.iterrows()], hovertemplate="%{text}<extra></extra>",
    ))

    if marker:
        mx = min(max(marker["flow"], x0), x1)
        fig.add_trace(go.Scatter(
            x=[mx], y=[marker["o2"]], mode="markers", name="Your scenario",
            marker=dict(symbol="star", size=22, color="#ffe14d", line=dict(color="black", width=1.5)),
            hovertemplate=marker.get("hover", "Scenario") + "<extra></extra>",
        ))
        fig.add_annotation(x=math.log10(mx), y=marker["o2"], xref="x", yref="y", text="★", showarrow=False,
                           font=dict(color="#ffe14d", size=30))
        fig.add_annotation(x=math.log10(mx), y=marker["o2"], xref="x", yref="y", text=marker.get("text", ""),
                           showarrow=True, arrowcolor="#ffe14d", ax=0, ay=-34, font=dict(color="#ffe14d", size=13),
                           bgcolor="rgba(0,0,0,0.55)")

    fig.update_layout(
        template="plotly_dark", height=580, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(type="log", title="Forced-flow speed (cm/s, log scale)", range=[math.log10(x0), math.log10(x1)]),
        yaxis=dict(title="O2 (%)", range=[y0, y1]),
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0, font=dict(size=11)),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def scenario_from_controls(preset: str, o2_custom: float, flow: float) -> dict[str, Any]:
    if preset == "Custom":
        return {"name": "Custom", "o2_percent": o2_custom, "pressure_psia": 14.7, "gravity": "micro", "flow": flow}
    key = next(k for k, v in api.MISSION_PRESETS.items() if v["short"] == preset)
    p = api.MISSION_PRESETS[key]
    return {"name": key, "o2_percent": p["o2_percent"], "pressure_psia": p["pressure_psia"], "gravity": p["gravity"],
            "flow": flow, "source": p["source"]}


def material_options(material: str) -> dict[str, Any]:
    """Selectable thickness / size / configuration values for a material (the values present in its points)."""
    fam = api.MATERIALS[material]["family"]
    pts = all_points()
    f = pts[(pts["material_family"] == fam) & pts["include_in_training"]]
    th = sorted(pd.to_numeric(f["thickness_mm"], errors="coerce").dropna().unique().tolist())
    kind = SIZE_KIND[fam]
    sizes = sorted(pd.to_numeric(f[kind], errors="coerce").dropna().unique().tolist(), reverse=True) if kind else []
    cfgs = sorted(f["flow_configuration"].unique().tolist(), key=lambda c: -int((f["flow_configuration"] == c).sum()))
    return {"family": fam, "thickness_mm": th, "size_kind": kind, "sizes": sizes, "configurations": cfgs,
            "defaults": api.get_engine().defaults[fam]}


def render_map_tab(st: Any, grid_loader, predict_fn) -> None:
    """Streamlit UI for the map tab. ``grid_loader(**kw)`` and ``predict_fn(**kw)`` are cached by app.py."""
    left, right = st.columns([3, 1.25], gap="large")
    with right:
        st.markdown("##### Scenario")
        material = st.selectbox("Material (BASS-II)", list(api.MATERIALS), key="map_material",
                                help="Every material family with labelled BASS-II tests (NASA/TM-20210011385 Appendix A).")
        st.caption(MATERIAL_HELP[material])
        opt = material_options(material)
        d = opt["defaults"]
        th = None
        if len(opt["thickness_mm"]) > 1:
            dflt = d["thickness_mm"] if d["thickness_mm"] in opt["thickness_mm"] else opt["thickness_mm"][0]
            th = st.select_slider("Thickness (mm)", options=opt["thickness_mm"], value=dflt, key=f"map_th_{material}")
        size = None
        if len(opt["sizes"]) > 1:
            lab = "Sample width (cm)" if opt["size_kind"] == "width_cm" else "Rod diameter (mm)"
            dflt = d["size"] if d["size"] in opt["sizes"] else opt["sizes"][0]
            size = st.radio(lab, opt["sizes"], index=opt["sizes"].index(dflt), horizontal=True, key=f"map_size_{material}")
        cfg = None
        if len(opt["configurations"]) > 1:
            cfg = st.radio("Flow configuration", opt["configurations"], horizontal=True, key=f"map_cfg_{material}")
        preset = st.radio("Mission preset", ["ISS", "Artemis EA", "Lunar", "Custom"], horizontal=True, key="map_preset",
                          help="ISS 14.7 psia / 21% O2 / µg · Artemis EA 8.2 psia / 34% O2 / µg (C4) · Lunar 8.2 psia / 34% O2 / 1/6 g")
        env = api.get_engine().env[opt["family"]]
        o2_custom = 18.0
        if preset == "Custom":
            o2_custom = st.slider("O2 (%) at 14.7 psia", 13.0, 40.0, 18.0, 0.1, key="map_o2",
                                  help=f"{material} data cover {env['o2_percent'][0]:g}–{env['o2_percent'][1]:g}% O2. Try leaving that range.")
        flow = st.slider("Cabin ventilation (cm/s)", 1.0, 60.0, 20.0, 0.5, key="map_flow", help=FLOW_SLIDER_HELP)
        st.caption("◀ **Fans OFF / near-quiescent** · SIBAL quenched at 1–5 cm/s (C3) · typical circulation ≈ 20–25 cm/s (C8b) ▶")

    sc = scenario_from_controls(preset, o2_custom, flow)
    kw = {"sample_width_cm": size} if opt["size_kind"] == "width_cm" else ({"diameter_mm": size} if opt["size_kind"] else {})
    res = predict_fn(material=material, o2_percent=sc["o2_percent"], pressure_psia=sc["pressure_psia"],
                     flow_velocity_cm_s=sc["flow"], gravity=sc["gravity"], thickness_mm=th, flow_configuration=cfg, **kw)

    with left:
        if res.get("ood_level") == "out_of_envelope":
            st.error(f"**⚠️ Out of distribution: {sc['name']} · {material}.** " + "; ".join(res["ood_reasons"])
                     + ". No prediction is made here: NASA's BASS-II data do not cover these conditions.")
        elif res.get("ood_level") == "extrapolation":
            st.warning(f"**Extrapolation.** Inside {material}'s tested ranges, but far from any of its labelled NASA tests: "
                       "the interval is [0, 1].")
        y_range = (13.0, 36.0) if sc["o2_percent"] > 23 else (13.0, 23.0)
        label = f"{sc['name']}" + (f" ({sc['pressure_psia']:g} psia)" if sc["pressure_psia"] != 14.7 else "")
        hover = (f"{label}<br>O2 {sc['o2_percent']:g}% · flow {sc['flow']:g} cm/s · {sc['pressure_psia']:g} psia · "
                 f"gravity {res['inputs']['gravity']}")
        grid = grid_loader(material=material, thickness_mm=th, flow_configuration=cfg, **kw)
        fig = build_map_figure(grid, {"flow": sc["flow"], "o2": sc["o2_percent"], "text": label, "hover": hover}, y_range)
        st.plotly_chart(fig, use_container_width=True, key="flammability_map")
        sz = grid.get("size")
        geo = (f"thickness {grid['thickness_mm']:g} mm, " if grid.get("thickness_mm") else "") + \
              (f"{'width' if grid['size_kind'] == 'width_cm' else 'diameter'} {sz:g} {'cm' if grid['size_kind'] == 'width_cm' else 'mm'}, " if sz else "")
        st.caption(
            f"{material}: {geo}{grid['flow_configuration']} flow, 14.7 psia (1 atm), microgravity. Colour = P(burn) from the "
            "shipped model; solid line = P(burn) 0.5 boundary; dashed/dotted = 90% band edges from the bootstrap over tests "
            "(missing where the band never reaches 0.5). Darkened = inside the tested ranges but far from labelled tests. "
            "Grey = outside this material's data. Hover any NASA point for its test ID, PI, outcome, quote and page."
        )

    with right:
        st.markdown("##### Readout")
        if res.get("burn_probability") is None:
            st.metric("P(burn)", "no prediction")
        else:
            lo, hi = res["burn_probability_interval"]
            st.metric("P(burn)", f"{res['burn_probability']:.2f}", help="Probability that a flame is sustained (1 atm, µg).")
            st.markdown(f"90% interval **{lo:.2f}–{hi:.2f}** · verdict **{str(res['label']).upper()}**")
        level = {"in_distribution": "🟢 in distribution", "extrapolation": "🟠 extrapolation", "out_of_envelope": "🔴 out of distribution"}
        st.markdown(f"Data coverage: **{level.get(res.get('ood_level'), '?')}**")
        if res.get("ood_reasons"):
            st.markdown("\n".join(f"- {r}" for r in res["ood_reasons"]))
        for n in res.get("notes") or []:
            st.caption(n)
        if res.get("spread_rate_mm_s") is not None:
            slo, shi = res["spread_rate_interval_mm_s"]
            st.markdown(f"Flame spread rate (if it spreads): **{res['spread_rate_mm_s']:.3f} mm/s** (90% {slo:.3f}–{shi:.3f})")
        else:
            st.markdown(f"Flame spread rate: *not predicted* ({res.get('spread_rate_reason') or 'n/a'}).")
        st.markdown("**3 nearest NASA experiments**")
        near = pd.DataFrame(res.get("nearest_experiments") or [])
        if not near.empty:
            st.dataframe(near[["id", "o2_percent", "flow_velocity_cm_s", "outcome", "source_page", "evidence_quote"]]
                         .rename(columns={"id": "test", "o2_percent": "O2 %", "flow_velocity_cm_s": "flow cm/s",
                                          "source_page": "page", "evidence_quote": "quote"}),
                         hide_index=True, use_container_width=True)
        if sc.get("source"):
            st.caption(f"Preset source: {sc['source']}")
