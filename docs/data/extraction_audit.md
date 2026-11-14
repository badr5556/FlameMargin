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
