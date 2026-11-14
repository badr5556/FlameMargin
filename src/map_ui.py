"""Layer 2: the Flammability Map (Plotly figure + Streamlit tab).

The figure is built by ``build_map_figure`` (pure function, testable without Streamlit);
``render_map_tab`` adds the controls and the live readout card.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import api
from src.features import load_display_points, load_points

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
OTHER_MATERIALS = {
    "Nomex": "no Nomex tests in this NASA extraction",
    "PMMA": "PMMA was tested in BASS-II, but those tests are not in our extraction",
    "Kapton": "no Kapton tests in this NASA extraction",
}


def _hover_point(r: pd.Series) -> str:
    return (f"<b>{r['test_id']}</b> ({r['point_id'].split('_')[-1]})<br>O2 {r['o2_pct']:g}% · flow {r['flow_cm_s']:g} cm/s"
            f" · width {r['sample_width_cm']:g} cm<br>Outcome: {'burn' if r['burn'] == 1 else 'extinguished'}"
            f"<br>{r['derivation_rule']}<br>{r['source']}, {r['source_page']}")


def _hover_display(r: pd.Series) -> str:
    status = "outcome not reported" if r["display_status"] == "outcome_not_reported" else "reused sample"
    comment = f" · comment: {r['reported_comment']}" if r["reported_comment"] else ""
    return (f"<b>{r['test_id']}</b> ({status}{comment})<br>O2 {r['o2_pct']:g}% · flow {r['flow_start_cm_s']:g}→"
            f"{r['flow_end_cm_s']:g} cm/s · width {r['sample_width_cm']:g} cm<br>Not used for training"
            f"<br>{r['source']}, {r['source_page']}")


def build_map_figure(grid: dict[str, Any], marker: dict[str, Any] | None = None, y_max: float = 22.0) -> go.Figure:
    """Heatmap of P(burn) over O2 x flow (log), 0.5 contour, band edges, OOD shading and NASA points."""
    o2 = np.asarray(grid["o2_percent"])
    flow = np.asarray(grid["flow_velocity_cm_s"])
    P = np.asarray(grid["p_burn"])
    LO, HI = np.asarray(grid["p_lo"]), np.asarray(grid["p_hi"])
    in_dist = np.asarray(grid["in_distribution"])
    inside_hard = np.asarray(grid["inside_hard_envelope"])
    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        x=flow, y=o2, z=P, zmin=0, zmax=1, colorscale=P_COLORSCALE, name="P(burn)",
        colorbar=dict(title="P(burn)", thickness=14, len=0.75),
        hovertemplate="flow %{x:.1f} cm/s<br>O2 %{y:.1f}%<br>P(burn) %{z:.2f}<extra></extra>",
    ))
    # Far from labelled tests (inside the hard envelope): darkened overlay.
    extrap = np.where(inside_hard & ~in_dist, 1.0, np.nan)
    fig.add_trace(go.Heatmap(
        x=flow, y=o2, z=extrap, zmin=0, zmax=1, colorscale=[[0, EXTRAP_FILL], [1, EXTRAP_FILL]], showscale=False,
        name="Extrapolation", hovertemplate="Far from labelled NASA tests (extrapolation)<extra></extra>",
    ))
    # 0.5 contour + 90% band edges (contours of the bootstrap band surfaces).
    # Lines are drawn only where the data support them (in-distribution cells).
    for z, name, dash, width in ((P, "P(burn) = 0.5 boundary", "solid", 3), (HI, "90% band edge (upper P = 0.5)", "dash", 1.5),
                                 (LO, "90% band edge (lower P = 0.5)", "dot", 1.5)):
        fig.add_trace(go.Contour(
            x=flow, y=o2, z=np.where(in_dist, z, np.nan), showscale=False, connectgaps=False,
            contours=dict(start=0.5, end=0.5, size=1, coloring="lines"), colorscale=[[0, "white"], [1, "white"]],
            line=dict(width=width, dash=dash), name=name, showlegend=True, hoverinfo="skip",
        ))

    # Outside the hard envelope: "Out of distribution: no NASA data".
    (o2lo, o2hi), (flo, fhi) = api.TRAINING_ENVELOPE["o2_percent"], api.TRAINING_ENVELOPE["flow_velocity_cm_s"]
    x0, x1 = float(flow.min()), float(flow.max())
    for (xa, xb, ya, yb) in ((x0, flo, 15.5, y_max), (fhi, x1, 15.5, y_max), (flo, fhi, o2hi, y_max), (flo, fhi, 15.5, o2lo)):
        if xb > xa and yb > ya:
            fig.add_shape(type="rect", x0=xa, x1=xb, y0=ya, y1=yb, fillcolor=OOD_FILL, line_width=0, layer="above")
    fig.add_annotation(x=math.log10(math.sqrt(flo * fhi)), y=min(y_max, o2hi + (y_max - o2hi) / 2), xref="x", yref="y",
                       text="Out of distribution: no NASA data", showarrow=False, font=dict(color="#e8e8e8", size=13))

    # NASA test points.
    pts = load_points()
    for test_id, g in pts.groupby("test_id"):
        if len(g) == 2:  # the flow ramp of one test
            fig.add_trace(go.Scatter(x=g["flow_cm_s"], y=g["o2_pct"], mode="lines", line=dict(color="rgba(255,255,255,0.35)", width=1),
                                     hoverinfo="skip", showlegend=False))
    for burn, name, symbol, color in ((1, "NASA test: burn", "circle", "#ff8c1a"), (0, "NASA test: extinguished", "x", "#7fd3ff")):
        g = pts[pts["burn"] == burn]
        fig.add_trace(go.Scatter(
            x=g["flow_cm_s"], y=g["o2_pct"], mode="markers", name=name,
            marker=dict(symbol=symbol, size=12 if burn else 11, color=color, line=dict(color="white" if burn else color, width=1.5)),
            text=[_hover_point(r) for _, r in g.iterrows()], hovertemplate="%{text}<extra></extra>",
        ))
    disp = load_display_points()
    fig.add_trace(go.Scatter(
        x=disp["flow_end_cm_s"], y=disp["o2_pct"], mode="markers", name="NASA test: not reported / reused",
        marker=dict(symbol="circle-open", size=10, color="#a0a0a0", line=dict(width=2)),
        text=[_hover_display(r) for _, r in disp.iterrows()], hovertemplate="%{text}<extra></extra>",
    ))

    if marker:
        fig.add_trace(go.Scatter(
            x=[marker["flow"]], y=[marker["o2"]], mode="markers", name="Your scenario",
            marker=dict(symbol="star", size=22, color="#ffe14d", line=dict(color="black", width=1.5)),
            hovertemplate=marker.get("hover", "Scenario") + "<extra></extra>",
        ))
        # Annotations draw above the grey OOD shapes, so the marker stays visible outside the data region.
        fig.add_annotation(x=math.log10(marker["flow"]), y=marker["o2"], xref="x", yref="y", text="★", showarrow=False,
                           font=dict(color="#ffe14d", size=30))
        fig.add_annotation(x=math.log10(marker["flow"]), y=marker["o2"], xref="x", yref="y", text=marker.get("text", ""),
                           showarrow=True, arrowcolor="#ffe14d", ax=0, ay=-34, font=dict(color="#ffe14d", size=13),
                           bgcolor="rgba(0,0,0,0.55)")

    fig.update_layout(
        template="plotly_dark", height=560, margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(type="log", title="Forced-flow speed (cm/s, log scale)", range=[math.log10(x0), math.log10(x1)]),
        yaxis=dict(title="O2 (%)", range=[15.5, y_max]),
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


def render_map_tab(st: Any, grid_loader, predict_fn) -> None:
    """Streamlit UI for the map tab. ``grid_loader(width)`` and ``predict_fn(**kw)`` are cached by app.py."""
    left, right = st.columns([3, 1.25], gap="large")
    with right:
        st.markdown("##### Scenario")
        st.selectbox("Material", ["SIBAL cotton-fiberglass fabric (BASS-II)"], key="map_material",
                     help="The only material in the NASA data used here (NASA/TM-20210011385 Table 7.1).")
        cols = st.columns(len(OTHER_MATERIALS))
        for c, (m, why) in zip(cols, OTHER_MATERIALS.items()):
            c.button(m, disabled=True, help=f"Disabled: {why}. Any prediction would be out of distribution.",
                     key=f"mat_{m}", use_container_width=True)
        st.caption("Other materials are disabled: no NASA data for them in this dataset.")
        preset = st.radio("Mission preset", ["ISS", "Artemis EA", "Lunar", "Custom"], horizontal=True, key="map_preset",
                          help="ISS 14.7 psia / 21% O2 / µg · Artemis EA 8.2 psia / 34% O2 / µg (C4) · Lunar 8.2 psia / 34% O2 / 1/6 g")
        o2_custom = 18.0
        if preset == "Custom":
            o2_custom = st.slider("O2 (%) at 14.7 psia", 15.0, 40.0, 18.0, 0.1, key="map_o2",
                                  help="Data cover 16.4–21.0% (labelled outcomes only up to 18.7%). Try leaving that range.")
        flow = st.slider("Cabin ventilation (cm/s)", 1.0, 60.0, 20.0, 0.5, key="map_flow", help=FLOW_SLIDER_HELP)
        st.caption("◀ **Fans OFF / near-quiescent** · SIBAL quenched at 1–5 cm/s (C3) · typical circulation ≈ 20–25 cm/s (C8b) ▶")
        width = st.radio("Sample width (cm)", [2.2, 1.2], horizontal=True, key="map_width",
                         help="Both widths were tested; 2.2 cm has 15 of the 21 points.")

    sc = scenario_from_controls(preset, o2_custom, flow)
    res = predict_fn(material="SIBAL", o2_percent=sc["o2_percent"], pressure_psia=sc["pressure_psia"],
                     flow_velocity_cm_s=sc["flow"], gravity=sc["gravity"], sample_width_cm=width)

    with left:
        if res.get("ood_level") == "out_of_envelope":
            st.error(f"**⚠️ Out of distribution: {sc['name']}.** " + "; ".join(res["ood_reasons"])
                     + ". No prediction is made here: NASA's microgravity data in this dataset do not cover these conditions.")
        elif res.get("ood_level") == "extrapolation":
            st.warning("**Extrapolation.** Inside the tested ranges, but far from any NASA test with a definitive outcome. "
                       "P(burn) ≈ 0.5 here means *no information*, not 50% risk.")
        y_max = 36.0 if sc["o2_percent"] > 22 else 22.0
        label = f"{sc['name']}" + (f" ({sc['pressure_psia']:g} psia)" if sc["pressure_psia"] != 14.7 else "")
        hover = (f"{label}<br>O2 {sc['o2_percent']:g}% · flow {sc['flow']:g} cm/s · {sc['pressure_psia']:g} psia · "
                 f"gravity {res['inputs']['gravity']}")
        fig = build_map_figure(grid_loader(width), {"flow": sc["flow"], "o2": sc["o2_percent"], "text": label, "hover": hover}, y_max)
        st.plotly_chart(fig, use_container_width=True, key="flammability_map")
        st.caption(
            f"Map at 14.7 psia (1 atm), microgravity, sample width {width:g} cm. Colour = P(burn) from the shipped model; "
            "solid line = P(burn) 0.5 boundary; dashed/dotted = 90% band edges from 300 bootstrap resamples over tests "
            "(missing where the band never reaches 0.5). Darkened = inside the tested ranges but far from labelled tests. "
            "Grey = outside the data. Hover any NASA point for its test ID and source page."
        )

    with right:
        st.markdown("##### Readout")
        if res.get("burn_probability") is None:
            st.metric("P(burn)", "no prediction")
        else:
            lo, hi = res["burn_probability_interval"]
            st.metric("P(burn)", f"{res['burn_probability']:.2f}", help="Probability that a flame is sustained (SIBAL, 1 atm, µg).")
            st.markdown(f"90% interval **{lo:.2f}–{hi:.2f}** · verdict **{str(res['label']).upper()}**")
        level = {"in_distribution": "🟢 in distribution", "extrapolation": "🟠 extrapolation", "out_of_envelope": "🔴 out of distribution"}
        st.markdown(f"Data coverage: **{level.get(res.get('ood_level'), '?')}**")
        if res.get("ood_reasons"):
            st.markdown("\n".join(f"- {r}" for r in res["ood_reasons"]))
        st.markdown("Flame spread rate: *not predicted* (no spread-rate data in the NASA extraction).")
        st.markdown("**3 nearest NASA experiments**")
        near = pd.DataFrame(res.get("nearest_experiments") or [])
        if not near.empty:
            st.dataframe(near[["id", "o2_percent", "flow_velocity_cm_s", "sample_width_cm", "outcome", "source_page", "distance"]]
                         .rename(columns={"id": "test", "o2_percent": "O2 %", "flow_velocity_cm_s": "flow cm/s",
                                          "sample_width_cm": "width cm", "source_page": "source page"}),
                         hide_index=True, use_container_width=True)
        if sc.get("source"):
            st.caption(f"Preset source: {sc['source']}")
