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
| D1 | Our model is trained on SIBAL fabric tests from NASA/TM-20210011385 Table 7.1 (BASS-II, ISS, 1 atm). | **PENDING** row-by-row verification | NASA/TM-20210011385, Section 7.1, Table 7.1, printed pp. 95–96 | pending: `docs/data/verification_checklist.md` (31 rows, two people, about 20 minutes) |

## Deleted or narrowed wording (do not use)
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

## Pre-check notes kept for the NOT VERIFIED rows (2026-11-13, search extracts only)
| ID | Open | Ctrl+F | Pre-check |
|---|---|---|---|
| C1 | https://svs.gsfc.nasa.gov/31394 | "buoyan", "round", "spher" | Page says buoyancy shapes the candle flame on Earth; without gravity the flame becomes round. Its images are SoFIE fabric flames, which are not spherical, so keep the "candle flame in still air" scope. |
| C9 | SAE 2003-01-2643 abstract; NIST r0200470 | "conservative", "quiescent" | Abstract: the upward-propagation ground test was conservative for the polymers tested; NIST: conservative compared with quiescent µg, degree varies by material. |
| C12 | any NASA ISS ECLSS document | "14.7", "21" | Only secondary sources found (about 101.3 kPa, about 21% O2). |
| C13 | NTRS 20260003925 PDF | "30% O" | Extract: data for many materials at 30% O2, limited above that. |

When a row is checked, change its status here **and** set `verified: True` for the matching entry in `src/copilot_facts.py`.
