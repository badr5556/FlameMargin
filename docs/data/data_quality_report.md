# Data Quality Report

## Inspected artifacts
- `TM-20210011385.pdf`: PDF, 141 pages, 48,972,416 bytes; NASA report.
- The supplied extraction (`data/raw/bass2_sibal_table7_1_extracted.csv` in this repo): CSV, 31 rows × 18 source columns.
- The task specification and the FlameMargin team brief (PDF and images) were also reviewed; they are contextual materials, not raw experimental data.

## Actual counts
- Rows in supplied SIBAL extraction: **31**.
- Unique `test_id`: **31**.
- Duplicate complete rows: **0**.
- Duplicate `test_id` rows: **0**.
- Reused-sample rows: **8**.
- Non-reused-sample rows: **23**.
- NASA report-wide total: **126 tests**, stated in Section 1.1; this is not the row count of the supplied extraction.

## Missing values (original 18-column CSV)
| Column | Missing |
|---|---:|
| `test_id` | 0 |
| `campaign` | 0 |
| `material` | 0 |
| `sample_width_cm` | 0 |
| `flow_start_cm_s` | 0 |
| `flow_end_cm_s` | 0 |
| `o2_vol_percent` | 0 |
| `reported_comment` | 7 |
| `conservative_event_label` | 0 |
| `reused_sample` | 0 |
| `sample_length_cm` | 0 |
| `sample_thickness_mm_approx` | 0 |
| `pressure_atm` | 0 |
| `gravity_environment` | 0 |
| `flow_configuration` | 0 |
| `source` | 0 |
| `source_page` | 0 |
| `notes` | 10 |

## Event labels (as extracted; not silently reclassified)
| Label | Rows |
|---|---:|
| `not_reported` | 13 |
| `quenched` | 6 |
| `ignited_reused` | 4 |
| `no_ignition` | 3 |
| `no_ignition_reused` | 3 |
| `blowoff` | 1 |
| `one_sided_flame_reused` | 1 |

## Issues and caveats
- The CSV is a 31-row subset for SIBAL cotton-fiberglass fabric; it is not the complete BASS-II experiment archive.
- All 31 test IDs are unique in this subset. The extraction stores start and end flow values, but no complete per-step velocity series. No repeated test IDs were detected in this subset.
- `reported_comment` is missing in 7 rows; `notes` is missing in 10 rows. Missing comment is not evidence of no ignition or no combustion.
- `conservative_event_label` contains 13 `not_reported` values. These must remain unknown, not be mapped to ignition or sustained burn.
- Labels such as `quenched`, `no_ignition`, and `blowoff` describe different physical events. They are not interchangeable binary outcomes.
- Eight rows are marked as reused samples by the extraction. These are retained in the main dataset but excluded from the conservative primary classification subset.
- The original CSV reports O2 in vol% and flow in cm/s. Sample dimensions are mixed cm/mm by column. No conversions were made.
- `sample_thickness_mm_approx` is explicitly approximate; treat it as approximate metadata, not exact metrology.
- The current source CSV contains no numerical flame spread-rate column. Regression observations from this file: zero.
- A single `airflow_velocity_cm_s` was not fabricated from start/end velocities.
- `ignition_outcome` and `sustained_combustion` remain null because the extraction does not provide a fully defensible canonical target for every row.
- The full NASA appendix tables are very wide and contain operational details, multi-step velocities, and narrative observations. They require structured manual/table extraction and source-level checking before merging.

## Verification status
- Report-level count of 126 tests: verified directly in NASA Section 1.1.
- Current 31 SIBAL rows: inspected structurally; source mapping is stated in the extraction, but row-by-row comparison to the PDF table is not complete.
- No suspicious numeric values have been silently corrected. There are no unit conversions.
- No evidence was found in the current extraction to support a 126-row all-material ML dataset.
