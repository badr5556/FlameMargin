# Model card: FlameMargin Prediction Engine (Layer 1)

> **Proof of pipeline on real NASA data, not a flight-qualification tool.**
> Every number in this card comes from `models/metrics.json` (written by `python -m src.model`) or from
> `data/processed/flame_points.csv` (written by `python src/data_pipeline/derive_points.py`).

## 1. What it predicts
**P(burn)**: the probability that a flame is sustained on **SIBAL cotton-fiberglass fabric** at a given O2
concentration and forced-flow speed, in ISS microgravity at 1 atm, with a 90% interval.

It does **not** predict a flame spread rate: the NASA extraction we use contains no spread-rate values
(`spread_rate_mm_s` is always `null`, reason: "no spread-rate measurements in the current NASA extraction").

## 2. Data
| Item | Value |
|---|---|
| Source | NASA/TM-20210011385 (BASS-II Summary Report), Section 7.1, Table 7.1, printed pp. 95–96 |
| Raw rows | 31 SIBAL fabric tests (`data/raw/bass2_sibal_table7_1_extracted.csv`), all 1 atm, ISS microgravity, concurrent flow |
| Raw O2 range | 16.4–21.0% |
| Explicit outcomes | 6 quenched, 3 no ignition, 1 blowoff; 2 more rows say "No blowoff" |
| Not used for training | 8 reused-sample rows and 11 rows without a definitive outcome (shown grey on the map) |
| Training points | **21 points from 12 tests: 11 burn, 10 extinguished** |
| Labelled O2 range | 16.4–18.7% (no test at 19–21% O2 reports a definitive outcome in the extraction) |
| Sample widths | 2.2 cm (15 points) and 1.2 cm (6 points) |
| Row verification | **PENDING**: the 31 rows have not yet been checked line by line against the PDF (`docs/data/verification_checklist.md`) |

### Derivation rules (stored per point in `derivation_rule`)
Each BASS-II test ramps the flow from `flow_start` to `flow_end` at fixed O2, so one test can give two observations.

| Rule | Event | Observations |
|---|---|---|
| R1 | `quenched` | burn=1 at (O2, flow_start), because a flame existed before the ramp; burn=0 at (O2, flow_end), because it quenched |
| R2 | `blowoff` | burn=1 at (O2, flow_start); burn=0 at (O2, flow_end) |
| R3 | comment "No blowoff" with flow increased | burn=1 at (O2, flow_start) and burn=1 at (O2, flow_end), because the flame survived the increase |
| R4 | `no_ignition` (non-reused) | burn=0 at (O2, flow); ignition failure is a conservative proxy for non-flammability |

### Sanity check against the verified literature
- **Quench end-flows: 2.2–5 cm/s** (2.2, 2.2, 2.6, 2.8, 3, 5). Consistent with claim **C3** (SIBAL flames quenched at 1–5 cm/s in µg).
  For the 2.2 cm samples the quench flow rises as O2 falls (18.7% → 2.2, 17.5% → 2.2, 17.4% → 2.6, 16.9% → 2.8 cm/s),
  which matches C3's "higher quenching speed at lower oxygen". The 5 cm/s value is a 1.2 cm sample (GMT190-T22).
- **No ignition at 16.4–16.8% O2** (GMT175-T9, GMT175-T10, GMT178-T12): the low end of the tested range, as expected.
- **Conflict, reported as is:** a **1.2 cm** sample blew off at **47 cm/s** at 17.2% O2 (GMT190-T21), while a **2.2 cm** sample
  survived an increase to **53 cm/s** at a *lower* 16.9% O2 (GMT178-T17). Sample width matters, which is why
  `sample_width_cm` is a model feature. With 6 points at 1.2 cm the width effect is poorly constrained.

## 3. Features
`o2_pct`, `log10_flow`, `log10_flow_sq` (lets a linear model bend into a U-shaped boundary: quenching branch at low flow,
blowoff at high flow), `sample_width_cm`. All standardized inside each model pipeline.

## 4. Models compared and validation
**Validation:** leave-one-test-out (`LeaveOneGroupOut` grouped by `test_id`, so both points of a test are held out together).
Every metric below is computed on the 21 out-of-fold predictions. Hyperparameters were not tuned on these folds
(logistic C = 1.0; GP kernel hyperparameters are fitted by marginal likelihood inside each training fold).

| Model | Accuracy | Balanced acc. | Brier ↓ | Log-loss ↓ | n points |
|---|---|---|---|---|---|
| Majority-class baseline | 0.333 | 0.318 | 0.263 | 0.719 | 21 |
| Logistic regression (L2, standardized) | 0.619 | 0.623 | 0.238 | 0.769 | 21 |
| **Gaussian process classifier (RBF + White)** ← chosen | **0.667** | **0.668** | **0.229** | **0.651** | 21 |
| GP with one length scale per feature (ARD), sensitivity only, not eligible | 0.619 | 0.623 | 0.237 | 0.674 | 21 |

- **Selection rule (fixed before training):** lowest LOTO Brier among eligible models; if none beats the baseline, ship the
  logistic regression. Result: the GP (Brier 0.229) beats the baseline (0.263), so it is the shipped model.
- **Baseline note:** the baseline predicts the training fold's majority class with probability = training class rate
  (`DummyClassifier(strategy="prior")`). Its accuracy (0.333) is *below* 50% because holding out a test shifts the
  training majority against that test's own points (a known leave-one-out artefact on balanced data); compare models on
  Brier and log-loss, where the baseline sits near a coin flip.
- **What it means:** the GP is better than the baseline, but only modestly. Its out-of-fold P(burn) averages 0.555 on
  burn points vs 0.491 on extinguished points, and 0.667 of its out-of-fold predictions lie between 0.4 and 0.6. With 21
  points from 12 tests this is a working, honest pipeline, not a precise predictor.
- The ARD GP was also scored, after the three pre-specified models, and is reported for transparency only.

## 5. Uncertainty and calibration
- **Interval:** 90% percentile interval of P(burn) over **300** bootstrap resamples of whole tests (resample the 12 tests
  with replacement, refit the GP each time; seed 42; 0 single-class resamples had to be redrawn).
- **Calibration note:** out of fold, the mean predicted P(burn) is 0.525 vs an observed burn rate of 0.524, so the model is
  not biased overall, but its predictions are compressed toward 0.5 (see above). 21 points are too few for a meaningful
  reliability diagram.
- **Bootstrap caveat:** in 0.37 of the replicates the GP length scale collapses below 0.05 (standardized units); such
  replicates memorize their training points and predict 0.5 elsewhere. This pulls interval ends toward 0.5 (e.g. an
  interval like 0.5–0.64). A bounded length-scale prior is the obvious next step; we did not tune it after seeing results.
- **Extrapolation rule:** far from the data a GP reverts to its prior, P(burn) = 0.5, and every bootstrap replicate does the
  same, so the raw band would collapse to [0.5, 0.5] and look certain. Wherever the kNN check (below) flags an
  extrapolation, the API therefore reports the interval as **[0, 1]**, sets `label = "uncertain"`, and keeps the raw band in
  `bootstrap_interval_raw` for transparency. 0.5 there means "no information", not "50% risk".
- **Ties:** a P(burn) that rounds to 0.50 is labelled `burn` (conservative for fire safety).

## 6. Out-of-distribution (OOD) rules
Hard rules are checked first; each one that triggers adds its own `ood_reason`, sets `ood_flag=True`,
`ood_level="out_of_envelope"`, and **no number is returned**.

| Hard rule | In-distribution range |
|---|---|
| Material | SIBAL cotton-fiberglass fabric only |
| Pressure | 14.7 psia (1 atm) ± 0.3 psia, i.e. 14.4–15.0 psia |
| Gravity | microgravity only (lunar, Mars and 1 g are OOD) |
| O2 | 16.4–21.0% |
| Flow | 2.0–53 cm/s |
| Sample width | 1.2–2.2 cm |

Then a **kNN distance check**: distance to the nearest training point in standardized (O2, log10 flow, width) space
(the squared flow term is left out so flow is not counted twice). Threshold = 95th percentile of the leave-one-test-out
nearest-neighbour distances = **1.682**. Above it: `ood_flag=True`, `ood_level="extrapolation"`, P(burn) is returned with
the [0, 1] interval above.

**Consequences (all tested in `tests/test_engine.py`):**
- **ISS cabin (14.7 psia, 21% O2, µg):** passes every hard rule, but the kNN check flags it as an extrapolation (distance
  3.28 at 20 cm/s), because no test at 21% O2 has a definitive outcome in the extraction. If the four 21% `BASS` rows
  report outcomes in the PDF, adding them would fix this (see the verification checklist).
- **Artemis Exploration Atmosphere (8.2 psia, 34% O2):** OOD on pressure and O2. No prediction.
- **Lunar habitat (8.2 psia, 34% O2, 1/6 g):** OOD on pressure, O2 and gravity. No prediction.
- **Kapton, Nomex, PMMA or any other material:** OOD (only SIBAL is in the data). No prediction.

This is the key honest finding: NASA's microgravity flammability data in this dataset do not reach the Exploration
Atmosphere, which mirrors the 2026 NESC finding that material flammability is the most critical hurdle there (claim C6).

## 7. Monotonicity sanity check
Physically, higher O2 should not lower P(burn) at a fixed flow. At 10 cm/s and 2.2 cm width, over 16.4–21.0% O2:
- **Logistic regression:** monotone (no violation).
- **Chosen GP: violated.** P(burn) has a small dip starting at 17.5% O2 (largest step down 0.041), peaks at 0.798 at
  18.7% O2 (the highest labelled O2) and falls back to 0.5 at 21.0%. The fall above 18.7% is the reversion to the prior in
  the extrapolation zone described above, not physics. The test `test_monotonicity_in_o2_is_reported_truthfully`
  checks that `metrics.json` reports this honestly.

## 8. Limits
- One material (SIBAL fabric), one pressure (1 atm), microgravity only, labelled O2 only 16.4–18.7%.
- 21 points from 12 tests; metrics are noisy and the improvement over the baseline is small.
- Labels are derived from start/end flows of a ramp, not from a continuous flow history; R4 uses ignition failure as a
  proxy for non-flammability.
- The 31-row extraction is not yet verified row by row against the PDF.
- No flame spread rate, no pressure or gravity dependence, no material transfer.
- Not a replacement for NASA-STD-6001 material testing. Decision support and a demonstration of the pipeline only.

## 9. Reproduce
```bash
python src/data_pipeline/derive_points.py   # 21 points + 19 display-only rows
python -m src.model                         # LOTO comparison, bootstrap, kNN threshold -> models/
python -m pytest -q                         # contract, OOD rules, derivation rules, metrics honesty
```
The artifact (`models/flame_model.joblib`) records the scikit-learn version; if a different version loads it, the API
retrains in-process with the same seeds instead of using a mismatched pickle.
