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
