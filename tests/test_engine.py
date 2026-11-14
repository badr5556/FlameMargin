"""Tests for the Prediction Engine v2 (src/api.py, src/model_v2.py): contract, per-material OOD rules, metrics honesty."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import api  # noqa: E402
from src import model_v2  # noqa: E402

CONTRACT_KEYS = {"value", "interval", "ood_flag", "ood_reason", "evidence", "label", "burn_probability",
                 "burn_probability_interval", "unit"}
METRICS = json.loads((ROOT / "models" / "metrics_v2.json").read_text(encoding="utf-8"))
POINTS = pd.read_csv(ROOT / "data" / "processed" / "flame_points_v2.csv")
TEST_IDS = set(POINTS["test_id"])
ISS, ARTEMIS, LUNAR = (api.MISSION_PRESETS[k] for k in ("ISS cabin", "Artemis Exploration Atmosphere", "Lunar surface habitat"))


def _preset_args(p: dict, flow: float = 10.0) -> dict:
    return {"o2_percent": p["o2_percent"], "pressure_psia": p["pressure_psia"], "gravity": p["gravity"], "flow_velocity_cm_s": flow}


# --------------------------------------------------------------------------- #
# Contract shape (unchanged from v1)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("result", [
    lambda: api.predict("SIBAL", 18.0, 14.7, 10.0),
    lambda: api.predict("Kapton", 21.0, 14.7, 10.0),
    lambda: api.predict("PMMA slab", 21.0, 14.7, 10.0),
    lambda: api.flammability_boundary("SIBAL", 14.7, o2_percent=18.0),
    lambda: api.compare_scenarios([{"preset": "ISS cabin", "flow_velocity_cm_s": 10}, {"o2_percent": 17.5, "flow_velocity_cm_s": 10}]),
    lambda: api.nearest_experiments("SIBAL", 18.0, 14.7, 10.0),
])
def test_contract_keys_on_every_output(result):
    r = result()
    assert CONTRACT_KEYS <= set(r), CONTRACT_KEYS - set(r)
    assert isinstance(r["ood_flag"], bool) and isinstance(r["evidence"], list)


def test_predict_returns_probability_interval_and_real_evidence():
    r = api.predict("SIBAL", 18.0, 14.7, 10.0)
    assert r["label"] in ("burn", "extinguish") and r["unit"] == "probability"
    lo, hi = r["burn_probability_interval"]
    assert 0.0 <= lo <= r["burn_probability"] <= hi <= 1.0
    assert r["value"] == r["burn_probability"] and r["interval"] == r["burn_probability_interval"]
    assert r["interval_level"] == 0.9
    assert set(r["evidence"]) <= TEST_IDS and len(r["evidence"]) == 3
    assert r["spread_rate_mm_s"] is None and "PMMA slabs" in r["spread_rate_reason"]


def test_label_matches_probability_with_conservative_tie():
    assert api._label(0.5) == "burn" and api._label(0.499) == "burn" and api._label(0.494) == "extinguish"


@pytest.mark.parametrize("name,expected", [
    ("SIBAL", "SIBAL fabric"), ("sibal fabric", "SIBAL fabric"), ("cotton-fiberglass", "SIBAL fabric"),
    ("PMMA film", "PMMA film"), ("acrylic", "PMMA slab"), ("PMMA", "PMMA slab"), ("acrylic rod", "PMMA rod"),
    ("Nomex III", "Nomex"), ("Nomex", "Nomex"), ("Kapton", None),
])
def test_material_aliases(name, expected):
    assert api.canonical_material(name) == expected


def test_generic_pmma_uses_geometry_when_given():
    assert api.canonical_material("PMMA", thickness_mm=0.2) == "PMMA film"
    assert api.canonical_material("acrylic", diameter_mm=6.35) == "PMMA rod"
    assert api.predict("acrylic", 21.0, 14.7, 10.0)["notes"][0].startswith("generic 'PMMA'")


# --------------------------------------------------------------------------- #
# Presets per material (the key findings)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("material", ["SIBAL fabric", "PMMA film", "PMMA slab", "Nomex"])
def test_iss_is_in_distribution_where_data_exist(material):
    r = api.predict(material, **_preset_args(ISS, 10.0))
    assert r["ood_level"] == "in_distribution" and not r["ood_flag"]
    assert r["burn_probability"] is not None and r["hard_rule_reasons"] == []


def test_iss_sibal_and_slab_burn_nomex_does_not():
    assert api.predict("SIBAL fabric", **_preset_args(ISS, 10.0))["label"] == "burn"
    assert api.predict("PMMA slab", **_preset_args(ISS, 10.0))["label"] == "burn"
    nomex = api.predict("Nomex", **_preset_args(ISS, 10.0))
    assert nomex["label"] == "extinguish" and set(nomex["evidence"]) == {"F1", "F2", "F3"}


def test_iss_rods_are_ood_on_o2():
    r = api.predict("PMMA rod", **_preset_args(ISS, 10.0))
    assert r["ood_level"] == "out_of_envelope" and any("O2 21% outside the tested range for PMMA rod" in x for x in r["ood_reasons"])


@pytest.mark.parametrize("material", list(api.MATERIALS))
def test_artemis_is_ood_with_no_number_for_every_material(material):
    r = api.predict(material, **_preset_args(ARTEMIS))
    assert r["ood_flag"] and r["ood_level"] == "out_of_envelope"
    assert any("pressure 8.2 psia" in x for x in r["ood_reasons"])
    assert any("O2 34%" in x for x in r["ood_reasons"])
    assert r["burn_probability"] is None and r["value"] is None and r["label"] is None


@pytest.mark.parametrize("material", list(api.MATERIALS))
def test_lunar_is_ood_on_gravity_too(material):
    r = api.predict(material, **_preset_args(LUNAR))
    assert r["ood_flag"] and api.GRAVITY_OOD_REASON in r["ood_reasons"] and r["burn_probability"] is None


@pytest.mark.parametrize("g", ["lunar", "mars", "earth", 0.166, 0.38, 1.0])
def test_any_non_microgravity_is_ood(g):
    assert api.GRAVITY_OOD_REASON in api.hard_rule_reasons("SIBAL", 18.0, 14.7, 10.0, g)


@pytest.mark.parametrize("material", ["Kapton", "Delrin", "Teflon"])
def test_other_materials_are_ood(material):
    r = api.predict(material, 21.0, 14.7, 10.0)
    assert r["ood_flag"] and r["burn_probability"] is None and "not in training data" in r["ood_reason"]
    assert r["evidence"] == []


def test_nomex_in_distribution_only_near_its_three_tests():
    assert api.predict("Nomex", 21.0, 14.7, 5.0)["ood_level"] == "out_of_envelope"   # tested flows 8-15 cm/s
    assert api.predict("Nomex", 21.0, 14.7, 20.0)["ood_level"] == "out_of_envelope"
    assert api.predict("Nomex", 18.0, 14.7, 10.0)["ood_level"] == "out_of_envelope"  # tested O2 21.0-22.2%


@pytest.mark.parametrize("kw,needle", [
    ({"pressure_psia": 8.2}, "pressure 8.2 psia"),
    ({"o2_percent": 30.0}, "O2 30%"),
    ({"flow_velocity_cm_s": 80.0}, "flow 80 cm/s"),
    ({"sample_width_cm": 5.0}, "width 5 cm"),
    ({"flow_configuration": "opposed"}, "opposed flow was not tested for SIBAL fabric"),
])
def test_each_hard_rule_triggers_with_its_own_reason(kw, needle):
    args = {"material": "SIBAL", "o2_percent": 18.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 10.0, "gravity": "micro",
            "sample_width_cm": 2.2, **kw}
    reasons = api.hard_rule_reasons(**args)
    assert len(reasons) == 1 and reasons[0].startswith(needle)


def test_pressure_tolerance_is_plus_minus_0_3_psia():
    assert api.hard_rule_reasons("SIBAL", 18.0, 14.4, 10.0) == []
    assert api.hard_rule_reasons("SIBAL", 18.0, 15.0, 10.0) == []
    assert api.hard_rule_reasons("SIBAL", 18.0, 14.3, 10.0)


def test_spread_rate_only_for_pmma_slab_inside_table_5_1():
    r = api.predict("PMMA slab", 21.0, 14.7, 10.0, thickness_mm=3.0)
    lo, hi = r["spread_rate_interval_mm_s"]
    assert lo < r["spread_rate_mm_s"] < hi and r["spread_rate_reason"] is None
    assert api.predict("PMMA slab", 17.0, 14.7, 10.0, thickness_mm=3.0)["spread_rate_mm_s"] is None  # O2 below Table 5.1
    assert api.predict("SIBAL", 18.0, 14.7, 10.0)["spread_rate_mm_s"] is None


# --------------------------------------------------------------------------- #
# Boundary, comparison, nearest experiments
# --------------------------------------------------------------------------- #
def test_boundary_shape_and_grid():
    b = api.flammability_boundary("SIBAL", 14.7, include_grid=True)
    assert len(b["value"]) == len(b["interval"])
    lo_o2, hi_o2 = api.get_engine().env["SIBAL_fabric"]["o2_percent"]
    for p in b["value"]:
        assert p["limit_status"] in ("crossing", "burns_at_all_tested_o2", "no_burn_in_tested_o2")
        assert p["o2_percent_limit"] is None or lo_o2 <= p["o2_percent_limit"] <= hi_o2
    g = b["grid"]
    shape = (len(g["o2_percent"]), len(g["flow_velocity_cm_s"]))
    assert np.array(g["p_burn"]).shape == shape == np.array(g["in_distribution"]).shape
    assert not np.array(g["in_distribution"])[:, 0].any()  # 0.4 cm/s is below every SIBAL test


def test_boundary_at_iss_o2_is_answerable_for_sibal_and_slab():
    for m in ("SIBAL fabric", "PMMA slab"):
        b = api.flammability_boundary(m, 14.7, o2_percent=21.0)
        assert not b["ood_flag"] and b["flows_where_flammable_cm_s"]


def test_compare_scenarios_deltas():
    c = api.compare_scenarios([{"material": "PMMA slab", "o2_percent": 21.0, "flow_velocity_cm_s": 10},
                               {"material": "PMMA slab", "o2_percent": 18.0, "flow_velocity_cm_s": 10}])
    a, b = c["value"]
    assert c["deltas"][0]["burn_probability_delta"] == round(b["burn_probability"] - a["burn_probability"], 2)


def test_nearest_experiments_are_real_nasa_tests_with_quotes():
    rows = api.nearest_experiments("PMMA slab", 18.0, 14.7, 8.0, k=3)["value"]
    assert len(rows) == 3 and len({r["id"] for r in rows}) == 3
    for r in rows:
        assert r["id"] in TEST_IDS and r["outcome"] in ("burn", "extinguish")
        assert r["evidence_quote"] and isinstance(r["source_page"], int) and "NASA/TM-20210011385" in r["source"]
    assert [r["distance"] for r in rows] == sorted(r["distance"] for r in rows)
    sib = api.nearest_experiments("SIBAL", 16.4, 14.7, 10.0, k=1)["value"][0]
    assert sib["id"] == "GMT175-T9" and sib["source_page"] in (96, 112, 113)


# --------------------------------------------------------------------------- #
# Metrics honesty
# --------------------------------------------------------------------------- #
def test_metrics_report_four_models_baseline_and_selection():
    m = METRICS
    assert set(m["models"]) == {"baseline", "logreg", "gpc", "hgb"}
    for r in m["models"].values():
        assert {"accuracy", "balanced_accuracy", "brier", "log_loss", "auc", "n_points"} <= set(r)
    best = min((n for n in m["models"] if n != "baseline"), key=lambda n: m["models"][n]["brier"])
    assert m["chosen_model"] == best and m["models"][best]["brier"] < m["models"]["baseline"]["brier"]
    assert "leave-one-test-out" in m["validation"] and m["bootstrap"]["n_resamples"] >= 200


def test_metrics_match_the_committed_points():
    assert hashlib.sha256((ROOT / "data" / "processed" / "flame_points_v2.csv").read_bytes()).hexdigest() == METRICS["data"]["points_sha256"]
    tr = POINTS[POINTS["include_in_training"]]
    assert METRICS["data"]["n_points"] == len(tr) and METRICS["data"]["n_tests"] == tr["test_id"].nunique()


def test_knn_threshold_is_the_95th_percentile_of_loto_distances():
    d = np.array(METRICS["ood"]["loto_nn_distances"], dtype=float)
    assert METRICS["ood"]["knn_threshold"] == pytest.approx(np.nanpercentile(d, 95), abs=1e-3)


def test_monotonicity_in_o2_is_reported_truthfully():
    e = api.get_engine()
    m = model_v2.monotonicity(e.model, pd.DataFrame(e.art["points"]))
    assert m == METRICS["monotonicity_check"][METRICS["chosen_model"]]


def test_reliability_table_and_per_family_are_reported():
    assert sum(r["n"] for r in METRICS["calibration_oof"]["table"]) == METRICS["data"]["n_points"]
    assert set(METRICS["per_family"]["logreg"]) == set(model_v2.FAMILIES)
    assert set(METRICS["stress_test_leave_one_family_out"]["logreg"]) == set(model_v2.FAMILIES)


def test_v2_vs_v1_on_the_v1_points_is_reported_even_when_worse():
    h = json.loads((ROOT / "models" / "metrics_history.json").read_text(encoding="utf-8"))
    assert h["v2_on_v1_points"]["chosen"]["n_points"] == 21
    assert "brier" in h["v2_on_v1_points"]["chosen"] and "brier" in h["v1"]["chosen"]


def test_mission_presets():
    assert (ISS["pressure_psia"], ISS["o2_percent"], ISS["gravity"]) == (14.7, 21.0, "micro")
    assert (ARTEMIS["pressure_psia"], ARTEMIS["o2_percent"], ARTEMIS["gravity"]) == (8.2, 34.0, "micro")
    assert (LUNAR["pressure_psia"], LUNAR["o2_percent"], LUNAR["gravity"]) == (8.2, 34.0, "lunar")
    for p in api.MISSION_PRESETS.values():
        assert p["source"]


def test_artifact_is_small_and_committed():
    path = ROOT / "models" / "flame_model_v2.joblib"
    assert path.exists() and path.stat().st_size < 5 * 1024 * 1024


def test_runtime_rebuild_gives_the_same_model():
    art = model_v2.runtime_artifact(n_bootstrap=5)
    e = api.get_engine()
    F = e.frame([18.0, 21.0], [10.0, 5.0], "PMMA_slab", "opposed", 3.0, 2.2)
    assert np.allclose(art["final_model"].proba(F), e.model.proba(F), atol=1e-9)
