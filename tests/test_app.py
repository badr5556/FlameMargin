"""Smoke tests for the map figure and the app modules (no browser)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from src import api, map_ui  # noqa: E402


def test_map_figure_has_heatmap_contour_points_and_marker():
    fig = map_ui.build_map_figure(api.boundary_grid("SIBAL fabric", 2.2), {"flow": 20.0, "o2": 34.0, "text": "Artemis"},
                                  y_range=(13.0, 36.0))
    names = [t.name for t in fig.data]
    assert "P(burn)" in names and "P(burn) = 0.5 boundary" in names
    assert {"NASA test: burn", "NASA test: extinguished", "Your scenario"} <= set(names)
    assert any((n or "").startswith("NASA test: excluded") for n in names)
    assert fig.layout.xaxis.type == "log"
    burn = next(t for t in fig.data if t.name == "NASA test: burn")
    assert len(burn.x) == 21 and "GMT" in burn.text[0] and "p. " in burn.text[0] and "“" in burn.text[0]
    assert any(a.text == map_ui.OOD_LABEL for a in fig.layout.annotations)


def test_log_axis_has_clean_ticks():
    fig = map_ui.build_map_figure(api.boundary_grid("SIBAL fabric"), None)
    assert list(fig.layout.xaxis.tickvals) == [0.5, 1, 2, 5, 10, 20, 50]
    assert list(fig.layout.xaxis.ticktext) == ["0.5", "1", "2", "5", "10", "20", "50"]


@pytest.mark.parametrize("material", ["SIBAL fabric", "PMMA film", "PMMA slab", "PMMA rod", "Nomex"])
@pytest.mark.parametrize("preset", ["ISS", "Artemis EA", "Lunar"])
def test_grey_label_sits_in_grey_far_below_every_preset_marker(material, preset):
    """The grey-region label must not sit next to a preset star (the old label sat right above the ISS star)."""
    sc = map_ui.scenario_from_controls(preset, 18.0, 20.0)
    y_range = (13.0, 36.0) if sc["o2_percent"] > 23 else (13.0, 23.0)
    grid = api.boundary_grid(material)
    fig = map_ui.build_map_figure(grid, {"flow": sc["flow"], "o2": sc["o2_percent"], "text": sc["name"]}, y_range)
    lab = next(a for a in fig.layout.annotations if a.text == map_ui.OOD_LABEL)
    assert "Out of distribution" not in " ".join(a.text or "" for a in fig.layout.annotations)
    span = y_range[1] - y_range[0]
    label_top = lab.y + 0.035 * span  # 11 px text (~16 px box) on a ~450 px plot area
    assert label_top < grid["envelope"]["o2_percent"][0], "label inside the grey band below the tested O2"
    assert sc["o2_percent"] - label_top > 0.25 * span, "preset star and its label are well above the grey label"
    assert lab.font.size <= 11


@pytest.mark.parametrize("material", ["SIBAL fabric", "PMMA film", "PMMA slab", "PMMA rod", "Nomex"])
def test_map_builds_for_every_material(material):
    opt = map_ui.material_options(material)
    fig = map_ui.build_map_figure(api.boundary_grid(material), None)
    pts = [t for t in fig.data if t.name in ("NASA test: burn", "NASA test: extinguished")]
    assert sum(len(t.x) for t in pts) == api.get_engine().env[opt["family"]]["n_points"]


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


def test_header_metrics_are_readable_and_computed_from_json(monkeypatch):
    import json

    from streamlit.testing.v1 import AppTest

    import app

    m = json.loads((ROOT / "models" / "metrics_v2.json").read_text(encoding="utf-8"))
    best, base = m["models"][m["chosen_model"]], m["models"]["baseline"]
    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    assert not at.exception
    got = {x.label: x.value for x in at.metric}
    assert got["Leave-one-test-out AUC"] == f"{best['auc']:.2f}"
    skill = app.brier_skill(best["brier"], base["brier"])
    assert got["Brier skill vs baseline"] == f"{skill:+.0%}" and abs(skill - (1 - 0.087 / 0.118)) < 1e-9
    assert got["NASA training points"] == str(m["data"]["n_points"]) and got["Artemis EA (8.2 psia / 34%)"] == "OOD"
    assert not any("Brier (LOTO)" in k for k in got)
    assert any(app.AUC_FOOTNOTE in c.value for c in at.caption)
