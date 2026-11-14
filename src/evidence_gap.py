"""The Evidence Gap view: where NASA's BASS-II tests sit in pressure x O2, and where the mission atmospheres are.

    python -m src.evidence_gap      # writes docs/img/evidence_gap.png (needs kaleido; not in requirements.txt)

Every point is one of the 126 tests of NASA/TM-20210011385 Appendix A (``data/raw/bass2_appendix_a_tests.csv``):
y = calibrated initial O2 (the report's MCA-based daily offset), x = total pressure. Pressure is not tabulated per test:
for the Bhattacharjee tests the report gives the measured range 99.2-99.5 kPa (p. 38), plotted at its midpoint; the T'ien
tests ran at 1 atm (p. 94); for the other PIs 1 atm (14.7 psia) is assumed. Each hover says which applies.

Reference marks carry claim IDs only (docs/science/claims_sheet.md): C4 (Exploration Atmosphere 8.2 psia / 34% O2),
C5 (31.4% O2 = upper limit with no burning-rate increase at 8.2 psia), C6 (NESC), C10 (no long-duration lunar-gravity
fire experiment yet). The iso-ppO2 curve through ISS air is arithmetic: 14.7 psia x 21% = 3.087 psia of O2.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "raw" / "bass2_appendix_a_tests.csv"
PNG_OUT = ROOT / "docs" / "img" / "evidence_gap.png"

KPA_TO_PSIA = 0.1450377
ATM_PSIA = 14.7
BHATTACHARJEE_KPA = (99.2, 99.5)  # "The total pressure is also monitored, which varied from 99.2 to 99.5 kPa" (p. 38)
ISS = {"pressure_psia": 14.7, "o2_percent": 21.0}
EA = {"pressure_psia": 8.2, "o2_percent": 34.0}
C5_O2 = 31.4  # claim C5
ISS_PPO2_PSIA = ISS["pressure_psia"] * ISS["o2_percent"] / 100.0  # 3.087 psia, derived
X_RANGE, Y_RANGE = (4.0, 16.0), (10.0, 40.0)
JITTER_PSIA = 0.12  # visual only; stated in the caption

CAPTION = ("Every BASS-II test ran at ~1 atm and ≤22.2% O2 (TM-20210011385). "
           "The Artemis Exploration Atmosphere is outside all of them (C4, C6).")
CAPTION_DETAIL = (f"Points: all 126 BASS-II tests (Appendix A), calibrated initial O2. Pressure: 99.2–99.5 kPa measured for "
                  "the Bhattacharjee tests (p. 38, plotted at the midpoint), 1 atm stated for the T'ien tests (p. 94), "
                  f"1 atm assumed for the other PIs. A small random x jitter (±{JITTER_PSIA:g} psia) separates overlapping "
                  "points; hover shows the real values. The shaded area is the convex hull of the tests (widened by the jitter). The iso-ppO2 curve "
                  "is derived arithmetic (14.7 psia × 21%), not a NASA limit.")

# Categorical slots 1, 2, 3, 5, 6, 7 of the dark reference palette (yellow and red are left to the preset markers),
# each with its own symbol so identity never rests on colour alone.
FAMILY_STYLE = {
    "SIBAL_fabric": ("SIBAL fabric", "#3987e5", "circle"),
    "PMMA_film": ("PMMA film", "#d95926", "square"),
    "PMMA_slab": ("PMMA slab", "#199e70", "diamond"),
    "PMMA_rod": ("PMMA rod", "#d55181", "triangle-up"),
    "Nomex": ("Nomex", "#0ca30c", "x"),
    "other": ("Other (PMMA spheres, candle)", "#9085e9", "cross"),
}


def _pressure(pi: str) -> tuple[float, str]:
    if pi == "Bhattacharjee":
        lo, hi = BHATTACHARJEE_KPA
        mid = (lo + hi) / 2 * KPA_TO_PSIA
        return mid, (f"{lo:g}–{hi:g} kPa ({lo * KPA_TO_PSIA:.2f}–{hi * KPA_TO_PSIA:.2f} psia) measured for these tests "
                     "(p. 38); plotted at the midpoint")
    if pi == "T'ien":
        return ATM_PSIA, "1 atm (14.7 psia), stated in the report (p. 94)"
    return ATM_PSIA, "1 atm (14.7 psia) assumed: not tabulated for this PI's tests"


@lru_cache(maxsize=1)
def test_points() -> pd.DataFrame:
    """One row per BASS-II test: pressure (psia, with its basis), calibrated initial O2, material, page."""
    df = pd.read_csv(CATALOG, dtype={"test_id": "string"})
    p = df["pi"].map(_pressure)
    out = pd.DataFrame({
        "test_id": df["test_id"].astype(str), "pi": df["pi"], "material": df["material_raw"],
        "family": df["material_family"].where(df["material_family"].isin(list(FAMILY_STYLE)), "other"),
        "o2_percent": df["cal_o2_initial"].astype(float), "pressure_psia": p.map(lambda t: t[0]),
        "pressure_basis": p.map(lambda t: t[1]), "source_page": df["source_page"].astype(int),
    })
    rng = np.random.default_rng(7)
    out["x_plot"] = out["pressure_psia"] + rng.uniform(-JITTER_PSIA, JITTER_PSIA, len(out))
    return out


def _hull(x: np.ndarray, y: np.ndarray) -> tuple[list[float], list[float]]:
    """Convex hull (monotone chain), closed polygon."""
    pts = sorted(set(zip(x.round(4).tolist(), y.round(4).tolist())))
    if len(pts) < 3:
        return [p[0] for p in pts], [p[1] for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    ring = lower[:-1] + upper[:-1] + [lower[0]]
    return [p[0] for p in ring], [p[1] for p in ring]


def build_evidence_gap_figure(height: int = 560) -> go.Figure:
    pts = test_points()
    fig = go.Figure()

    # Hull of the tests' real (pressure, O2), widened by the jitter so it encloses every plotted marker.
    hx, hy = _hull(np.concatenate([pts["pressure_psia"] - JITTER_PSIA, pts["pressure_psia"] + JITTER_PSIA]),
                   np.concatenate([pts["o2_percent"], pts["o2_percent"]]))
    fig.add_trace(go.Scatter(x=hx, y=hy, fill="toself", mode="lines", line=dict(color="rgba(255,255,255,0.55)", width=1),
                             fillcolor="rgba(255,255,255,0.10)", name="Region covered by NASA BASS-II tests (convex hull)",
                             hoverinfo="skip"))

    p = np.linspace(ISS_PPO2_PSIA * 100 / Y_RANGE[1], X_RANGE[1], 120)
    fig.add_trace(go.Scatter(x=p, y=100 * ISS_PPO2_PSIA / p, mode="lines", line=dict(color="#c3c2b7", width=2, dash="dot"),
                             name="Same O2 partial pressure as ISS air (derived: 14.7 psia × 21%)",
                             hovertemplate="%{x:.1f} psia · %{y:.1f}% O2: same O2 partial pressure as ISS air<extra></extra>"))
    fig.add_trace(go.Scatter(x=[EA["pressure_psia"] - 1.3, EA["pressure_psia"] + 1.3], y=[C5_O2, C5_O2], mode="lines",
                             line=dict(color="#e66767", width=3),
                             name="Max O2 with no burning-rate increase at 8.2 psia (C5)",
                             hovertemplate="Max O2 with no burning-rate increase at 8.2 psia (C5)<extra></extra>"))

    for fam, (label, color, symbol) in FAMILY_STYLE.items():
        g = pts[pts["family"] == fam]
        if g.empty:
            continue
        fig.add_trace(go.Scatter(
            x=g["x_plot"], y=g["o2_percent"], mode="markers", name=f"{label} ({len(g)} tests)",
            marker=dict(symbol=symbol, size=8, color=color, line=dict(color="#0e1117", width=1)),
            customdata=g[["test_id", "material", "pi", "source_page", "pressure_basis"]].to_numpy(),
            hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}<br>PI %{customdata[2]} · "
                           "O2 %{y:g}% (calibrated initial)<br>Pressure: %{customdata[4]}"
                           "<br>NASA/TM-20210011385 Appendix A, p. %{customdata[3]}<extra></extra>"),
        ))

    fig.add_trace(go.Scatter(x=[ISS["pressure_psia"]], y=[ISS["o2_percent"]], mode="markers", name="ISS cabin (team brief, C12 pending)",
                             marker=dict(symbol="star", size=20, color="#ffe14d", line=dict(color="black", width=1.5)),
                             hovertemplate="ISS cabin: 14.7 psia, 21% O2, microgravity (team brief; C12 pending)<extra></extra>"))
    fig.add_trace(go.Scatter(x=[EA["pressure_psia"]], y=[EA["o2_percent"]], mode="markers", name="Artemis Exploration Atmosphere (C4)",
                             marker=dict(symbol="star", size=20, color="#ffe14d", line=dict(color="black", width=1.5)),
                             hovertemplate="Artemis Exploration Atmosphere: 8.2 psia, 34% O2 (C4)<extra></extra>"))
    fig.add_trace(go.Scatter(x=[EA["pressure_psia"]], y=[EA["o2_percent"]], mode="markers",
                             name="Lunar habitat (C4 at 1/6 g, C10)",
                             marker=dict(symbol="circle-open", size=34, color="#ffe14d", line=dict(width=2)),
                             hovertemplate="Lunar surface habitat: 8.2 psia, 34% O2 at 1/6 g: also outside the µg data (C10)<extra></extra>"))

    ann = dict(showarrow=True, arrowcolor="#ffe14d", font=dict(color="#ffe14d", size=13), bgcolor="rgba(0,0,0,0.6)")
    fig.add_annotation(x=ISS["pressure_psia"], y=ISS["o2_percent"], text="ISS cabin", ax=-60, ay=-40, **ann)
    fig.add_annotation(x=EA["pressure_psia"], y=EA["o2_percent"], text="Artemis EA", ax=70, ay=-34, **ann)
    fig.add_annotation(x=EA["pressure_psia"] - 0.35, y=EA["o2_percent"] + 0.9, text="Lunar habitat · 1/6 g: also outside µg data",
                       ax=-40, ay=-56, **ann)
    fig.add_annotation(x=EA["pressure_psia"] - 1.3, y=C5_O2, text="max O2, no burning-rate increase (C5)", showarrow=False,
                       xanchor="left", yanchor="top", yshift=-4, font=dict(color="#e66767", size=12))
    fig.add_annotation(x=14.55, y=12.4, text="every NASA test", showarrow=False, font=dict(color="#f0efec", size=12),
                       xanchor="center")

    fig.update_layout(
        template="plotly_dark", height=height, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Total pressure (psia)", range=list(X_RANGE), dtick=2, zeroline=False),
        yaxis=dict(title="O2 (vol %)", range=list(Y_RANGE), dtick=5, zeroline=False),
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0, font=dict(size=11)),
        hoverlabel=dict(align="left"),
    )
    return fig


def coverage_summary() -> dict[str, Any]:
    pts = test_points()
    return {"n_tests": int(len(pts)), "o2_min": float(pts["o2_percent"].min()), "o2_max": float(pts["o2_percent"].max()),
            "pressure_psia_min": float(pts["pressure_psia"].min()), "pressure_psia_max": float(pts["pressure_psia"].max())}


def render_evidence_tab(st: Any) -> None:
    s = coverage_summary()
    st.markdown("#### Where NASA's microgravity fire data are, and where the next missions will fly")
    st.plotly_chart(build_evidence_gap_figure(), use_container_width=True, key="evidence_gap")
    st.markdown(f"**{CAPTION}**")
    st.caption(CAPTION_DETAIL)
    c1, c2, c3 = st.columns(3)
    c1.metric("BASS-II tests plotted", f"{s['n_tests']}", help="All Appendix A tests (Tables A.1–A.6), as-run 1–126.")
    c2.metric("Highest calibrated O2 in any test", f"{s['o2_max']:g}%", help="Calibrated initial O2, Appendix A.")
    c3.metric("Artemis EA (8.2 psia / 34% O2)", "outside all tests", help="Claim C4 (atmosphere), C6 (NESC: flammability is "
              "the most critical hurdle there).")
    st.caption("That is why FlameMargin refuses to give a number for the Exploration Atmosphere: no NASA test is near it. "
               "The Flammability Map tab shows P(burn) inside the tested region, per material.")


def export_png(path: Path = PNG_OUT) -> Path:
    fig = build_evidence_gap_figure(height=640)
    fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", margin=dict(l=20, r=20, t=90, b=20),
                      title=dict(text="The evidence gap: NASA BASS-II tests vs the Artemis Exploration Atmosphere", x=0.01,
                                 font=dict(size=18)))
    fig.add_annotation(text=CAPTION, xref="paper", yref="paper", x=0, y=1.03, xanchor="left", yanchor="bottom",
                       showarrow=False, font=dict(size=12, color="#c3c2b7"))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(path), width=1200, height=760, scale=2)
    return path


if __name__ == "__main__":
    print(export_png().relative_to(ROOT))
