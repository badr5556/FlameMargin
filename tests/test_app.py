"""Smoke tests for the map figure and the app modules (no browser)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import api, map_ui  # noqa: E402


def test_map_figure_has_heatmap_contour_points_and_marker():
    fig = map_ui.build_map_figure(api.boundary_grid(2.2), {"flow": 20.0, "o2": 34.0, "text": "Artemis"}, y_max=36.0)
    names = [t.name for t in fig.data]
    assert "P(burn)" in names and "P(burn) = 0.5 boundary" in names
    assert {"NASA test: burn", "NASA test: extinguished", "NASA test: not reported / reused", "Your scenario"} <= set(names)
    assert fig.layout.xaxis.type == "log"
    burn = next(t for t in fig.data if t.name == "NASA test: burn")
    assert len(burn.x) == 11 and "GMT" in burn.text[0] and "Table 7.1" in burn.text[0]
    assert any("Out of distribution" in (a.text or "") for a in fig.layout.annotations)


def test_presets_resolve_for_the_map():
    sc = map_ui.scenario_from_controls("Artemis EA", 18.0, 20.0)
    assert (sc["o2_percent"], sc["pressure_psia"]) == (34.0, 8.2)
    assert map_ui.scenario_from_controls("Custom", 17.5, 4.0)["o2_percent"] == 17.5


def test_no_fans_off_number_is_defined():
    """The ventilation slider must not invent a single fans-off flow value."""
    from src import copilot_tools

    assert copilot_tools._scan_repo_for_fans_off() is None


def test_app_and_entry_point_import():
    import app  # noqa: F401
    import src.copilot_ui  # noqa: F401

    src_text = (ROOT / "src" / "copilot_ui.py").read_text(encoding="utf-8")
    assert "st.set_page_config(" not in src_text
    assert (ROOT / "app.py").read_text(encoding="utf-8").count("st.set_page_config(") == 1
