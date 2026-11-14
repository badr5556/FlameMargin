# FlameMargin claims sheet (science fact-check)

Owner: Omar Issam (AI Agent & Science Lead), team IGNISPHERE. First pass: 2026-11-13. Primary-source check: 2026-11-14.

## Rules
- **VERIFIED** = a team member opened the primary source (abstract or PDF) and it says this. The *Claim* cell is the
  exact wording we may use. Nothing in the app, README or pitch may be stronger than it.
- **CORRECTED** = the original claim was too strong; the corrected wording was checked against the primary source.
- **NOT VERIFIED** = only the 2026-11-13 search-extract pre-check exists (kept below). Say these only with "(pending
  verification)", or not at all on stage.
- **PENDING** = depends on work the team still has to do (named in the row).
- The same IDs, wording, sources and `verified` flags live in `src/copilot_facts.py`; `tests/test_facts.py` checks that
  every fact has a source and a boolean `verified`.

## Summary

| ID | Claim (exact wording we use) | Status | Source | Verified by |
|---|---|---|---|---|
| C1 | Without gravity there is no buoyant flow, so a candle flame in still air becomes round instead of teardrop-shaped. | NOT VERIFIED (pre-check: likely OK) | NASA SVS 31394, https://svs.gsfc.nasa.gov/31394 | pending |
| C2 | BASS-II flame extinctions on the ISS indicated that materials can burn at a lower oxygen concentration in microgravity than in normal gravity. | **VERIFIED** (first half of the original claim only; the ventilation-shutdown part is deleted) | Olson, ICES 2019, https://ttu-ir.tdl.org/items/1922ad9f-ef4c-4f52-96a4-980c23debe5e | primary source abstract/PDF, checked 2026-11-14 |
| C2b | In BASS-II opposed-flow tests on PMMA rods, flame spread was sustained at 17% O2 in microgravity vs 18% in normal gravity. | **VERIFIED** (new) | Scientific Reports 2017, doi:10.1038/s41598-017-18398-4 | primary source abstract/PDF, checked 2026-11-14 |
| C3 | On SIBAL cotton-fiberglass fabric in microgravity, flames were quenched at low flow speeds of 1–5 cm/s, with a higher quenching speed at lower oxygen. | **VERIFIED** ("~20 cm/s buoyant flow" and "only in µg" removed) | Zhao, T'ien, Ferkul, Olson 2015, NTRS 20150008962, https://ntrs.nasa.gov/citations/20150008962 | primary source abstract/PDF, checked 2026-11-14 |
| C4 | NASA's recommended Exploration Atmosphere was revised to 8.2 psia and 34% O2 (from 8.0 psia / 32%) to reduce hypoxia; final specifications are still being evaluated. | **VERIFIED** | NTRS 20240003211, https://ntrs.nasa.gov/citations/20240003211 | primary source abstract/PDF, checked 2026-11-14 |
| C5 | 31.4% O2 is the calculated upper limit that would not increase burning rate at 8.2 psia, so the 34% Exploration Atmosphere is an atmosphere of increased burning rate. | **VERIFIED** | Aerospace Medicine and Human Performance 89(9), 2018, p. 792 | primary source abstract/PDF, checked 2026-11-14 |
| C6 | A 2026 NASA NESC study found that material flammability is the most critical hurdle in the 8.2 psia / 34–40% O2 environment, where 70% of the assessed ECLSS subsystems would require material replacements, many not yet developed. | **VERIFIED** (replaces the 2026-11-13 "UNSUPPORTED" pre-check) | NASA/TM-20260003925 (NESC), https://ntrs.nasa.gov/citations/20260003925 | primary source abstract/PDF, checked 2026-11-14 |
| C7 | SIBAL fabric, which extinguishes immediately after ignition in Earth gravity, burned downward in air at lunar gravity in centrifuge and parabolic-flight tests; flame spread rate as a function of gravity may peak near lunar gravity. | **VERIFIED** (reworded) | NTRS 20240015307, https://ntrs.nasa.gov/citations/20240015307 ; LPSC 2026, NTRS 20260000646 | primary source abstract/PDF, checked 2026-11-14 |
| C8 | Saffire was the first large-scale fire intentionally set inside a spacecraft in orbit (uncrewed Cygnus), with an average forced airflow of about 20 cm/s. | **VERIFIED** | ICES-2017-224, NTRS 20170008805, https://ntrs.nasa.gov/citations/20170008805 | primary source abstract/PDF, checked 2026-11-14 |
| C8b | Saffire's 20–25 cm/s forced airflow is typical of spacecraft air circulation speeds. *(Context only; not a fans-off value.)* | **VERIFIED** (new) | Legros et al., Combustion and Flame | primary source abstract/PDF, checked 2026-11-14 |
| C9 | Older Mir tests found the Earth test conservative for the plastics they tested, compared with still or very slow air in microgravity. | NOT VERIFIED (pre-check: likely OK) | Hirsch & Beeson, SAE 2003-01-2643; NIST r0200470 | pending |
| C10 | No long-duration fire experiment has ever been done in actual lunar gravity; NASA's FM2 will be the first combustion experiment on another world, with launch planned for late 2026. | **CORRECTED** (never say "no lunar data at all": short partial-gravity tests exist, see C7) | LPSC 2026, NTRS 20260000646 | primary source abstract/PDF, checked 2026-11-14 |
| C11 | NASA relies on NASA-STD-6001B Test 1, conducted in normal Earth gravity, to screen material flammability for flight. | **VERIFIED** (reworded) | LPSC 2026, NTRS 20260000646 | primary source abstract/PDF, checked 2026-11-14 |
| C12 | The ISS cabin is kept close to sea-level air: about 14.7 psia and about 21% oxygen. | NOT VERIFIED (secondary sources only) | no NASA primary found yet | pending |
| C13 | NASA has data for many materials at 30% O2, but limited material flammability data above that level. | NOT VERIFIED (pre-check: likely OK) | NASA/TM-20260003925 | pending |
| C14 | The evidence suggests the Earth test is conservative compared with still air in microgravity, but not compared with ventilated microgravity; air-flow speed is the variable that decides. | TEAM SYNTHESIS of C2 + C9 (never attribute to NASA) | n/a | n/a |
| C2c | BASS-II concurrent-flow PMMA rods had a minimum flammable O2 of 13.6%; opposed-flow rods 16.3%. | **VERIFIED** (new) | Olson et al., ICES-2019-101, https://ttu-ir.tdl.org/bitstreams/2024efac-4733-4352-826e-8eaaa6954038/download · cross-check in NASA/TM-20210011385 below | primary source PDF, verified by Omar Issam, checked 2026-11-14 (team brief; the host was not reachable from the build sandbox, so the quote was not re-opened there) |
| C2d | µg limits were 1–2% O2 lower than 1 g limits; 1 g PMMA limits are 17% downward and 15.4% upward. | **VERIFIED** (new) | Olson et al., ICES-2019-101 (same URL as C2c) · cross-check in NASA/TM-20210011385 below | primary source PDF, verified by Omar Issam, checked 2026-11-14 (team brief; not re-opened in the build sandbox) |
| D1 | Training data: 85 tests / 192 points from NASA/TM-20210011385 Appendix A (Tables A.1–A.6), Table 7.1 and Table 5.1; SIBAL rows cross-checked against Zhao et al. 2015 (31/31 match). | **VERIFIED** (replaces the PENDING v1 wording) | NASA/TM-20210011385 pp. 57, 96, 103–113; Zhao, T'ien, Ferkul, Olson 2015, NTRS 20150008962 (Appendix table, p. 9) | checked 2026-11-14: all 126 Appendix A rows compared with the PDF page images; 20% re-check with a second extractor 26/26 (`docs/data/double_check_v2.md`); Table 7.1 vs Zhao 2015: 31/31 rows identical (`src/data_pipeline/crosscheck_zhao2015.py`) |
| D3 | In BASS-II on the ISS, Nomex III samples ignited only briefly and did not sustain a flame in concurrent flow at 21–22.2% O2 (tests F1, F2, F3; calibrated O2 22.2%, 21% and 21.7% at 9.5, 15 and 8 cm/s). | **VERIFIED** (new) | NASA/TM-20210011385, Table A.2 (p. 105) and Section 3.1.1 (p. 46) | primary source PDF, checked 2026-11-14 (quotes below) |

## Quotes for the new rows (2026-11-14)
**D3, Nomex (NASA/TM-20210011385, Table A.2, p. 105; calibrated O2 / air display from the same rows):**
- F1 (22.2% O2, 9.5 cm/s, concurrent): "Ignited briefly but did not spread at all and extinguished while the igniter was still on"
- F2 (21% O2, 15 cm/s, concurrent): "Tried to ignite, flame would not sustain"
- F3 (21.7% O2, 8 cm/s, concurrent): "Brief ignition flash, no sustained flame; no postburn sensor readings taken"
- Section 3.1.1 (p. 46): "The three Nomex® samples did not ignite, which is an excellent result for fire safety aboard the ISS."
  (Table A.2 is more precise: brief ignition, no sustained flame. We use the Table A.2 wording.)

**C2c cross-check against the report's own rod data:**
- Concurrent/stagnation rods (Section 6.1, Olson, p. 68): "Despite this limiting O2 concentration for ignition, flames ignited at a
  higher O2 survived to final O2 concentrations as low as 13.6 percent O2" — **agrees** with 13.6%. In Table A.5 that final 13.6% is
  test O4 ("Larger rod, decreased flow, extinguished at 0.36"), which Table A.5 lists as *stagnation*; Section 6.1 treats its rod
  series as "concurrent rod flammability tests" in axial stagnation flow (p. 64). Also p. 68: "Below an initial O2 concentration of
  ~14.5 percent O2, a sustained ignition could not be achieved".
- Opposed rods (Section 4, Fernandez-Pello): Figure 4.4(f) caption, p. 52: "Black PMMA rod, 3.18 mm, 16.3 percent O2, at 5 cm/s.
  Cap-shaped flame burned away initial hemispherical tip of rod to flat surface and then extinguished." and Table A.3, P21a
  (calibrated 16.3%): "Flame self-extinguished at 5 cm/s after sample end became flat, dim flame". **Agrees** that 16.3% is the
  lowest O2 at which an opposed-flow rod held a flame; note that p. 50 says flame *spread* was observed down to 17.5%: "While in
  microgravity, flame spread was observed at O2 concentrations as low as 17.5 percent, in normal gravity, flame spread was not
  observed below 19 percent."
- **C2d:** the report states the 1 g upward limit: "significantly lower than the observed upward flame spread limit of 15.4 percent O2
  (in normal gravity with an additional 4-cm/s forced flow" (p. 76) — **agrees** with 15.4% upward. The 17% downward limit and the
  "1–2% lower" wording are not stated in NASA/TM-20210011385; they rest on ICES-2019-101 only.

## Deleted or narrowed wording (do not use)
- D1 (v1): "Our model is trained on SIBAL fabric tests from Table 7.1 … PENDING row-by-row verification" (superseded by D1 above).
- D3: "Nomex does not ignite" as a blanket statement: Table A.2 shows brief ignition; say "did not sustain a flame" and keep the
  three conditions (concurrent flow, 21–22.2% O2, 8–15 cm/s, 1 atm).
- C2: anything like "shutting off ventilation may not be enough" (no source supports it).
- C3: "~20 cm/s buoyant flow in 1 g" and "the quenching branch exists only in µg".
- C6: the 70% figure is allowed **only** in the verified C6 sentence above (70% of the *assessed ECLSS subsystems*).
- C10: "no lunar-gravity combustion data exists". Short partial-gravity tests exist (C7); the correct statement is about
  long-duration experiments in actual lunar gravity.
- Any single "fans-off" flow value. C8b is typical circulation context, not a fans-off number; our data do not measure
  residual flow with fans off.

## How we use them
| Where | Claims |
|---|---|
| App: Flammability Map ventilation slider | C3, C8b |
| App: mission presets | C4 (Artemis EA), C10 (lunar), C12 (ISS, marked pending) |
| README problem statement | C11, C2, C5, C6 |
| Key honest finding (Artemis OOD) | C4, C6, model card section 6 |
| Copilot `get_background_fact` | every row except C14 and D1, each with its `verified` flag |
| README training-data sentence, model card, pitch counts | D1 |
| Copilot Nomex answers, pitch | D3 (with the F1/F2/F3 evidence rows from the engine) |
| Pitch (µg vs 1 g limits for PMMA rods) | C2c, C2d |

## Pre-check notes kept for the NOT VERIFIED rows (2026-11-13, search extracts only)
| ID | Open | Ctrl+F | Pre-check |
|---|---|---|---|
| C1 | https://svs.gsfc.nasa.gov/31394 | "buoyan", "round", "spher" | Page says buoyancy shapes the candle flame on Earth; without gravity the flame becomes round. Its images are SoFIE fabric flames, which are not spherical, so keep the "candle flame in still air" scope. |
| C9 | SAE 2003-01-2643 abstract; NIST r0200470 | "conservative", "quiescent" | Abstract: the upward-propagation ground test was conservative for the polymers tested; NIST: conservative compared with quiescent µg, degree varies by material. |
| C12 | any NASA ISS ECLSS document | "14.7", "21" | Only secondary sources found (about 101.3 kPa, about 21% O2). |
| C13 | NTRS 20260003925 PDF | "30% O" | Extract: data for many materials at 30% O2, limited above that. |

When a row is checked, change its status here **and** set `verified: True` for the matching entry in `src/copilot_facts.py`.
