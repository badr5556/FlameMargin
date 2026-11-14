# Machine Learning Feasibility Report

## Executive decision
The current supplied extraction supports a **small, exploratory event-label dataset only**. It does **not** support a numerical flame-spread regression dataset. It is not a validated all-material BASS-II training corpus.

## Classification
- Total extracted SIBAL rows: 31.
- Unique tests: 31.
- Conservative primary rows with explicit label and non-reused sample: 10.
- Target is `classification_target_event`, retaining the event classes exactly as extracted.
- Class counts: {'quenched': 6, 'no_ignition': 3, 'blowoff': 1}.
- Excluded from this primary subset: reused samples; `not_reported` records; any event labels outside the explicit supported set.
- This is a **3-class event label** (`quenched`, `no_ignition`, `blowoff`), not a clean ignition/sustained-combustion binary target.
- There is only one `blowoff` observation; class imbalance is severe. A supervised classifier is not currently suitable for a defensible performance claim.
- Feature availability is limited to SIBAL fabric sample width/length/approximate thickness, oxygen, start/end airflow, configuration, pressure, and gravity environment. Several are constant across the subset.
- The scalar `airflow_velocity_cm_s` is deliberately null: using start or end flow as a representative feature would be a modeling assumption, not source data.
- Do not use row-random splitting if additional repeated measurements are later introduced. Group by `test_id`; if each test_id has one row, grouped split is equivalent to row grouping but still preferred.
- Do not apply SMOTE to this tiny, physically constrained, highly imbalanced sample.

## Regression
- Valid numerical flame spread-rate observations in the supplied extraction: **0**.
- Unique tests with numerical spread rates: **0**.
- Target range/distribution: not available.
- Therefore regression is **not supported** by the current SIBAL CSV.
- `regression_dataset.csv` is an empty schema-bearing file, not a trained-model input dataset.

## Recommended validation strategy
1. Do not report accuracy/F1/R² from the present data as a performance claim. (Integration note: the binary model in `docs/model_card.md` reports leave-one-test-out metrics next to a majority-class baseline, explicitly as an exploratory proof of pipeline, not as a validated performance claim.)
2. When a richer extraction exists, use `GroupKFold` or `GroupShuffleSplit` keyed by `test_id`, with all within-test velocity points assigned to one fold.
3. Keep material/PI groups visible. A stronger generalization test is leave-one-test-out or leave-one-material/PI-group-out where sample sizes permit.
4. Establish a simple physics-informed baseline and compare against it only after enough independent tests exist.
5. Keep an untouched test group. With only 10 eligible labelled rows and a singleton class, even cross-validation estimates will be unstable.

## Claims in an earlier summary that are not verified by supplied files
An earlier, unverified executive summary described a much larger, fully labelled dataset (all 126 tests with complete outcomes), a specific train/test class split, a separate set of regression tests with spread-rate values, a recommended Miller `M1–M20` subset, and a high expected regression score. None of these is present in, or reproducible from, the supplied structured data:
- Complete outcome labels for all 126 tests: not present in the supplied extracted CSV (31 rows, 13 without a definitive outcome).
- The quoted class split: not reproducible from current files.
- Regression tests and a Miller velocity profile: not present in current extraction; not verified here.
- Miller `M1–M20` subset with complete features and numerical rates: cannot be accepted based on current supplied structured data. Appendix A.4 is a test matrix; detailed data and spread-rate values require extraction from the appropriate report section and table/figure.
- The quoted regression score: unsupported and must not be claimed without grouped model evaluation.

These numbers are deliberately not repeated anywhere in the repo.

## Integration recommendation
- Main CSV/JSON: suitable for exploratory backend ingestion with provenance flags and null targets.
- Classification CSV: suitable only for UI/data-pipeline smoke tests, not production model training or validation.
- Regression CSV: not model-ready; no target observations.
- Do not present model outputs from these records as spacecraft safety determinations.
