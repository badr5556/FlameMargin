"""Tests for the Prediction Engine (src/api.py, src/model.py): contract, OOD rules, metrics honesty."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import api  # noqa: E402
from src.features import feature_frame  # noqa: E402

CONTRACT_KEYS = {"value", "interval", "ood_flag", "ood_reason", "evidence", "label", "burn_probability",
                 "burn_probability_interval", "unit"}
METRICS = json.loads((ROOT / "models" / "metrics.json").read_text(encoding="utf-8"))
RAW_IDS = set(pd.read_csv(ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv")["test_id"])
ISS, ARTEMIS, LUNAR = (api.MISSION_PRESETS[k] for k in ("ISS cabin", "Artemis Exploration Atmosphere", "Lunar surface habitat"))


def _preset_args(p: dict, flow: float = 20.0) -> dict:
    return {"o2_percent": p["o2_percent"], "pressure_psia": p["pressure_psia"], "gravity": p["gravity"], "flow_velocity_cm_s": flow}


# --------------------------------------------------------------------------- #
# Contract shape
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("result", [
    lambda: api.predict("SIBAL", 18.0, 14.7, 10.0),
    lambda: api.predict("Kapton", 21.0, 14.7, 10.0),
    lambda: api.flammability_boundary("SIBAL", 14.7, o2_percent=18.0),
    lambda: api.compare_scenarios([{"preset": "ISS cabin", "flow_velocity_cm_s": 10}, {"o2_percent": 17.5, "flow_velocity_cm_s": 10}]),
    lambda: api.nearest_experiments("SIBAL", 18.0, 14.7, 10.0),
])
def test_contract_keys_on_every_output(result):
    r = result()
    assert CONTRACT_KEYS <= set(r), CONTRACT_KEYS - set(r)
    assert isinstance(r["ood_flag"], bool)
    assert isinstance(r["evidence"], list)
    json.dumps(r)  # JSON-serializable


def test_predict_returns_probability_interval_and_no_spread_rate():
    r = api.predict("SIBAL", 18.0, 14.7, 10.0)
    assert r["label"] in ("burn", "extinguish") and r["unit"] == "probability"
    lo, hi = r["burn_probability_interval"]
    assert 0.0 <= lo <= r["burn_probability"] <= hi <= 1.0
    assert r["value"] == r["burn_probability"] and r["interval"] == r["burn_probability_interval"]
    assert r["interval_level"] == 0.9
    assert r["spread_rate_mm_s"] is None
    assert r["spread_rate_reason"] == "no spread-rate measurements in the current NASA extraction"
    assert set(r["evidence"]) <= RAW_IDS and len(r["evidence"]) == 3


def test_label_matches_probability_with_conservative_tie():
    assert api._label(0.5) == "burn" and api._label(0.499) == "burn" and api._label(0.494) == "extinguish"


def test_boundary_shape_and_grid():
    b = api.flammability_boundary("SIBAL", 14.7, include_grid=True)
    assert len(b["value"]) == len(api.DEFAULT_FLOWS) == len(b["interval"])
    for p in b["value"]:
        assert p["limit_status"] in ("crossing", "burns_at_all_tested_o2", "no_burn_in_tested_o2")
        assert p["o2_percent_limit"] is None or 16.4 <= p["o2_percent_limit"] <= 21.0
    g = b["grid"]
    shape = (len(g["o2_percent"]), len(g["flow_velocity_cm_s"]))
    assert np.array(g["p_burn"]).shape == shape == np.array(g["in_distribution"]).shape
    assert g["o2_percent"][0] == 16.0 and g["o2_percent"][-1] == 21.0
    assert abs(g["flow_velocity_cm_s"][0] - 1.0) < 1e-6 and abs(g["flow_velocity_cm_s"][-1] - 60.0) < 1e-3
    assert not np.array(g["in_distribution"])[:, 0].any()  # 1 cm/s is below the tested 2.0 cm/s


def test_compare_scenarios_deltas():
    c = api.compare_scenarios([{"label": "A", "o2_percent": 17.5, "flow_velocity_cm_s": 10},
                               {"label": "B", "o2_percent": 18.5, "flow_velocity_cm_s": 10}])
    a, b = c["value"]
    assert c["deltas"][0]["burn_probability_delta"] == round(b["burn_probability"] - a["burn_probability"], 2)


def test_nearest_experiments_are_real_nasa_tests():
    n = api.nearest_experiments("SIBAL", 17.0, 14.7, 2.8, k=3)
    rows = n["value"]
    assert len(rows) == 3 and len({r["id"] for r in rows}) == 3
    for r in rows:
        assert r["id"] in RAW_IDS and r["outcome"] in ("burn", "extinguish")
        assert "Table 7.1" in r["source"] and r["source_page"]
    assert rows[0]["id"] == "GMT178-T14"  # quenched at 16.9% O2, 2.8 cm/s
    assert [r["distance"] for r in rows] == sorted(r["distance"] for r in rows)


# --------------------------------------------------------------------------- #
# OOD rules
# --------------------------------------------------------------------------- #
def test_iss_is_inside_the_hard_rule_envelope():
    assert api.hard_rule_reasons("SIBAL", ISS["o2_percent"], ISS["pressure_psia"], 20.0, ISS["gravity"]) == []


def test_iss_21pct_is_flagged_as_extrapolation_by_knn():
    # Honest finding: no test at 21% O2 has a definitive outcome in the extraction (highest labelled O2: 18.7%).
    r = api.predict("SIBAL", **_preset_args(ISS))
    assert r["ood_flag"] and r["ood_level"] == "extrapolation" and r["hard_rule_reasons"] == []
    assert r["knn_distance"] > r["knn_threshold"]
    assert r["burn_probability_interval"] == [0.0, 1.0]


def test_in_distribution_point_is_not_flagged():
    r = api.predict("SIBAL", 17.5, 14.7, 4.0)
    assert not r["ood_flag"] and r["ood_level"] == "in_distribution" and r["ood_reason"] is None


def test_artemis_is_ood_with_no_number():
    r = api.predict("SIBAL", **_preset_args(ARTEMIS))
    assert r["ood_flag"] and r["ood_level"] == "out_of_envelope"
    assert any("pressure 8.2 psia" in x for x in r["ood_reasons"])
    assert any("O2 34%" in x for x in r["ood_reasons"])
    assert r["burn_probability"] is None and r["value"] is None and r["label"] is None


def test_lunar_is_ood_on_gravity_too():
    r = api.predict("SIBAL", **_preset_args(LUNAR))
    assert r["ood_flag"] and api.GRAVITY_OOD_REASON in r["ood_reasons"]
    assert r["burn_probability"] is None


@pytest.mark.parametrize("g", ["lunar", "mars", "earth", 1.0, 0.38, "1/6 g"])
def test_any_non_microgravity_is_ood(g):
    assert api.GRAVITY_OOD_REASON in api.hard_rule_reasons("SIBAL", 18.0, 14.7, 10.0, g)


@pytest.mark.parametrize("material", ["Kapton", "Nomex", "PMMA", "Delrin"])
def test_other_materials_are_ood(material):
    r = api.predict(material, 18.0, 14.7, 10.0)
    assert r["ood_flag"] and r["burn_probability"] is None
    assert "not in training data" in r["ood_reason"]


@pytest.mark.parametrize("name", ["SIBAL", "sibal fabric", "SIBAL cotton-fiberglass fabric", "cotton-fiberglass"])
def test_sibal_aliases(name):
    assert api.canonical_material(name) == "SIBAL"


@pytest.mark.parametrize("kw,needle", [
    ({"pressure_psia": 14.0}, "pressure"), ({"pressure_psia": 15.1}, "pressure"),
    ({"o2_percent": 16.3}, "O2"), ({"o2_percent": 21.1}, "O2"),
    ({"flow_velocity_cm_s": 1.9}, "flow"), ({"flow_velocity_cm_s": 54}, "flow"),
    ({"sample_width_cm": 3.0}, "sample width"),
])
def test_each_hard_rule_triggers_with_its_own_reason(kw, needle):
    args = {"material": "SIBAL", "o2_percent": 18.0, "pressure_psia": 14.7, "flow_velocity_cm_s": 10.0, "gravity": "micro",
            "sample_width_cm": 2.2, **kw}
    reasons = api.hard_rule_reasons(**args)
    assert len(reasons) == 1 and reasons[0].startswith(needle)


def test_pressure_tolerance_is_plus_minus_0_3_psia():
    assert api.hard_rule_reasons("SIBAL", 18.0, 14.4, 10.0) == []
    assert api.hard_rule_reasons("SIBAL", 18.0, 15.0, 10.0) == []


def test_knn_threshold_is_the_95th_percentile_of_loto_distances():
    d = METRICS["ood"]["loto_nn_distances"]
    assert METRICS["ood"]["knn_threshold"] == pytest.approx(np.percentile(d, 95), abs=1e-3)


# --------------------------------------------------------------------------- #
# Metrics honesty + sanity
# --------------------------------------------------------------------------- #
def test_metrics_report_baseline_and_loto():
    m = METRICS
    assert m["data"]["n_points"] == 21 and m["data"]["n_tests"] == 12
    assert m["data"]["class_balance"] == {"burn": 11, "extinguished": 10}
    assert "leave-one-test-out" in m["validation"]
    for name in ("baseline", "logreg", "gpc"):
        assert {"accuracy", "balanced_accuracy", "brier", "log_loss", "n_points"} <= set(m["models"][name])
    eligible = [n for n, r in m["models"].items() if r["eligible"] and n != "baseline"]
    best = min(eligible, key=lambda n: m["models"][n]["brier"])
    if m["chosen_beats_baseline"]:
        assert m["chosen_model"] == best and m["models"][best]["brier"] < m["models"]["baseline"]["brier"]
    else:
        assert m["chosen_model"] == "logreg"
    assert m["bootstrap"]["n_resamples"] >= 200


def test_data_hash_in_metrics_matches_committed_points():
    import hashlib

    assert hashlib.sha256((ROOT / "data" / "processed" / "flame_points.csv").read_bytes()).hexdigest() == METRICS["data"]["points_sha256"]


def test_monotonicity_in_o2_is_reported_truthfully():
    """Higher O2 should not lower P(burn) at a fixed mid-range flow. The chosen model may violate this
    (a GP reverts to 0.5 far from data); the test checks that metrics.json reports it honestly."""
    e = api.get_engine()
    o2 = np.round(np.arange(16.4, 21.0 + 1e-9, 0.1), 2)
    p = e.proba(feature_frame(o2, 10.0, 2.2))
    violated = bool((np.diff(p) < -1e-3).any())
    assert METRICS["monotonicity_check"]["chosen"]["violated"] == violated
    assert METRICS["monotonicity_check"]["logreg"]["violated"] is False


def test_model_reproduces_the_clear_data_patterns():
    e = api.get_engine()
    F = feature_frame([16.4, 16.4, 18.7], [10.0, 5.0, 10.0], 2.2)
    p = e.proba(F)
    assert p[0] < 0.5 and p[1] < 0.5  # no ignition at 16.4% O2 (GMT175-T9, -T10)
    assert p[2] >= 0.5  # flame present at 18.7%, 10 cm/s (GMT45-T4, -T15)


def test_mission_presets():
    assert (ISS["pressure_psia"], ISS["o2_percent"], ISS["gravity"]) == (14.7, 21.0, "micro")
    assert (ARTEMIS["pressure_psia"], ARTEMIS["o2_percent"], ARTEMIS["gravity"]) == (8.2, 34.0, "micro")
    assert (LUNAR["pressure_psia"], LUNAR["o2_percent"], LUNAR["gravity"]) == (8.2, 34.0, "lunar")
    for p in api.MISSION_PRESETS.values():
        assert p["source"]


def test_artifact_is_small_and_committed():
    path = ROOT / "models" / "flame_model.joblib"
    assert path.exists() and path.stat().st_size < 5 * 1024 * 1024
