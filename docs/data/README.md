# FlameMargin BASS-II Data Package

> **v2 (2026-11-14): the full BASS-II test catalog.** All 126 tests of NASA/TM-20210011385 Appendix A (Tables A.1–A.6) are
> transcribed in `data/raw/bass2_appendix_a_tests.csv` and turned into 215 traceable points (192 for training, 5 materials) in
> `data/processed/flame_points_v2.csv`. Start here:
> - [`extraction_audit.md`](extraction_audit.md): how the tables were read, counts, every uncertain row, the labelling rules and exclusions
> - [`data_dictionary_v2.md`](data_dictionary_v2.md): every column of the catalog and the points
> - [`double_check_v2.md`](double_check_v2.md): independent 20% re-check with a second extractor (26/26 rows pass)
> - [`points_recheck_v2.md`](points_recheck_v2.md): 20% re-check of the labelled points against the source text (43/43 pass)
> - Table 7.1: the 31 v1 rows below match the report text (31/31) and Zhao et al. 2015 (31/31); the v1 checklist is closed.
>
> The v1 description below is kept for the before/after comparison.

Prepared by the IGNISPHERE data team (Data & ML Lead: Adel Elwan) and integrated into the repo layout below.

## What this package contains
This is a conservative, traceable processing package built from the supplied extraction (31 rows of SIBAL cotton-fiberglass fabric tests) and the original NASA/TM-20210011385 PDF. The NASA report states that 126 tests were conducted overall, but the supplied structured extraction contains only 31 rows. This package does **not** claim to reconstruct all 126 tests.

## Where the files live in the repo
```text
data/
├── raw/bass2_sibal_table7_1_extracted.csv     # the supplied 31-row extraction, byte-for-byte unchanged
├── processed/
│   ├── bass2_extracted_data.csv               # clean_data.py output (all 31 rows + provenance columns)
│   ├── bass2_extracted_data.json              # same records as nested experiment objects
│   ├── flame_points.csv                       # derive_points.py: 21 binary observation points (training)
│   └── display_only_points.csv                # derive_points.py: 19 rows shown on the map only (grey)
└── ml_ready/
    ├── classification_dataset.csv             # 10 explicit-event rows (3-class event label)
    └── regression_dataset.csv                 # empty schema: no spread-rate values exist
src/data_pipeline/
├── inspect_data.py
├── clean_data.py
├── prepare_datasets.py
├── validate_data.py
└── derive_points.py                           # added during integration (binary points, written rules)
docs/data/
├── README.md                                  # this file
├── data_dictionary.md
├── source_map.md
├── data_quality_report.md
├── ml_feasibility_report.md
└── verification_checklist.md                  # 31-row check against the PDF table (to do)
```

## Reproduce
From the repo root:
```bash
python -m pip install -r requirements.txt
python src/data_pipeline/inspect_data.py
python src/data_pipeline/clean_data.py
python src/data_pipeline/prepare_datasets.py
python src/data_pipeline/validate_data.py
python src/data_pipeline/derive_points.py
```
Re-running `clean_data.py` and `prepare_datasets.py` reproduces the committed processed and ML-ready CSVs byte for byte.

## Data interpretation
- Original extracted columns are retained.
- Added fields identify provenance and leave scientifically unsupported targets null.
- `flow_start_cm_s` and `flow_end_cm_s` remain separate. They are not converted to a single representative velocity.
- The JSON preserves each test as an experiment record and stores the start/end flow pair as a nested `flow_profile`.
- Classification uses only explicit non-reused event labels (`quenched`, `no_ignition`, `blowoff`). It is a three-class exploratory target, not a binary flammability verdict.
- Regression output is empty because the supplied SIBAL extraction contains no numerical flame spread-rate target.
- The report-wide NASA count of 126 tests is metadata only; it is not padded into synthetic records.

## Binary observation points (added during integration)
`derive_points.py` turns each test's start→end flow ramp into at most two burn/extinguish observations, using four written rules (R1 quenched, R2 blowoff, R3 "No blowoff" with flow increased, R4 no_ignition). The rule that produced each point is stored in its `derivation_rule` column. Reused-sample rows and rows without a definitive outcome are not used for training; they are kept in `display_only_points.csv` and shown as grey points on the map. See `docs/model_card.md` for the full rule table.

## Scientific limitations
The 31-row extraction has not been checked line-by-line against Table 7.1 (see `verification_checklist.md`). The PDF's Appendix A test matrices and PI sections contain further information, including multiple velocity steps, qualitative outcomes, and potentially numerical spread-rate data. Those must be extracted and source-verified before claiming complete 126-test coverage or training a general-purpose FlameMargin model.

The original NASA PDF is not copied into this repo; retain it as the authoritative source document.
