"""P1.3 / P1.4: safety operating point and reliability table, recomputed from the shipped model's LOTO predictions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src import safety_eval  # noqa: E402

SAVED = json.loads((ROOT / "models" / "safety_operating_point.json").read_text(encoding="utf-8"))


def test_saved_json_matches_a_fresh_computation():
    assert safety_eval.compute() == SAVED


def test_safety_threshold_is_the_largest_meeting_the_target():
    y, p, _ = safety_eval.oof_predictions()
    t = SAVED["safety_threshold"]["threshold"]
    assert safety_eval.at_threshold(y, p, t)["burn_recall"] >= 0.95
    for t2 in np.round(np.arange(t + 0.01, 1.0001, 0.01), 2):
        assert safety_eval.at_threshold(y, p, float(t2))["burn_recall"] < 0.95


def test_counts_are_consistent():
    for r in (SAVED["verdict_threshold"], SAVED["safety_threshold"]):
        assert r["n_burn"] + r["n_extinguished"] == SAVED["n_points"] == 192
        assert abs(r["miss_rate"] - (1 - r["burn_recall"])) < 2e-3
        assert r["missed_burns"] <= r["n_safe_calls"]
    assert SAVED["verdict_threshold"]["threshold"] == 0.5


def test_reliability_matches_the_engine_metrics():
    m = json.loads((ROOT / "models" / "metrics_v2.json").read_text(encoding="utf-8"))
    assert SAVED["model"] == m["chosen_model"]
    assert SAVED["reliability"] == m["calibration_oof"]["table"]
    assert sum(r["n"] for r in SAVED["reliability"]) == 192
    assert (ROOT / "docs" / "img" / "reliability.png").exists()


def test_readout_note_states_the_threshold_from_the_json():
    from src.map_ui import verdict_note

    v = SAVED["verdict_threshold"]
    assert "0.5" in verdict_note() and f"{v['missed_burns']} of {v['n_burn']}" in verdict_note()
