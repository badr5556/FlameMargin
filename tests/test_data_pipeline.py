"""Tests for the data package integration and the written derivation rules."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_pipeline import derive_points as dp  # noqa: E402

RAW = ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv"


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(RAW, dtype={"test_id": "string"})


@pytest.fixture(scope="module")
def derived(raw):
    return dp.derive(raw)


def test_raw_extraction_shape_and_scope(raw):
    assert len(raw) == 31 and raw["test_id"].is_unique
    assert set(raw["material"]) == {"SIBAL cotton-fiberglass fabric"}
    assert set(raw["pressure_atm"]) == {1.0}
    assert set(raw["gravity_environment"]) == {"ISS microgravity"}
    assert raw["o2_vol_percent"].between(16.4, 21.0).all()
    counts = raw["conservative_event_label"].value_counts().to_dict()
    assert counts["quenched"] == 6 and counts["no_ignition"] == 3 and counts["blowoff"] == 1
    assert int(raw["reused_sample"].sum()) == 8


def test_point_counts_and_balance(derived):
    pts, disp = derived
    assert len(pts) == 21
    assert pts["test_id"].nunique() == 12
    assert int(pts["burn"].sum()) == 11 and int((pts["burn"] == 0).sum()) == 10
    assert len(disp) == 19
    assert disp["display_status"].value_counts().to_dict() == {"outcome_not_reported": 11, "reused_sample": 8}
    assert list(pts.columns) == dp.POINT_COLUMNS


def test_every_point_has_a_written_rule_and_source(derived):
    pts, _ = derived
    assert pts["derivation_rule"].isin(dp.RULES.values()).all()
    assert pts["source"].str.contains("NASA/TM-20210011385").all()
    assert pts["source_page"].notna().all()


def test_quenched_rule(derived, raw):
    pts, _ = derived
    row = raw.set_index("test_id").loc["GMT45-T4"]
    p = pts[pts["test_id"] == "GMT45-T4"].set_index("point_id")
    assert p.loc["GMT45-T4_start", "burn"] == 1 and p.loc["GMT45-T4_start", "flow_cm_s"] == row["flow_start_cm_s"]
    assert p.loc["GMT45-T4_end", "burn"] == 0 and p.loc["GMT45-T4_end", "flow_cm_s"] == row["flow_end_cm_s"]
    assert (p["o2_pct"] == row["o2_vol_percent"]).all()


def test_blowoff_rule(derived):
    pts, _ = derived
    p = pts[pts["test_id"] == "GMT190-T21"].set_index("point_id")
    assert (p.loc["GMT190-T21_start", "flow_cm_s"], p.loc["GMT190-T21_start", "burn"]) == (11.0, 1)
    assert (p.loc["GMT190-T21_end", "flow_cm_s"], p.loc["GMT190-T21_end", "burn"]) == (47.0, 0)


def test_no_blowoff_rule_needs_increased_flow(derived, raw):
    pts, _ = derived
    for tid in ("GMT45-T15", "GMT178-T17"):
        p = pts[pts["test_id"] == tid]
        assert len(p) == 2 and (p["burn"] == 1).all()
    # A "No blowoff" comment with a decreasing flow must NOT produce points.
    fake = raw[raw["test_id"] == "GMT45-T15"].copy()
    fake["flow_end_cm_s"] = 5.0
    pts2, disp2 = dp.derive(fake)
    assert pts2.empty and disp2["display_status"].tolist() == ["outcome_not_reported"]


def test_no_ignition_rule(derived):
    pts, _ = derived
    p = pts[pts["derivation_rule"] == dp.RULES["R4"]]
    assert sorted(p["test_id"]) == ["GMT175-T10", "GMT175-T9", "GMT178-T12"]
    assert (p["burn"] == 0).all()
    assert "conservative proxy" in p["derivation_rule"].iloc[0]


def test_reused_and_not_reported_rows_never_train(derived, raw):
    pts, disp = derived
    reused = set(raw.loc[raw["reused_sample"], "test_id"])
    assert not reused & set(pts["test_id"])
    assert reused <= set(disp["test_id"])
    assert not set(disp["test_id"]) & set(pts["test_id"])


def test_committed_points_match_the_script(derived):
    pts, disp = derived
    committed = pd.read_csv(ROOT / "data" / "processed" / "flame_points.csv")
    pd.testing.assert_frame_equal(committed, pts.reset_index(drop=True), check_dtype=False)
    committed_disp = pd.read_csv(ROOT / "data" / "processed" / "display_only_points.csv", keep_default_na=False)
    assert committed_disp["test_id"].tolist() == disp["test_id"].tolist()


def test_regression_dataset_keeps_empty_schema():
    reg = pd.read_csv(ROOT / "data" / "ml_ready" / "regression_dataset.csv")
    assert reg.empty and "flame_spread_rate_mm_s" in reg.columns
