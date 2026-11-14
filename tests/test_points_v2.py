"""Task B: labelled observation points v2. Every rule is tested with real quotes from the report."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_pipeline import derive_points_v2 as dp  # noqa: E402


@pytest.fixture(scope="module")
def pts() -> pd.DataFrame:
    return pd.read_csv(dp.OUT_POINTS)


@pytest.fixture(scope="module")
def by_id(pts) -> pd.DataFrame:
    return pts.set_index("point_id")


# --------------------------------------------------------------------------- #
# Rules, one test per rule, real quotes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,flows", [
    ("Steady burning at 3 and 5 cm/s, did not reach 10 cm/s before end of sample, complete burnout, HCl –>0.3", [3.0, 5.0]),  # B6
    ("Steady burning at 2 cm/s, extinguished at 0.35", [2.0]),                                                              # B9
    ("Initial HCl 0.2 final 0.5, no HCN, flame spread whole sample at 3 cm/s", [3.0]),                                     # T16
    ("Spread at 10 cm/s, did not blowoff", [10.0]),                                                                         # B8
    ("Flame took some time to establish, initially only on bottom of fuel; ignition at 10 cm/s (left 8 min) then flow "
     "down to 8 cm/s (flame out after 3 more minutes)", [10.0]),                                                            # M20
])
def test_stated_burning_at_flow_explicit(text, flows):
    hits = [h for h in dp.stated_burning_hits(text) if h.mode == "quote"]
    assert hits and hits[0].rule == "stated_burning_at_flow" and hits[0].flows == flows
    assert hits[0].quote in text


@pytest.mark.parametrize("text", [
    "Multiple velocities for steady spread, extinguished at pot 0.35",                       # B10, B11, B13
    "Burned with decreasing flows until it went out on its own at 5 cm/s",                   # M19
    "HCl 0.3 > 0.9, steady burn at multiple velocities, finite quench at pot 0.3",           # P10
    "18 min burn; burned entire sample; HCl 2.2 > 3.9",                                     # M7
])
def test_stated_burning_at_multiple_velocities(text):
    hits = [h for h in dp.stated_burning_hits(text) if h.mode == "air_before_extinction"]
    assert hits and hits[0].confidence == "high"


def test_single_flow_burn_phrases():
    assert dp.stated_burning_hits("Burned completely, steady, HCl 0.3 to 0.9")[0].mode == "air_single"  # T11
    assert dp.stated_burning_hits("Steady burn, HCL 0.3 > 0.6")[0].mode == "air_single"                  # T19


@pytest.mark.parametrize("text,flow", [
    ("Prolonged ignition, followed by flow reduction after flame moved away from igniter region and spread steadily; "
     "flame self-extinguished at an air reading of 9 cm/s.", 9.0),                                                  # M14
    ("26-min burn; flow briefly at 15 cm/s but flame was too strong so turned down; HCl 0 > 3.1, extinguished 8 cm/s", 8.0),  # M18
    ("Burned with decreasing flows until it went out on its own at 5 cm/s", 5.0),                                    # M19
    ("Extinguished at 18 cm/s; HCl 0.6 > 2.6", 18.0),                                                                 # M3
    ("29-min burn; extinguished at 12 cm/s., HCl 0.5 > 5.0", 12.0),                                                   # M11
    ("Quick extinction when we turned air down to 3 cm/s, HCl 0.8 end", 3.0),                                         # T20
    ("Ignited at 10 cm/s, photographs every 5 s or so, turned up flow when flame looked weak; died after 15 min at 14 "
     "cm/s; 17-min burn; HCl 0 > 1.7", 14.0),                                                                         # M9
    ("...flame self-extinguished at 8 cm/s after almost 10 min", 8.0),                                                # M10
    ("ignition at 10 cm/s (left 8 min) then flow down to 8 cm/s (flame out after 3 more minutes)", 8.0),             # M20
])
def test_stated_extinction_at_flow(text, flow):
    hits = [h for h in dp.stated_extinction_hits(text) if h.mode == "quote"]
    assert hits and hits[0].flows == [flow] and hits[0].confidence == "high"


def test_blowoff_at_max_uses_the_stated_maximum():
    hit = dp.stated_extinction_hits("Successful blowoff! HCl still 0.8 end")[0]                                      # T21
    assert hit.mode == "air_max"
    assert dp.cms_values(dp.parse_air_display("11, maximum (47)")) == [11.0, 47.0]


@pytest.mark.parametrize("text", [
    "Ignited briefly but did not spread at all and extinguished while the igniter was still on",  # F1
    "Tried to ignite, flame would not sustain",                                                     # F2
    "Brief ignition flash, no sustained flame; no postburn sensor readings taken",                  # F3
    "Brief ignition but flame extinguished before spreading beyond igniter",                         # T9, T10
    "Brief flame at end of first ignition, but no joy on sustained flame",                           # O16
])
def test_no_sustained_ignition(text):
    hits = dp.no_sustained_ignition_hits(text)
    assert hits and hits[0].rule == "no_sustained_ignition" and hits[0].mode == "air_single"


def test_no_ignition_at_any_flow_without_cm_s_gives_no_point(by_id):
    # O12: "No sustained flame at any flow" but the flows are pot settings only -> no point.
    hits = dp.no_sustained_ignition_hits("No sustained flame at any flow, flame with igniter but died immediately upon igniter removal, HCL 12.3")
    assert hits[0].mode == "air_any"
    assert dp.cms_values(dp.parse_air_display("No ignition at any flow")) == []
    assert not any(i.startswith("O12_") for i in by_id.index)


def test_no_blowoff_at_max():
    assert dp.no_blowoff_hits("Tried to blowoff, but did not")[0].rule == "no_blowoff_at_max"                           # T17
    assert dp.no_blowoff_hits("...flow only maxed out to 29 cm/s; no blowoff attained")[0].mode == "air_max"           # T15


def test_no_blowoff_without_a_numeric_maximum_gives_no_max_point(by_id):
    # B8 "Spread at 10 cm/s, did not blowoff" with air "10, maximum": the maximum has no cm/s value.
    assert "B8_b10@21" in by_id.index and by_id.loc["B8_b10@21", "derivation_rule"] == "stated_burning_at_flow"
    assert not [i for i in by_id.index if i.startswith("B8_") and i != "B8_b10@21"]
    # P17 "tried blowoff without success" with air "5, 3, 2, 22, 2, low": 22 cm/s is stated.
    assert by_id.loc["P17_b22@16.8", "derivation_rule"] == "no_blowoff_at_max"


@pytest.mark.parametrize("text", [
    "HCN 0 HCL 0.6; ignited at 10, turned down to 2, then 1, sample very small and dim, but seemed to burn full sample length as a flamelet",  # T5
    "HCL 0.9 at the end, still did not extinguish",  # T6
])
def test_hedged_burning(text):
    hits = dp.hedged_burning_hits(text)
    assert hits and hits[0].confidence == "medium" and hits[0].rule == "hedged_burning"


def test_t6_hedged_points_only_at_stated_cm_s(by_id):
    t6 = by_id[by_id.index.str.startswith("GMT100-T6_")]
    assert sorted(t6["flow_cm_s"]) == [2.6, 4.5]  # Table 7.1 flows; nothing at "<1"
    assert set(t6["label_confidence"]) == {"medium"}


def test_flame_present_before_ramp_is_medium(by_id):
    p = by_id.loc["P1_b5@17.7"]  # "nice flame, got down to extinction at pot 0.315"
    assert p["derivation_rule"] == "flame_present_before_ramp" and p["label_confidence"] == "medium"


def test_table_5_1_spread_rate_points(by_id):
    p = by_id.loc["M7_b3@18.9"]
    assert p["derivation_rule"] == "table_5_1_spread_rate_at_flow" and p["source_page"] == 57 and p["width_cm"] == 1.2


def test_sibal_text_rule_unique_condition_match(by_id):
    for pid, flow in (("GMT96-T7_b10@21", 10.0), ("GMT96-T8_b5@21", 5.0)):
        p = by_id.loc[pid]
        assert p["derivation_rule"] == "text_reports_steady_spread__unique_condition_match"
        assert p["flow_cm_s"] == flow and p["o2_pct"] == 21.0 and p["source_page"] == 95 and p["include_in_training"]
    t71 = dp.parse_table_7_1()
    for flow in (10.0, 5.0):  # exactly one 2.2-cm, 21% test at each flow
        m = t71[(t71["sample_width_cm"] == 2.2) & (t71["o2_vol_percent"] == 21.0) & (t71["flow_start_cm_s"] == flow)]
        assert len(m) == 1


def test_sibal_v1_rules_kept(by_id):
    assert by_id.loc["GMT45-T4_b10@18.7", "derivation_rule"] == "v1_flame_before_ramp"
    assert by_id.loc["GMT45-T4_x2.2@18.7", "burn"] == 0
    assert by_id.loc["GMT190-T21_x47@17.2", "derivation_rule"] == "stated_extinction_at_flow"
    assert by_id.loc["GMT178-T17_b53@16.9", "derivation_rule"] == "no_blowoff_at_max"
    assert by_id.loc["GMT175-T9_x10@16.4", "burn"] == 0


def test_sibal_a6_outcomes_fill_v1_not_reported_rows(by_id):
    assert by_id.loc["GMT178-T11_b4@17.1", "derivation_rule"] == "stated_burning_at_flow"   # "Burned completely, steady"
    assert by_id.loc["GMT190-T19_b11@17.2", "derivation_rule"] == "stated_burning_at_flow"  # "Steady burn"
    assert by_id.loc["GMT100-T16_b3@17.6", "derivation_rule"] == "stated_burning_at_flow"   # "spread whole sample at 3 cm/s"


def test_table_7_1_to_a6_mapping_by_number_and_gmt_day():
    m = dp.match_table71_to_a6(dp.parse_table_7_1(), pd.read_csv(dp.CATALOG_CSV, keep_default_na=False))
    assert m["GMT45-T1"] == "T1" and m["GMT100-T5"] == "T5" and m["GMT175-T9"] == "T9" and m["GMT216-T29"] == "T29"
    assert "GMT96-T7" not in m and "GMT131-T10" not in m  # BASS (2012) rows have no A.6 counterpart
    assert len(m) == 27
    assert dp.gmt_day("6/24/2018") == 175 and dp.gmt_day("2/14/2014 GMT 2014-45") == 45


# --------------------------------------------------------------------------- #
# Exclusions
# --------------------------------------------------------------------------- #
def test_exclusions(by_id, pts):
    ex = pts[~pts["include_in_training"]]
    assert all(ex["exclusion_reason"].fillna("") != "")
    assert not by_id.loc["GMT216-T25_b5@20.8", "include_in_training"]              # reused (Table 7.1)
    assert not by_id.loc["P25_b5@20.9", "include_in_training"]                     # "Reburn of 217m"
    assert not by_id.loc["GMT45-T2_b5@18.5", "include_in_training"]                # NASA footnote b
    assert not any(pts.loc[pts["include_in_training"], "material_family"].isin(["candle_wax", "PMMA_sphere"]))
    assert not any(pts["test_id"].isin(["O1", "O2", "O18", "M12", "B2", "P21b"]))   # unknown config / ambiguous / hardware
    assert by_id.loc["F3_x8@21.7", "include_in_training"]  # flagged FINAL O2 does not affect a point that uses the initial O2


def test_o2_and_flow_valid_for_training(pts):
    tr = pts[pts["include_in_training"]]
    assert tr["o2_pct"].between(10, 30).all() and (tr["flow_cm_s"] > 0).all()


def test_burn_points_use_initial_and_extinction_points_final_o2(pts):
    a = pts[pts["pi_table"].isin(["A.1", "A.2", "A.3", "A.4", "A.5"])]
    assert set(a.loc[a["burn"] == 0, "o2_source"]) <= {"cal_o2_final", "cal_o2_initial"}
    ext = a[a["derivation_rule"] == "stated_extinction_at_flow"]
    assert set(ext["o2_source"]) == {"cal_o2_final"}
    assert set(a.loc[a["burn"] == 1, "o2_source"]) <= {"cal_o2_initial", "Table 5.1 initial O2"}


# --------------------------------------------------------------------------- #
# Traceability
# --------------------------------------------------------------------------- #
def test_every_quote_is_an_exact_substring_of_its_source(pts):
    assert dp.verify_quotes(pts) == []


def test_points_file_is_reproducible(pts):
    import io

    buf = io.StringIO()
    dp.derive().to_csv(buf, index=False)
    buf.seek(0)
    pd.testing.assert_frame_equal(pd.read_csv(buf), pts)


def test_air_display_parser_handles_pots_markers_and_uncertain_values():
    assert dp.cms_values(dp.parse_air_display("5, pots 0.4, 0.36, 0.32, 0.31, 0.30 extinguished")) == [5.0]
    assert dp.cms_values(dp.parse_air_display("3, 5 pot, 0.4 pot")) == [3.0]
    assert dp.cms_values(dp.parse_air_display("10, ~8")) == [10.0]
    assert dp.cms_values(dp.parse_air_display("5, 2.5, 2 (pot 0.9, 0.5, 0.35, 0.33)")) == [5.0, 2.5, 2.0]
    assert dp.cms_values(dp.parse_air_display("49, 44, 42, 41, 41, 40.5 (5, 2, 0)", "O13a")) == [5.0, 2.0, 0.0]
    assert dp.flows_before_extinction(dp.parse_air_display("5, 3, 2, extinction")) == [5.0, 3.0, 2.0]
    assert dp.flows_before_extinction(dp.parse_air_display("10, 17, 14, 10, 8"), extinction_flow=8.0) == [10.0, 17.0, 14.0]


def test_summary_counts(pts):
    tr = pts[pts["include_in_training"]]
    assert len(tr) == 192 and tr["test_id"].nunique() == 85
    assert set(tr["material_family"]) == {"SIBAL_fabric", "PMMA_film", "PMMA_slab", "PMMA_rod", "Nomex"}
    assert (tr["material_family"] == "SIBAL_fabric").sum() == 31
