# Data dictionary v2

Source for every value: NASA/TM-20210011385 (BASS-II Summary Report, 2021). Page numbers are printed page numbers.
No value is read off a figure. v1 files (`bass2_sibal_table7_1_extracted.csv`, `flame_points.csv`) are kept unchanged
for the before/after comparison; their dictionary is [`data_dictionary.md`](data_dictionary.md).

**O2 convention.** All O2 values are the **calibrated** O2 (vol%). The O2 sensor "is not recalibrated on orbit, so we also
used the Major Constituents Analyzer (MCA) (Refs. 6 and 7) data to determine the O2 sensor offset on a daily basis" (p. 6).
Table 7.1 uses the calibrated value (GMT45-T1: 18.5 in Table 7.1 and in A.6's calibrated initial O2; raw sensor 17.3).
Raw sensor readings are kept verbatim in `o2_initial_raw` / `o2_final_raw` and are not used.

**Flow convention.** Flow values are the cm/s readings of the duct's airspeed transducer ("Air display", Appendix A) or the
cm/s columns of Table 7.1 / Table 5.1. Fan-display and potentiometer ("pot") settings are not converted to cm/s: a point
whose flow is only a pot setting has no flow value and is not created.

**Pressure.** 1 atm. Stated for the T'ien SIBAL tests ("Ambient pressure was 1 atm.", p. 94) and measured as 99.2–99.5 kPa
for the Bhattacharjee tests (p. 38); for the other PIs it is an assumption (ISS cabin / MSG). Gravity: ISS microgravity.

## `data/raw/bass2_appendix_a_tests.csv` (126 rows, one per BASS-II test)

| Column | Meaning |
|---|---|
| `pi_table` | A.1–A.6 |
| `pi` | Bhattacharjee, Ferkul, Fernandez-Pello, Miller, Olson, T'ien |
| `as_run_number` | global as-run test number (1–126, each once) |
| `test_id` | the PI's test number (B6, F1, P12, M10, O13a, T5, …) |
| `gmt_date_raw` | "Actual date" cell, verbatim |
| `sample_number` | verbatim |
| `material_raw` | verbatim material text (wrapped lines joined) |
| `material_family` | `PMMA_film`, `PMMA_slab`, `PMMA_rod`, `SIBAL_fabric`, `Nomex`, `candle_wax`, `PMMA_sphere`, `other` (rules: extraction_audit.md §A.3) |
| `pmma_color` | `black`, `clear` or blank (only when written) |
| `thickness_mm` | sheet thickness written in the material text (µm → mm); blank if not written |
| `width_cm` | width written in the material text; blank if not written as a width |
| `diameter_mm` | rod diameter written in the material text |
| `flow_configuration` | `opposed`, `concurrent`, `stagnation`, `unknown` ("?") |
| `fan_display_raw`, `air_display_raw` | verbatim cells; the air display is the cm/s sequence |
| `cal_o2_initial`, `cal_o2_final` | calibrated O2, vol% (numeric; blank when the cell is "-----") |
| `o2_initial_raw`, `o2_final_raw` | raw sensor O2 cells, verbatim (not used) |
| `observations_raw` | "Test observations and anomalies" cell, verbatim |
| `source_page` | printed page of the table row |
| `pdf_page` | PDF page (printed + 8) |
| `flow_configuration_raw`, `flow_configuration_source` | the cell as printed and where the configuration came from |
| `cal_o2_initial_raw`, `cal_o2_final_raw` | the calibrated O2 cells as printed |
| `o2_flag` | calibrated O2 outside 10–30 vol% (flagged, not deleted) |
| `flow_restrictor_raw`, `igniter_raw` | verbatim |
| `sample_reuse_of` | first test that used the same sample number (blank if this is the first use) |
| `catalog_notes` | pipeline notes (date typo, reuse, width not stated) |

## `data/processed/flame_points_v2.csv` (one row per labelled observation)

| Column | Meaning |
|---|---|
| `point_id` | `<test>_<b|x><flow>@<O2>` (b = burn, x = extinguished) |
| `test_id` | Appendix A test number; SIBAL points use the Table 7.1 id (GMT45-T4, …) |
| `pi_table` | A.1–A.5, or `7.1/A.6` for SIBAL |
| `material_family` | as in the catalog |
| `thickness_mm` | catalog value; Miller slabs: Table 5.1; SIBAL: 0.32 ("The thickness of the sample is about 0.32 mm", p. 94) |
| `width_cm` | catalog value; Miller slabs: Table 5.1; SIBAL: Table 7.1 |
| `diameter_mm` | rods only |
| `flow_configuration` | as in the catalog (SIBAL: concurrent) |
| `o2_pct` | calibrated O2: initial for burn points, final for extinction points; SIBAL: Table 7.1 O2; Table 5.1 points: its initial O2 |
| `flow_cm_s` | the stated cm/s value (never a pot setting) |
| `burn` | 1 = a flame was sustained at this condition, 0 = it was not (extinction, blowoff, no sustained ignition) |
| `label_confidence` | `high` or `medium` |
| `derivation_rule` | the rule that produced the point (list in extraction_audit.md §B) |
| `evidence_quote` | exact substring of the test's observation text, or of the whitespace-normalized page text |
| `source_page` | printed page of the evidence quote |
| `include_in_training` | False for exclusions (reason in `exclusion_reason`); excluded points are kept for display |
| `exclusion_reason` | why a point is not used for training |
| `appendix_test_id` | the Appendix A test the point comes from (SIBAL: the A.6 test matched by number and GMT day) |
| `pi`, `pmma_color`, `sides_burning` | provenance (sides from Table 5.1 for Miller slabs: 1 = one-sided, 2 = two-sided) |
| `o2_source`, `conditions_source` | which table each value came from |

## `data/processed/spread_rates_v1.csv`
See [`../model_card.md`](../model_card.md) §Spread rate: one row per Table 5.1 velocity with a measured spread rate (PMMA slabs).
