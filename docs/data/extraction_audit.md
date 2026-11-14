# Extraction audit v2: BASS-II catalog (Appendix A) and labelled points

Source: NASA/TM-20210011385, *Burning and Suppression of Solids–II (BASS–II) Summary Report* (2021).
Page numbers below are **printed** page numbers (printed page = PDF page − 8; Table A.1 is on PDF page 111 = printed p. 103).

Everything here is reproducible from two committed snapshots of the PDF:

| Snapshot | What it is | Made by |
|---|---|---|
| `data/raw/source/appendix_a_cells.json` | one record per Appendix A table row: the raw text of every column cell, located by the table's ruling lines | `python -m src.data_pipeline.extract_appendix_a --pdf-dir DIR` (pdfplumber) |
| `data/raw/source/tm20210011385_pages.json` | whitespace-normalized text of every page, keyed by printed page | same command |

`python -m src.data_pipeline.extract_appendix_a` rebuilds `data/raw/bass2_appendix_a_tests.csv` from the cell snapshot
(the test `test_catalog_is_reproducible_from_the_committed_cell_snapshot` checks that the committed CSV is exactly that output).

## A. Catalog (`data/raw/bass2_appendix_a_tests.csv`)

### A.1 How the tables were read
- The six tables are landscape pages with full ruling lines. pdfplumber finds the cell grid from the lines; columns are
  identified from their header text (rotated headers come out reversed and are matched both ways).
- A table row with a Test number starts a test; following grid rows without a Test number are the wrapped lines of the
  same test. Each column's text is read **once** from the union of that test's cells, by character centre. (A first
  attempt that read each sub-row separately duplicated merged cells, e.g. B1 "PMMA film, PMMA film"; that version was
  discarded.)
- Wrapped lines are joined with one space, except after an ASCII hyphen ("0.2-" + "mm" → "0.2-mm",
  "self-" + "extinguished" → "self-extinguished").
- **Row-by-row comparison.** After parsing, every one of the 126 rows was printed and compared with the rendered page
  image of its table page (PDF pages 111–121). All 126 rows matched. The independent 20% re-check with a different
  extractor is in [`double_check_v2.md`](double_check_v2.md) (26/26 rows pass).

### A.2 Counts
- **126 tests**, as-run numbers 1–126 each exactly once. This matches the report: "A total of 126 tests were conducted as
  part of BASS–II." (p. 3).
- Per table: A.1 Bhattacharjee 22 (matches "Twenty-two test points were obtained with the BASS–II experiments.", p. 13),
  A.2 Ferkul 4, A.3 Fernandez-Pello 27, A.4 Miller 20 (matches Table 5.1, 20 tests), A.5 Olson 24, A.6 T'ien 29.

| Material family | opposed | concurrent | stagnation | unknown ("?") | total |
|---|---|---|---|---|---|
| PMMA_film (A.1, 0.1–0.4 mm) | 22 | | | | 22 |
| PMMA_slab (A.4, 1–5 mm) | 20 | | | | 20 |
| PMMA_rod (A.3, A.5) | 25 | 12 | 12 | 2 | 51 |
| SIBAL_fabric (A.6) | | 27 | | | 27 |
| Nomex (A.2) | | 3 | | | 3 |
| PMMA_sphere (A.6) | | | 2 | | 2 |
| candle_wax (A.2) | | | 1 | | 1 |
| **total** | 67 | 42 | 15 | 2 | **126** |

### A.3 Mapping rules (verbatim text → family, geometry, configuration)
- **Family** from the verbatim material text: "Nomex" → Nomex; "candle"/"wax" → candle_wax; "spherical" → PMMA_sphere
  (p. 5: "cast polymethylmethacrylate (PMMA) samples were shaped as rods of various diameters (6.35 to 12.7 mm), thin to
  thick slabs (0.125 to 5 mm), or a section of a 4-cm-diameter sphere"); "SIBAL" (and A.6 T23 "2 cm SI, moved igniter")
  → SIBAL_fabric; "rod" → PMMA_rod; flat PMMA: "film" → PMMA_film, "slab" → PMMA_slab, otherwise by the written
  thickness (< 1 mm film, ≥ 1 mm slab). This split follows the PIs' own wording: Section 2.1.1 "thin films of plastic
  (PMMA)… Thicknesses were between 0.1 and 0.4 mm" (p. 13) and Section 5 "five thicknesses of PMMA slab (1 to 5 mm)" (p. 58).
  B5 ("200 µm 2 cm wide") does not repeat the word PMMA; it is in the Bhattacharjee PMMA-film table and says "Repeat of B2
  test conditions" (B2 = "200-µm PMMA film, 2 cm wide").
- **pmma_color**: "black"/"clear" when written; blank otherwise (P17 "6.35-mm rod" has no colour).
- **thickness_mm / width_cm / diameter_mm**: only numbers written in the material text; µm converted to mm. A value
  written as "... cm thick" is **not** read as a width (M5 "3-mm-thick PMMA, two-sided, 2 cm thick": width left blank in the
  catalog). Nomex rows state no geometry.
- **flow_configuration** comes from the column headed "Sample distance", which holds Opposed / Concurrent / Stagnation.
  "?" (O1, O2) → `unknown`. The four GMT 45 SIBAL rows (T1, T2, T4, T15) print "1" in that column; their configuration is
  taken from the Table 7.1 title "TEST SUMMARY OF FLAT SIBAL FABRICS IN CONCURRENT FLOW" (p. 96) and the source is written
  in `flow_configuration_source`.

### A.4 O2 convention and sensor sanity
- **Calibrated O2 is used everywhere.** p. 6: "The O2 sensor (CSA-CP) is not recalibrated on orbit, so we also used the
  Major Constituents Analyzer (MCA) (Refs. 6 and 7) data to determine the O2 sensor offset on a daily basis." Table 7.1
  uses the calibrated value: GMT45-T1 is 18.5 in Table 7.1 and 18.5 in A.6's "Calibrated initial O2" (raw sensor 17.3).
  Miller's Table 5.1 initial/final O2 equal A.4's calibrated values for all 20 tests (tested).
- **Flagged, not deleted** (`o2_flag`, outside 10–30 vol%): B2 final 1.6, F3 final 0.9, P22a final 0.6, P22b final 39.1,
  T28a final 0.9, T28b final 40.4. All six are *final* readings; F3's text says "no postburn sensor readings taken".
  A point is excluded only if the O2 value it uses is flagged (F3 and P22a burn points use the valid initial O2).
- NASA's own flag: Table 7.1 footnote b, "O2 reading in these two tests might be inaccurate" (GMT45-T1, GMT45-T2).
  Points from these two tests are excluded from training.

### A.5 Pressure
- p. 94 (Section 7.1.3, T'ien SIBAL tests): "Ambient pressure was 1 atm."
- p. 38 (Section 2.3.5, Bhattacharjee): "The total pressure is also monitored, which varied from 99.2 to 99.5 kPa in the
  tests reported." (99.2–99.5 kPa = 14.39–14.43 psia.)
- Section 1 does not state a measured MSG pressure; it uses "pressure P = 1 atm" inside the O2-consumption calculation
  (p. 11), and the dilution model "assumes the work volume is at constant pressure and temperature" (p. 6).
- Recorded value for all other PIs: **1 atm (ISS cabin/MSG; stated for T'ien tests p. 94) — assumption.** The OOD rule
  keeps 14.7 ± 0.3 psia; note that 99.2 kPa (14.39 psia) sits 0.01 psia below that band's lower edge (14.4 psia).

### A.6 Rows I was unsure about, and why
| Row(s) | Issue | What the catalog does |
|---|---|---|
| T9, T10, T18, F4 | date printed "6/24/2018"; BASS-II ran in 2014 and GMT day 175 = 24 June | kept verbatim; `catalog_notes` says so; Table 7.1 mapping uses the day of year (175) |
| T1, T2, T4, T15 | configuration column prints "1" | concurrent from the Table 7.1 title, source recorded |
| O1, O2 | configuration "?" | `unknown`; excluded from training |
| M5 | "2 cm thick" (a width written as a thickness?) | width blank in the catalog; Table 5.1 gives M5 width 2.2 cm, used for the points |
| A.4 widths | A.4 writes "2 cm"/"1 cm", Table 5.1 writes 2.2 / 1.2 cm for the same tests | catalog keeps A.4's text; points use Table 5.1 (the PI's own summary table) |
| A.6 widths | A.6 writes "2 cm"/"1 cm", Table 7.1 writes 2.2 / 1.2 cm | catalog keeps A.6's text; points use Table 7.1 |
| T24 | A.6 "1 cm SIBAL, top side ign" vs Table 7.1 GMT190-T24 width 2.2 | reused sample, excluded either way |
| O13a, O13b, O5b | the "Air display" cell holds fan readings with cm/s in parentheses ("49, 44, 42, 41, 41, 40.5 (5, 2, 0)") or as "49, 5 cm/s" | cm/s taken from the same cell (`AIR_DISPLAY_CMS_OVERRIDE` in `derive_points_v2.py`) |
| P22b | calibrated initial 20.0 printed in red, raw initial "----" | kept; reused sample, excluded |
| Sample numbers | same sample number reused later (e.g. P25 "Reburn of 217m", first burned in O12) | `sample_reuse_of` names the first test; later uses excluded from training |
| "137" vs "137m" (T13/T26), "138" vs "138m" (T15/T25) | unclear whether the suffix marks a different sample | not merged; T25/T26 are excluded anyway as "Reused" in Table 7.1 |

### A.7 Table 7.1 verification (closes the v1 "PENDING" item)
All 31 rows of the v1 extraction (`data/raw/bass2_sibal_table7_1_extracted.csv`) were compared with the Table 7.1 page
text (p. 96): width, start/end flow, O2 and comment match for **31/31** rows (`test_table_7_1_v1_rows_verified_31_of_31`).

## B. Labelled observation points (`data/processed/flame_points_v2.csv`)

Built by `python -m src.data_pipeline.derive_points_v2` from the catalog, Table 7.1 (p. 96) and Table 5.1 (p. 57).
**215 points from 103 tests; 192 used for training, from 85 tests** (137 high-, 55 medium-confidence). A seeded 20% re-check
of the points against the source text passed 43/43 ([`points_recheck_v2.md`](points_recheck_v2.md)). Every
`evidence_quote` is an exact substring of the test's observation text or of the normalized page text
(`test_every_quote_is_an_exact_substring_of_its_source`).

### B.1 Rules (one name per case; real-quote unit tests in `tests/test_points_v2.py`)
| Rule | burn | Confidence | O2 used | Training points |
|---|---|---|---|---|
| `stated_burning_at_flow` (explicit cm/s, or "multiple velocities / decreasing flows / burned entire sample" → every air-display cm/s before the extinction step, or a single-flow test that "burned completely, steady") | 1 | high | calibrated initial | 60 |
| `table_5_1_spread_rate_at_flow` (Table 5.1 reports a measured spread rate at that velocity) | 1 | high | Table 5.1 initial (= A.4 calibrated initial) | 39 |
| `stated_extinction_at_flow` (cm/s at extinction or blowoff written in the text; T21 "Successful blowoff" at the stated maximum 47) | 0 | high (M15: medium) | calibrated final | 15 |
| `no_sustained_ignition` (single test flow; "at any flow" → one point per stated cm/s; no cm/s → no point) | 0 | high | calibrated initial | 6 |
| `no_blowoff_at_max` (at the maximum **stated** cm/s; "max"/"maximum" without a number → no point) | 1 | high | calibrated initial | 3 |
| `hedged_burning` ("seemed to burn full sample length as a flamelet", "still did not extinguish", "seemed steady") | 1 | medium | calibrated initial | 4 |
| `flame_present_before_ramp` (added rule, see B.2) | 1 | medium | calibrated initial | 49 |
| `text_reports_steady_spread__unique_condition_match` (GMT96-T7, GMT96-T8; p. 95) | 1 | high | Table 7.1 | 2 |
| SIBAL v1 rules: `v1_flame_before_ramp`, `v1_quenched_end`, `v1_no_ignition` | 1 / 0 / 0 | high (GMT175-T18 start: medium) | Table 7.1 | 9 / 4 / 1 |

### B.2 Judgment calls in the labelling
- **Added rule `flame_present_before_ramp` (medium).** Many tests report a flame and then an extinction, quench or
  blowoff at a *pot setting* with no cm/s (e.g. P1 "nice flame, got down to extinction at pot 0.315"). The flame
  existed at every cm/s value listed in the air display before that step. This is the same logic as v1 rule R1/R2
  for SIBAL ("a flame existed before the ramp"), applied with **medium** confidence. If the list ends on a reading that
  the extinction directly followed and no marker separates them (O3a "5, 3": "Flame extinguished as soon as he turned
  flow down"), that last reading is dropped.
- **Added source: Table 5.1** (Miller, p. 57). A measured spread rate at a velocity is the strongest burn evidence in the
  report, so each velocity with a spread rate is a burn point (39). Table 5.1 is the PI's own summary table, like
  Table 7.1 for SIBAL, so the Miller points also take its **width (2.2 / 1.2 cm) and thickness**; A.4 writes "2 cm" /
  "1 cm" and M5's width only as "2 cm thick".
- **Same flow, two outcomes.** M9 (14 cm/s) and M18 (8 cm/s) have a Table 5.1 spread rate *and* an extinction at the same
  flow ("died after 15 min at 14 cm/s", "extinguished 8 cm/s"). Both points are kept: burn=1 at the initial O2
  (18.0 / 17.9) and burn=0 at the final O2 (17.6 / 16.8); the flame burned until the O2 had dropped. A test with both
  outcomes at the same flow *and* O2 would be excluded; none occurs.
- **SIBAL flows and widths come from Table 7.1**, outcomes from A.6. Where A.6 lists other velocities, Table 7.1 wins:
  T11 "Burned completely, steady" is placed at Table 7.1's 4 cm/s (A.6 air display 5); T6's hedged points are at 4.5 and
  2.6 cm/s (A.6 "5, 2, 1, <1"; nothing at "<1"); T5's at 10 and 2.4 (A.6 "10, 2, 1").
- **GMT175-T18 start point is medium**, not high: Table 7.1 says "Quenched" (v1 R1), but A.6 says "Brief ignition but
  flame extinguished as it spread away from igniter, further than previous runs today".
- **GMT100-T16 start (4 cm/s) is medium** (`flame_present_before_ramp`); the 3 cm/s point is high ("flame spread whole
  sample at 3 cm/s").
- **GMT45-T2** ("Flow velocity changed to 9 to 5 fairly early then very late in the burn changed to 4") gives medium burn
  points at 10 and 5, excluded from training by the NASA O2 footnote b.
- **Table 7.1 → A.6 mapping** is by test number *and* GMT day (27 of 27 BASS-II rows map; the four 2012 BASS rows
  GMT96-T7/T8, GMT131-T10, GMT222-T11 are not in A.6 and share numbers with unrelated A.6 tests, so number alone would be wrong).
- **Uncertain cm/s values are not used:** "~8" (M14), "4?" (O13b), "2(?)" (T29), "<1", "approaching 10" (B6), and every pot
  setting. Flow 0 (fan off) is not a point (log scale; a fan-off quench says nothing about a flammability limit).
- **B16** ("3, 5 pot, 0.4 pot") gives one medium burn point at 3 cm/s; 5 and 0.4 are pot settings.
- **Rows whose air-display cell holds fan readings** (O13a, O13b, O5b): cm/s taken from the same cell, see §A.6.

### B.3 Ambiguous or excluded tests (no points)
| Test | Why |
|---|---|
| B14 | "only brief ignition, flame extinguished" but the air display lists "5, 3, 2, extinction" and the final O2 is "-----": which flow failed is not stated |
| B3, B4, B5, B7, B12, T1 | the observation describes the flame or the setup but states no outcome |
| B2, P21b | observations are about hardware only (B2 cable/stills; P21b igniter broke, reused sample) |
| M12 | A.4 air display "<1" (pot plateaus) vs Table 5.1 "12 and 10" (not tracked): the sources disagree |
| O18 | blew out at the high-flow step, restabilized, then failed to restabilize at the low flow it had burned at earlier: contradictory per flow |
| O12 | "No sustained flame at any flow", but the flows are pot settings only → no cm/s, no point |
| O6, O7, O8a, O8b, O9 | air display "See fan" / "------------": no cm/s |
| O1, O2 | flow configuration "?" |
| P8, P3b, O3b, O13b, O15b, P9, P13b, P22b, P25, B21, B22, O5b | later use of an already burned sample (points kept for display only where a rule fired) |
| F4 (candle), T3, T7 (spherical sections) | excluded families |

### B.4 Exclusions of derived points (23 points, kept for display)
reused sample (Table 7.1: GMT190-T23, GMT216-T25…T29): 7 · reused sample (same sample number, incl. "Reburn"): 9 ·
PMMA_sphere: 5 (T3, T7) · NASA O2 footnote b (GMT45-T2): 2. No training point uses a flagged O2 value, an unknown
configuration, or a flow without a cm/s value.

### B.5 Training points per material family × configuration × outcome
| Family | Configuration | burn=0 | burn=1 | Tests | O2 range (%) | Flow range (cm/s) |
|---|---|---|---|---|---|---|
| SIBAL_fabric | concurrent | 10 | 21 | 19 | 16.4–21.0 | 2.2–53 |
| PMMA_slab | opposed | 11 | 70 | 19 | 16.8–22.2 | 1–21 |
| PMMA_rod | opposed / concurrent / stagnation | 1 / 0 / 1 | 28 / 17 / 3 | 31 | 14.5–20.8 | 0.5–22 |
| PMMA_film | opposed | 0 | 27 | 13 | 17.3–22.2 | 1–10 |
| Nomex | concurrent | 3 | 0 | 3 | 21.0–22.2 | 8–15 |

**What this means.** The labels are strongly one-sided outside SIBAL and the slabs: for PMMA films and rods almost every
extinction in Appendix A happened at a pot setting with no cm/s value, so those families have (almost) only burn points.
Nomex has only non-sustained points. A per-family classifier cannot locate a boundary it never sees; the model card
reports this per family instead of hiding it.
