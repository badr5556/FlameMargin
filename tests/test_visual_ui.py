"""The presentation layer must never show a number where the model refuses to predict."""
import numpy as np

from src import api, visual_ui
from src.map_ui import all_points


def test_ood_card_shows_no_number():
    res = api.predict(material="SIBAL fabric", o2_percent=34.0, pressure_psia=8.2, flow_velocity_cm_s=20.0)
    assert res["burn_probability"] is None
    card = visual_ui.result_card_html(res, "Artemis EA", "SIBAL fabric")
    assert "No prediction" in card and "OUTSIDE NASA DATA" in card and "P(BURN)" not in card


def test_in_data_card_shows_model_numbers():
    res = api.predict(material="SIBAL fabric", o2_percent=17.5, pressure_psia=14.7, flow_velocity_cm_s=4.0)
    lo, hi = res["burn_probability_interval"]
    card = visual_ui.result_card_html(res, "Custom", "SIBAL fabric")
    assert f"{res['burn_probability']:.2f}" in card and f"{lo:.2f}–{hi:.2f}" in card


def test_3d_surface_is_empty_outside_tested_ranges():
    grid = api.boundary_grid("SIBAL fabric")
    fig = visual_ui.build_3d_figure(grid, all_points())
    z = np.asarray(fig.data[0].z, dtype=float)
    inside = np.asarray(grid["inside_hard_envelope"], dtype=bool)
    assert np.isnan(z[~inside]).all() and not np.isnan(z[inside]).any()


def test_mission_board_only_shows_numbers_inside_the_data():
    board = {m: {mat: api.predict(material=mat, o2_percent=p["o2_percent"], pressure_psia=p["pressure_psia"],
                                  gravity=p["gravity"], flow_velocity_cm_s=10.0) for mat in api.MATERIALS}
             for m, p in api.MISSION_PRESETS.items()}
    out = visual_ui.mission_board_html(board)
    n_ood = sum(r["burn_probability"] is None for row in board.values() for r in row.values())
    assert out.count("NO DATA") == n_ood
    for mission in ("Artemis Exploration Atmosphere", "Lunar surface habitat"):
        assert all(r["burn_probability"] is None for r in board[mission].values())
    iss = board["ISS cabin"]["SIBAL fabric"]
    assert f"{iss['burn_probability']:.2f}" in out


def test_margin_matches_the_model_and_stays_in_the_data():
    base = dict(material="SIBAL fabric", pressure_psia=14.7, flow_velocity_cm_s=3.0, gravity="micro")
    env = api.get_engine().env["SIBAL_fabric"]["o2_percent"]
    scan = visual_ui.margin_scan(api.predict, base, tuple(env))
    assert env[0] <= scan["lo"] and scan["hi"] <= env[1]
    if scan["status"] == "crossed":
        b = scan["boundary"]
        below = api.predict(**{**base, "o2_percent": max(env[0], b - 0.3)})["burn_probability"]
        above = api.predict(**{**base, "o2_percent": min(env[1], b + 0.3)})["burn_probability"]
        assert below <= 0.5 <= above
    assert "THE MARGIN" in visual_ui.margin_html(scan, 19.0)
