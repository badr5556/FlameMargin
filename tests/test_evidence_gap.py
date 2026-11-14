"""P1.1: the Evidence Gap view plots all 126 BASS-II tests against the mission atmospheres."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import evidence_gap as eg  # noqa: E402


def test_all_126_tests_with_traceable_pressure_and_o2():
    pts = eg.test_points()
    assert len(pts) == 126 and pts["test_id"].is_unique
    assert pts["o2_percent"].min() == 13.6 and pts["o2_percent"].max() == 22.2
    bh = pts[pts["pi"] == "Bhattacharjee"]
    assert len(bh) == 22 and bh["pressure_basis"].str.contains("99.2–99.5 kPa").all()
    assert abs(bh["pressure_psia"].iloc[0] - 99.35 * 0.1450377) < 1e-9
    assert (pts.loc[pts["pi"] != "Bhattacharjee", "pressure_psia"] == 14.7).all()
    assert (pts.loc[pts["pi"] == "T'ien", "pressure_basis"].str.contains("p. 94")).all()
    assert ((pts["x_plot"] - pts["pressure_psia"]).abs() <= eg.JITTER_PSIA).all()


def test_figure_has_points_presets_and_claim_labelled_references():
    fig = eg.build_evidence_gap_figure()
    names = [t.name or "" for t in fig.data]
    n_points = sum(len(t.x) for t in fig.data if "tests)" in (t.name or ""))
    assert n_points == 126
    assert any("(C5)" in n and "8.2 psia" in n for n in names)
    assert any(n.startswith("Same O2 partial pressure as ISS air") for n in names)
    assert any("Artemis" in n and "(C4)" in n for n in names) and any("Lunar" in n for n in names)
    assert any("convex hull" in n for n in names)
    iso = next(t for t in fig.data if (t.name or "").startswith("Same O2 partial pressure"))
    assert all(abs(x * y - 100 * 14.7 * 0.21) < 1e-6 for x, y in zip(iso.x, iso.y))
    c5 = next(t for t in fig.data if "(C5)" in (t.name or ""))
    assert set(c5.y) == {31.4} and min(c5.x) < 8.2 < max(c5.x)
    hover = next(t for t in fig.data if (t.name or "").startswith("SIBAL fabric")).hovertemplate
    assert "customdata[0]" in hover and "p. %{customdata[3]}" in hover


def test_caption_matches_the_data():
    s = eg.coverage_summary()
    assert s["o2_max"] == 22.2 and "≤22.2% O2" in eg.CAPTION and "(C4, C6)" in eg.CAPTION
    assert s["pressure_psia_min"] > 14.3 and s["pressure_psia_max"] == 14.7
    assert "jitter" in eg.CAPTION_DETAIL


def test_app_has_evidence_gap_as_first_tab(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    assert not at.exception
    assert [t.label for t in at.tabs][:2] == ["🧭 Evidence Gap", "🔥 Flammability Map"]
