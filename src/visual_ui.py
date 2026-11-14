"""Presentation layer for the Streamlit app: hero header, styled cards, the result card and a 3D view of the map.

Pure display code. Every number shown here comes from ``api.predict`` / ``api.flammability_boundary`` results passed in by
the caller; nothing is computed or invented here. Out-of-distribution results are always shown as "no prediction".
"""
from __future__ import annotations

import html
import math
from typing import Any

import numpy as np
import plotly.graph_objects as go

INK = "#0F1420"
CARD = "#1A2232"
FIRE = "#F2683C"
SKY = "#5AA9E6"
TEXT = "#EDEAE3"
MUTED = "#A9B3C4"
GREY = "#6B7280"

CSS = f"""
<style>
.block-container {{ padding-top: 1.6rem; }}
div[data-testid="stMetric"] {{
  background: {CARD}; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 14px 16px;
}}
div[data-testid="stMetricValue"] {{ color: {TEXT}; }}
button[data-baseweb="tab"] p {{ font-size: 1.02rem; font-weight: 600; }}
.fm-hero {{
  display: flex; align-items: center; justify-content: space-between; gap: 24px;
  background: radial-gradient(circle at 88% 50%, rgba(242,104,60,0.16), rgba(15,20,32,0) 42%), {INK};
  border: 1px solid rgba(255,255,255,0.06); border-radius: 18px; padding: 22px 28px; margin-bottom: 14px;
}}
.fm-kicker {{ color: {FIRE}; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.22em; margin-bottom: 4px; }}
.fm-title {{ font-size: 2.6rem; font-weight: 800; line-height: 1.05; color: {TEXT}; margin: 0; letter-spacing: -0.02em; }}
.fm-title span {{ color: {FIRE}; }}
.fm-tag {{ color: {MUTED}; font-size: 1.02rem; margin-top: 8px; max-width: 760px; }}
.fm-sphere {{
  flex: 0 0 auto; width: 112px; height: 112px; border-radius: 50%;
  background: radial-gradient(circle, #ffffff 0%, #a9d6f7 30%, {SKY} 62%, rgba(43,108,176,0.15) 100%);
  box-shadow: 0 0 40px 14px rgba(242,104,60,0.28), 0 0 90px 30px rgba(90,169,230,0.12);
  animation: fm-breathe 4s ease-in-out infinite alternate;
}}
@keyframes fm-breathe {{ from {{ transform: scale(0.94); }} to {{ transform: scale(1.04); }} }}
@media (prefers-reduced-motion: reduce) {{ .fm-sphere {{ animation: none; }} }}
.fm-card {{ border-radius: 16px; padding: 18px 20px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.08); }}
.fm-card .lab {{ font-size: 0.78rem; letter-spacing: 0.16em; font-weight: 700; opacity: 0.9; }}
.fm-card .big {{ font-size: 3.1rem; font-weight: 800; line-height: 1.05; margin: 4px 0 2px; }}
.fm-card .verdict {{ font-size: 1.05rem; font-weight: 700; }}
.fm-card .sub {{ color: {MUTED}; font-size: 0.9rem; margin-top: 6px; }}
.fm-bar {{ position: relative; height: 12px; border-radius: 6px; margin: 12px 0 4px;
  background: linear-gradient(90deg, #1f4e79 0%, #8fb8d8 45%, #f4c48a 55%, {FIRE} 80%, #c0392b 100%); }}
.fm-band {{ position: absolute; top: -3px; height: 18px; border: 2px solid {TEXT}; border-radius: 6px;
  background: rgba(255,255,255,0.18); box-sizing: border-box; }}
.fm-dot {{ position: absolute; top: -6px; width: 4px; height: 24px; background: {TEXT}; border-radius: 2px; }}
.fm-scale {{ display: flex; justify-content: space-between; color: {MUTED}; font-size: 0.75rem; }}
.fm-badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.82rem; font-weight: 700; }}
</style>
"""


def hero_html(tagline: str) -> str:
    """The app header: name, tagline and a breathing 'microgravity flame' sphere (decorative illustration)."""
    return (
        '<div class="fm-hero"><div>'
        '<div class="fm-kicker">NASA SPACE APPS 2026 · FLAME IN FREEFALL · TEAM IGNISPHERE</div>'
        '<div class="fm-title">Flame<span>Margin</span></div>'
        f'<div class="fm-tag">{html.escape(tagline)}</div>'
        '</div><div class="fm-sphere" title="Illustration: in microgravity a flame has no up or down, so it is spherical"></div></div>'
    )


_COVERAGE = {
    "in_distribution": ("IN NASA DATA", "#1f7a4d", "#d7f5e6"),
    "extrapolation": ("EXTRAPOLATION", "#8a5a12", "#ffe9c7"),
    "out_of_envelope": ("OUTSIDE NASA DATA", "#7a1f1f", "#ffd9d9"),
}


def _pct(x: float) -> float:
    return max(0.0, min(100.0, 100.0 * float(x)))


def result_card_html(res: dict[str, Any], scenario: str, material: str) -> str:
    """Big verdict card for one ``api.predict`` result. OOD results show no number, by design."""
    level = res.get("ood_level") or "in_distribution"
    badge_txt, badge_bg, badge_fg = _COVERAGE.get(level, _COVERAGE["in_distribution"])
    badge = f'<span class="fm-badge" style="background:{badge_bg};color:{badge_fg};">{badge_txt}</span>'
    where = html.escape(f"{scenario} · {material}")
    p = res.get("burn_probability")
    if p is None:
        return (
            f'<div class="fm-card" style="background:#20242c;">'
            f'<div class="lab" style="color:{MUTED};">RESULT · {where}</div>'
            f'<div class="big" style="color:{GREY};">No prediction</div>'
            f'<div class="verdict" style="color:{TEXT};">NASA\'s microgravity data do not cover this condition.</div>'
            f'<div class="sub">{badge}  The model refuses to guess here; see the reasons below.</div></div>'
        )
    lo, hi = res.get("burn_probability_interval") or (0.0, 1.0)
    burn = str(res.get("label", "")).lower() == "burn"
    color = FIRE if burn else SKY
    verdict = "Flame predicted to SURVIVE" if burn else "Flame predicted to GO OUT"
    bg = "rgba(242,104,60,0.10)" if burn else "rgba(90,169,230,0.10)"
    band_left, band_w = _pct(lo), max(1.5, _pct(hi) - _pct(lo))
    return (
        f'<div class="fm-card" style="background:{bg};border-color:{color}55;">'
        f'<div class="lab" style="color:{color};">P(BURN) · {where}</div>'
        f'<div class="big" style="color:{color};">{float(p):.2f}</div>'
        f'<div class="verdict" style="color:{TEXT};">{verdict}</div>'
        f'<div class="fm-bar"><div class="fm-band" style="left:{band_left:.1f}%;width:{band_w:.1f}%;"></div>'
        f'<div class="fm-dot" style="left:calc({_pct(p):.1f}% - 2px);"></div></div>'
        '<div class="fm-scale"><span>0 · goes out</span><span>0.5</span><span>1 · burns</span></div>'
        f'<div class="sub">{badge}  90% interval {float(lo):.2f}–{float(hi):.2f}</div></div>'
    )


def build_3d_figure(grid: dict[str, Any], points: Any, marker: dict[str, Any] | None = None) -> go.Figure:
    """3D surface of P(burn) over O2 x log10(flow), drawn ONLY inside the material's tested ranges, with NASA tests
    as dots at P = 1 (burned) or 0 (went out). Outside the tested ranges there is no surface: no data, no prediction."""
    o2 = np.asarray(grid["o2_percent"], dtype=float)
    flow = np.asarray(grid["flow_velocity_cm_s"], dtype=float)
    P = np.asarray(grid["p_burn"], dtype=float)
    inside = np.asarray(grid["inside_hard_envelope"], dtype=bool)
    Z = np.where(inside, P, np.nan)
    lx = np.log10(flow)
    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=lx, y=o2, z=Z, cmin=0, cmax=1, opacity=0.92, name="P(burn)",
        colorscale=[[0, "#1f4e79"], [0.45, "#8fb8d8"], [0.5, "#f1e3c8"], [0.55, "#f4c48a"], [0.8, FIRE], [1, "#c0392b"]],
        colorbar=dict(title="P(burn)", thickness=12, len=0.6),
        contours=dict(z=dict(show=True, start=0.5, end=0.5, size=1, color="white", width=4)),
        customdata=np.power(10, np.broadcast_to(lx, Z.shape)),
        hovertemplate="flow %{customdata:.1f} cm/s<br>O2 %{y:.1f}%<br>P(burn) %{z:.2f}<extra></extra>",
    ))
    pts = points[(points["material_family"] == grid["material_family"]) & points["include_in_training"]]
    for burn, name, color in ((1, "NASA test: burned", "#ff8c1a"), (0, "NASA test: went out", "#7fd3ff")):
        g = pts[pts["burn"] == burn]
        fig.add_trace(go.Scatter3d(
            x=np.log10(g["flow_cm_s"].clip(lower=float(flow.min()))), y=g["o2_pct"], z=np.full(len(g), float(burn)),
            mode="markers", name=name, marker=dict(size=4.5, color=color, line=dict(color="white", width=0.5)),
            text=g["test_id"], hovertemplate="%{text}<br>O2 %{y:.1f}%<extra></extra>",
        ))
    if marker and marker.get("p") is not None:
        mx = math.log10(min(max(marker["flow"], float(flow.min())), float(flow.max())))
        fig.add_trace(go.Scatter3d(
            x=[mx, mx], y=[marker["o2"], marker["o2"]], z=[0, marker["p"]], mode="lines+markers", name="Your scenario",
            line=dict(color="#ffe14d", width=6), marker=dict(size=[2, 9], color="#ffe14d"),
            hovertemplate=f"{html.escape(marker.get('text', 'Scenario'))}<br>P(burn) {marker['p']:.2f}<extra></extra>",
        ))
    ticks = [t for t in (1, 2, 5, 10, 20, 50) if flow.min() <= t <= flow.max()]
    fig.update_layout(
        template="plotly_dark", height=560, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=0.02, x=0.02, font=dict(size=11)),
        scene=dict(
            xaxis=dict(title="Flow (cm/s)", tickvals=[math.log10(t) for t in ticks], ticktext=[f"{t:g}" for t in ticks]),
            yaxis=dict(title="O2 (%)"), zaxis=dict(title="P(burn)", range=[0, 1]),
            camera=dict(eye=dict(x=1.55, y=-1.55, z=0.85)), aspectmode="manual", aspectratio=dict(x=1.3, y=1, z=0.6),
        ),
    )
    return fig


BOARD_CSS = f"""
<style>
.fm-board {{ display: grid; grid-template-columns: 190px repeat(5, minmax(0, 1fr)); gap: 10px; margin: 6px 0 8px; }}
.fm-bh {{ color: {MUTED}; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-align: center; padding: 4px 0; }}
.fm-row {{ display: flex; flex-direction: column; justify-content: center; padding: 6px 4px; }}
.fm-row b {{ color: {TEXT}; font-size: 1.0rem; }}
.fm-row span {{ color: {MUTED}; font-size: 0.78rem; }}
.fm-tile {{ border-radius: 14px; padding: 12px 10px; text-align: center; min-height: 92px;
  display: flex; flex-direction: column; justify-content: center; border: 1px solid rgba(255,255,255,0.08); }}
.fm-tile .v {{ font-size: 1.9rem; font-weight: 800; line-height: 1.05; }}
.fm-tile .w {{ font-size: 0.78rem; font-weight: 700; letter-spacing: 0.06em; margin-top: 3px; }}
.fm-tile .r {{ font-size: 0.72rem; color: {MUTED}; margin-top: 4px; line-height: 1.25; }}
.fm-nodata {{ background: repeating-linear-gradient(135deg, #1d212a 0 10px, #23272f 10px 20px); }}
</style>
"""

_MISSION_SUB = {
    "ISS cabin": "14.7 psia · 21% O2 · µg",
    "Artemis Exploration Atmosphere": "8.2 psia · 34% O2 · µg",
    "Lunar surface habitat": "8.2 psia · 34% O2 · 1/6 g",
}


def _short_reason(res: dict[str, Any]) -> str:
    reasons = " ".join(res.get("ood_reasons") or []).lower()
    parts = [w for k, w in (("pressure", "pressure"), ("o2", "O2"), ("gravity", "gravity"), ("flow", "airflow"),
                            ("configuration", "flow type")) if k in reasons]
    return ("untested " + " + ".join(parts)) if parts else "outside NASA data"


def _tile(res: dict[str, Any]) -> str:
    p = res.get("burn_probability")
    if p is None or res.get("ood_level") == "out_of_envelope":
        return (f'<div class="fm-tile fm-nodata"><div class="v" style="color:{GREY};">—</div>'
                f'<div class="w" style="color:#c9ced8;">NO DATA</div><div class="r">{html.escape(_short_reason(res))}</div></div>')
    burn = str(res.get("label", "")).lower() == "burn"
    lo, hi = res.get("burn_probability_interval") or (0.0, 1.0)
    alpha = 0.12 + 0.30 * (float(p) if burn else 1 - float(p))
    color, rgb, word = (FIRE, "242,104,60", "BURNS") if burn else (SKY, "90,169,230", "GOES OUT")
    note = " · extrapolation" if res.get("ood_level") == "extrapolation" else ""
    return (f'<div class="fm-tile" style="background:rgba({rgb},{alpha:.2f});border-color:{color}66;">'
            f'<div class="v" style="color:{TEXT};">{float(p):.2f}</div><div class="w" style="color:{color};">{word}</div>'
            f'<div class="r">90% {float(lo):.2f}–{float(hi):.2f}{note}</div></div>')


def mission_board_html(board: dict[str, dict[str, dict[str, Any]]]) -> str:
    """Grid of mission presets (rows) x materials (columns); each cell is one ``api.predict`` result."""
    materials = list(next(iter(board.values())).keys())
    cells = ['<div></div>'] + [f'<div class="fm-bh">{html.escape(m.upper())}</div>' for m in materials]
    for mission, row in board.items():
        cells.append(f'<div class="fm-row"><b>{html.escape(mission)}</b>'
                     f'<span>{html.escape(_MISSION_SUB.get(mission, ""))}</span></div>')
        cells += [_tile(row[m]) for m in materials]
    return BOARD_CSS + '<div class="fm-board">' + "".join(cells) + "</div>"


def margin_scan(predict_fn, base: dict[str, Any], o2_range: tuple[float, float], step: float = 0.2) -> dict[str, Any]:
    """Walk O2 across the material's tested range at the scenario's other inputs and find where the model's P(burn)
    crosses 0.5 (the predicted extinction line). Uses only ``predict_fn`` results; points outside the data are skipped."""
    lo, hi = float(o2_range[0]), float(o2_range[1])
    grid = [round(x, 3) for x in np.arange(lo, hi + 1e-9, step)]
    if grid[-1] < hi:
        grid.append(hi)
    pts = []
    for o2 in grid:
        r = predict_fn(**{**base, "o2_percent": float(o2)})
        if r.get("burn_probability") is not None and r.get("ood_level") == "in_distribution":
            pts.append((float(o2), float(r["burn_probability"])))
    out: dict[str, Any] = {"lo": lo, "hi": hi, "boundary": None, "status": "no_data"}
    if len(pts) < 2:
        return out
    for (o_a, p_a), (o_b, p_b) in zip(pts, pts[1:]):
        if (p_a - 0.5) * (p_b - 0.5) <= 0 and p_a != p_b:
            out.update(boundary=o_a + (0.5 - p_a) * (o_b - o_a) / (p_b - p_a), status="crossed")
            return out
    out["status"] = "below_range" if pts[0][1] >= 0.5 else "above_range"
    return out


def margin_html(scan: dict[str, Any], o2_now: float) -> str:
    """'The margin': how far the scenario's O2 is from the model's predicted extinction line, on the tested O2 range."""
    lo, hi, b, st = scan["lo"], scan["hi"], scan["boundary"], scan["status"]
    if st == "no_data" or hi <= lo:
        return ""
    pos = lambda x: max(0.0, min(100.0, 100.0 * (x - lo) / (hi - lo)))  # noqa: E731
    now = pos(o2_now)
    if st == "crossed":
        d = o2_now - b
        head = (f"+{d:.1f} O2 points above the extinction line" if d >= 0 else f"{-d:.1f} O2 points below the extinction line")
        sub = (f"Predicted line: P(burn) = 0.5 at {b:.1f}% O2. "
               + ("Lower O2 by this much and the flame is predicted to go out." if d >= 0
                  else "Raise O2 by this much and the flame is predicted to survive."))
        color = FIRE if d >= 0 else SKY
        split = pos(b)
        tick = (f'<div style="position:absolute;left:calc({split:.1f}% - 1px);top:-8px;width:3px;height:30px;'
                f'background:{TEXT};border-radius:2px;"></div>'
                f'<div style="position:absolute;left:calc({split:.1f}% - 30px);top:26px;width:60px;text-align:center;'
                f'font-size:0.7rem;color:{TEXT};">P = 0.5</div>')
    elif st == "below_range":
        split, tick, color = 0.0, "", FIRE
        head = f"≥ {o2_now - lo:.1f} O2 points of margin"
        sub = (f"No extinction line inside NASA's tested range: even at {lo:g}% O2 (the lowest tested) the flame is "
               "predicted to survive. The real line is lower, but we have no data there.")
    else:
        split, tick, color = 100.0, "", SKY
        head = "Predicted to go out across the whole tested O2 range"
        sub = f"Even at {hi:g}% O2 (the highest tested) P(burn) stays below 0.5 at these settings."
    bar = (f'<div style="position:relative;height:14px;border-radius:7px;margin:18px 0 30px;'
           f'background:linear-gradient(90deg,{SKY} 0%,{SKY} {split:.1f}%,{FIRE} {split:.1f}%,{FIRE} 100%);">'
           f'{tick}<div style="position:absolute;left:calc({now:.1f}% - 9px);top:-7px;width:18px;height:28px;'
           f'border-radius:6px;background:#ffe14d;border:2px solid {INK};"></div></div>')
    return (f'<div class="fm-card" style="background:{CARD};">'
            f'<div class="lab" style="color:{color};">THE MARGIN · O2 AT THESE SETTINGS</div>'
            f'<div style="font-size:1.45rem;font-weight:800;color:{TEXT};margin-top:6px;line-height:1.2;">{head}</div>'
            f'{bar}<div class="fm-scale"><span>{lo:g}% O2 · lowest tested</span><span>{hi:g}% · highest tested</span></div>'
            f'<div class="sub">{html.escape(sub)} Yellow = your scenario. Blue = predicted to go out, orange = to burn.</div></div>')
