# Slides outline (8 slides)

One message per slide. Only VERIFIED / CORRECTED claims from `docs/science/claims_sheet.md`. Credit NASA images ("Image: NASA").

| # | Title | The one message | Visual | Speaker notes | Claim IDs |
|---|---|---|---|---|---|
| 1 | FlameMargin | Know your margin, and know when you don't. | Team IGNISPHERE, a credited NASA microgravity flame image | "We are IGNISPHERE, from Cairo. Our challenge is Flame in Freefall." | none |
| 2 | Tested on Earth, flown in space | Materials are screened in normal gravity, but they can burn at lower oxygen in microgravity. | Earth test icon vs ISS icon | "NASA relies on NASA-STD-6001B Test 1, in normal Earth gravity, to screen materials. BASS-II flame extinctions on the ISS indicated materials can burn at lower oxygen in microgravity. In PMMA rod tests: 17% vs 18% O2." | C11, C2, C2b |
| 3 | The next cabin is harder | Artemis air is an atmosphere of increased burning rate, and flammability is NASA's most critical hurdle there. | ISS (14.7 psia, 21%) vs Exploration Atmosphere (8.2 psia, 34%) points; line at 31.4% | "Exploration Atmosphere: 8.2 psia, 34% O2, still being evaluated. 31.4% is the no-increase limit at 8.2 psia. NESC 2026: 70% of the assessed ECLSS subsystems would need material replacements." | C4, C5, C6 |
| 4 | Real NASA data | All 126 BASS-II tests → 192 burn/extinguish points for 5 materials, each with a quote and page. | Appendix A snippet → written rules → 192 points (166 burn / 26 extinguished) from 85 tests | "Every point carries the crew's own words and the report page. Rows without an outcome are shown, never used." | D1 |
| 5 | The Flammability Map | P(burn) over oxygen × airflow, with every NASA test on it. | `docs/img/flammability_map.png` | "Quenching at low flow: SIBAL's quench flows in our data were 2.2–5 cm/s, matching NASA's 1–5 cm/s. Typical cabin circulation is 20–25 cm/s." | C3, C8b |
| 6 | Live demo | Map → Artemis OOD → Copilot with cited NASA tests. | Live app (`demo_script.md`) | Run Act 2. | (demo) |
| 7 | Honest by design | Artemis is out of distribution; the model refuses to guess. | Screenshot: red OOD banner + star above the data; Copilot first line "⚠️ Out of distribution" | "LOTO Brier 0.087 vs 0.118 baseline, and shown per material. Code checks every number. Evals: LLM 15/15, fallback 15/15." | C4, C6 |
| 8 | Limits and next steps | 1 atm only, one-sided labels for film and Nomex, spread rate for slabs only; here is the plan. | Two columns: "Limits today" / "Next" (per-material flow terms, PI raw data for spread rates, FM2 lunar data, expert review) | "No long-duration fire experiment has been done in actual lunar gravity; FM2 will be the first. We'll add it. Thank you." | C10 |
