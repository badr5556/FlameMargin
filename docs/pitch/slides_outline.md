# Slides outline (8 slides)

One message per slide. Only VERIFIED / CORRECTED claims from `docs/science/claims_sheet.md`. Credit NASA images ("Image: NASA").

| # | Title | The one message | Visual | Speaker notes | Claim IDs |
|---|---|---|---|---|---|
| 1 | FlameMargin | Know your margin, and know when you don't. | Team IGNISPHERE, a credited NASA microgravity flame image | "We are IGNISPHERE, from Cairo. Our challenge is Flame in Freefall." | none |
| 2 | Tested on Earth, flown in space | Materials are screened in normal gravity, but they can burn at lower oxygen in microgravity. | Earth test icon vs ISS icon | "NASA relies on NASA-STD-6001B Test 1, in normal Earth gravity, to screen materials. BASS-II flame extinctions on the ISS indicated materials can burn at lower oxygen in microgravity. In PMMA rod tests: 17% vs 18% O2." | C11, C2, C2b |
| 3 | The next cabin is harder | Artemis air is an atmosphere of increased burning rate, and flammability is NASA's most critical hurdle there. | ISS (14.7 psia, 21%) vs Exploration Atmosphere (8.2 psia, 34%) points; line at 31.4% | "Exploration Atmosphere: 8.2 psia, 34% O2, still being evaluated. 31.4% is the no-increase limit at 8.2 psia. NESC 2026: 70% of the assessed ECLSS subsystems would need material replacements." | C4, C5, C6 |
| 4 | Real NASA data | 31 SIBAL tests from the BASS-II report → 21 burn/extinguish points with written rules. | Table 7.1 snippet → 4 rules (R1–R4) → 21 points (11 burn / 10 extinguished) | "Each test ramps the flow at fixed oxygen, so one test gives up to two observations. Rows without an outcome are shown, never used." | D1 (pending row verification) |
| 5 | The Flammability Map | P(burn) over oxygen × airflow, with every NASA test on it. | `docs/img/flammability_map.png` | "Quenching at low flow: our quench flows were 2.2–5 cm/s, matching NASA's 1–5 cm/s. Typical cabin circulation is 20–25 cm/s." | C3, C8b |
| 6 | Live demo | Map → Artemis OOD → Copilot with cited NASA tests. | Live app (`demo_script.md`) | Run Act 2. | (demo) |
| 7 | Honest by design | Artemis is out of distribution; the model refuses to guess. | Screenshot: red OOD banner + star above the data; Copilot first line "⚠️ Out of distribution" | "LOTO Brier 0.229 vs 0.263 baseline: modest, and shown. Code checks every number. Evals: LLM 13/14, fallback 14/14." | C4, C6 |
| 8 | Limits and next steps | One material, 1 atm, no spread rate; here is the plan. | Two columns: "Limits today" / "Next" (verify 31 rows, more BASS-II tables, FM2 lunar data, expert review) | "No long-duration fire experiment has been done in actual lunar gravity; FM2 will be the first. We'll add it. Thank you." | C10 |
