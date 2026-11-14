"""The frozen v1 engine (SIBAL only, 21 points) kept for the v1 -> v2 before/after table: metrics honesty checks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.features import feature_frame  # noqa: E402
from src.model import load_artifact  # noqa: E402

METRICS = json.loads((ROOT / "models" / "metrics.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def v1():
    return load_artifact()


def test_knn_threshold_is_the_95th_percentile_of_loto_distances():
    d = METRICS["ood"]["loto_nn_distances"]
    assert METRICS["ood"]["knn_threshold"] == pytest.approx(np.percentile(d, 95), abs=1e-3)


def test_metrics_report_baseline_and_loto():
    m = METRICS
    assert m["data"]["n_points"] == 21 and m["data"]["n_tests"] == 12
    assert m["data"]["class_balance"] == {"burn": 11, "extinguished": 10}
    assert "leave-one-test-out" in m["validation"]
    eligible = [n for n, r in m["models"].items() if r["eligible"] and n != "baseline"]
    best = min(eligible, key=lambda n: m["models"][n]["brier"])
    assert m["chosen_model"] == best and m["models"][best]["brier"] < m["models"]["baseline"]["brier"]
    assert m["bootstrap"]["n_resamples"] >= 200


def test_data_hash_in_metrics_matches_committed_points():
    assert hashlib.sha256((ROOT / "data" / "processed" / "flame_points.csv").read_bytes()).hexdigest() == METRICS["data"]["points_sha256"]


def test_monotonicity_in_o2_is_reported_truthfully(v1):
    o2 = np.round(np.arange(16.4, 21.0 + 1e-9, 0.1), 2)
    p = v1["final_model"].predict_proba(feature_frame(o2, 10.0, 2.2)[v1["features"]])[:, 1]
    assert METRICS["monotonicity_check"]["chosen"]["violated"] == bool((np.diff(p) < -1e-3).any())


def test_v1_reproduces_the_clear_data_patterns(v1):
    p = v1["final_model"].predict_proba(feature_frame([16.4, 16.4, 18.7], [10.0, 5.0, 10.0], 2.2)[v1["features"]])[:, 1]
    assert p[0] < 0.5 and p[1] < 0.5 and p[2] >= 0.5


def test_history_file_compares_v1_and_v2():
    h = json.loads((ROOT / "models" / "metrics_history.json").read_text(encoding="utf-8"))
    assert h["v1"]["n_points"] == 21 and h["v1"]["chosen"]["brier"] == METRICS["models"][METRICS["chosen_model"]]["brier"]
    assert h["v2"]["n_points"] > h["v1"]["n_points"]
