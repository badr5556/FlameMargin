"""Task A: the Appendix A catalog (126 BASS-II tests) and the report text tables it is checked against."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_pipeline import extract_appendix_a as ea  # noqa: E402
from src.data_pipeline.report_tables import page_text, parse_table_5_1, parse_table_7_1  # noqa: E402


@pytest.fixture(scope="module")
def cat() -> pd.DataFrame:
    return pd.read_csv(ea.CATALOG_CSV, keep_default_na=False)


@pytest.fixture(scope="module")
def by_id() -> pd.DataFrame:
    """All columns as the strings written in the CSV (blank = not stated)."""
    return pd.read_csv(ea.CATALOG_CSV, dtype=str, keep_default_na=False).set_index("test_id")


def test_catalog_is_reproducible_from_the_committed_cell_snapshot(cat):
    cells = json.loads(ea.CELLS_JSON.read_text(encoding="utf-8"))
    rebuilt = ea.build_catalog(cells)
    rebuilt.to_csv(ROOT / "data" / "raw" / ".rebuilt_check.csv", index=False)
    try:
        again = pd.read_csv(ROOT / "data" / "raw" / ".rebuilt_check.csv", keep_default_na=False)
    finally:
        (ROOT / "data" / "raw" / ".rebuilt_check.csv").unlink()
    pd.testing.assert_frame_equal(again, cat)


def test_126_tests_matches_the_report_total(cat):
    # p. 3: "A total of 126 tests were conducted as part of BASS–II."
    assert "A total of 126 tests were conducted as part of BASS–II." in page_text(3)
    assert len(cat) == 126 and cat["test_id"].is_unique
    assert sorted(cat["as_run_number"]) == list(range(1, 127))  # as-run numbers are global and complete
    assert cat.groupby("pi_table").size().to_dict() == {"A.1": 22, "A.2": 4, "A.3": 27, "A.4": 20, "A.5": 24, "A.6": 29}


def test_bhattacharjee_count_matches_section_2(cat):
    # p. 13: "Twenty-two test points were obtained with the BASS–II experiments."
    assert "Twenty-two test points were obtained with the BASS–II experiments." in page_text(13)
    assert (cat["pi_table"] == "A.1").sum() == 22


@pytest.mark.parametrize("tid,field,value", [
    ("B6", "air_display_raw", "3, 5, approaching 10"),
    ("B6", "observations_raw", "Steady burning at 3 and 5 cm/s, did not reach 10 cm/s before end of sample, complete burnout, HCl –>0.3"),
    ("F1", "observations_raw", "Ignited briefly but did not spread at all and extinguished while the igniter was still on"),
    ("F2", "cal_o2_initial_raw", "21"),
    ("F3", "cal_o2_initial_raw", "21.7"),
    ("M14", "observations_raw", "Prolonged ignition, followed by flow reduction after flame moved away from igniter region and spread steadily; flame self-extinguished at an air reading of 9 cm/s."),
    ("M2", "observations_raw", "Ignite at 20 cm/s, turn down to 15 cm/s after spread away from igniter; seemed steady, so turned down to 13 cm/s; flame got very dim, so increased flow to 14 cm/s, but it self-extinguished"),
    ("O13a", "air_display_raw", "49, 44, 42, 41, 41, 40.5 (5, 2, 0)"),
    ("T21", "air_display_raw", "11, maximum (47)"),
    ("T1", "cal_o2_initial_raw", "18.5"),
    ("P17", "material_raw", "6.35-mm rod"),
])
def test_spot_values(by_id, tid, field, value):
    assert by_id.loc[tid, field] == value


def test_o2_flags_are_flagged_not_deleted(by_id):
    flagged = {t: by_id.loc[t, "cal_o2_final_raw"] for t in by_id.index if by_id.loc[t, "o2_flag"]}
    assert flagged == {"B2": "1.6", "F3": "0.9", "P22a": "0.6", "P22b": "39.1", "T28a": "0.9", "T28b": "40.4"}


def test_calibrated_o2_convention_matches_table_7_1(by_id):
    # GMT45-T1 is 18.5 in Table 7.1 and in Table A.6's calibrated initial O2 (raw sensor value 17.3).
    t71 = parse_table_7_1().set_index("test_id")
    assert t71.loc["GMT45-T1", "o2_vol_percent"] == 18.5
    assert float(by_id.loc["T1", "cal_o2_initial"]) == 18.5 and by_id.loc["T1", "o2_initial_raw"] == "17.3"


def test_material_families_and_configurations(cat):
    fam = cat.groupby("material_family").size().to_dict()
    assert fam == {"Nomex": 3, "PMMA_film": 22, "PMMA_rod": 51, "PMMA_slab": 20, "PMMA_sphere": 2,
                   "SIBAL_fabric": 27, "candle_wax": 1}
    assert set(cat["flow_configuration"]) == {"opposed", "concurrent", "stagnation", "unknown"}
    assert set(cat.loc[cat["flow_configuration"] == "unknown", "test_id"]) == {"O1", "O2"}  # printed "?"


def test_geometry_numbers_only_when_written(by_id):
    assert by_id.loc["B13", "thickness_mm"] == "0.4" and by_id.loc["B13", "width_cm"] == "2.0"
    assert by_id.loc["B14", "thickness_mm"] == "0.2" and by_id.loc["B14", "width_cm"] == "1.0"
    assert by_id.loc["P12", "diameter_mm"] == "9.525"
    assert by_id.loc["M5", "width_cm"] == ""  # "2 cm thick" is not read as a width
    assert by_id.loc["F1", "thickness_mm"] == "" and by_id.loc["F1", "width_cm"] == ""


def test_sample_reuse_detection(by_id):
    assert by_id.loc["P25", "sample_reuse_of"] == "O12"  # "Reburn of 217m", first burned in O12
    assert by_id.loc["P8", "sample_reuse_of"] == "P4"
    assert by_id.loc["B21", "sample_reuse_of"] == "B14"
    assert by_id.loc["P4", "sample_reuse_of"] == ""


def test_cell_line_joining():
    assert ea.join_cell_lines("1-cm, 0.2-\nmm PMMA\nfilm") == "1-cm, 0.2-mm PMMA film"
    assert ea.join_cell_lines("but it self-\nextinguished") == "but it self-extinguished"
    assert ea.join_cell_lines("–41, –42, –\n30") == "–41, –42, – 30"


def test_table_7_1_v1_rows_verified_31_of_31():
    """The 31 v1 rows (data/raw/bass2_sibal_table7_1_extracted.csv) match the Table 7.1 page text."""
    t71 = parse_table_7_1().set_index("test_id")
    old = pd.read_csv(ROOT / "data" / "raw" / "bass2_sibal_table7_1_extracted.csv").set_index("test_id")
    assert len(t71) == len(old) == 31
    for tid, r in old.iterrows():
        n = t71.loc[tid]
        assert (r["sample_width_cm"], r["flow_start_cm_s"], r["flow_end_cm_s"], r["o2_vol_percent"]) == \
               (n["sample_width_cm"], n["flow_start_cm_s"], n["flow_end_cm_s"], n["o2_vol_percent"]), tid
        assert ("" if pd.isna(r["reported_comment"]) else r["reported_comment"]) == n["comment"], tid
        assert n["row_text"] in page_text(96)


def test_table_5_1_matches_appendix_a4_calibrated_o2(by_id):
    t51 = parse_table_5_1()
    assert len(t51) == 20 and sum(len(v) for v in t51["spread_rates_mm_s"]) == 39
    for _, r in t51.iterrows():
        a4 = by_id.loc[r["test_id"]]
        assert float(a4["cal_o2_initial"]) == r["o2_initial"], r["test_id"]
        assert float(a4["cal_o2_final"]) == r["o2_final"], r["test_id"]


def test_pressure_statements_are_in_the_text():
    assert "Ambient pressure was 1 atm." in page_text(94)
    assert "The total pressure is also monitored, which varied from 99.2 to 99.5 kPa in the tests reported." in page_text(38)
