# Space Apps project page text (ready to paste)

Claim IDs in brackets are for the team; remove them before pasting. Numbers come from `models/metrics.json` and `evals/results.md`.

---

## Project name
FlameMargin

## High-level summary (short)
NASA relies on NASA-STD-6001B Test 1, conducted in normal Earth gravity, to screen material flammability for flight [C11],
yet BASS-II flame extinctions on the ISS indicated that materials can burn at a lower oxygen concentration in microgravity
[C2]. FlameMargin turns all 126 of NASA's own ISS fire tests (BASS-II, NASA/TM-20210011385 Appendix A) into a live flammability
map: the probability that a flame survives on five materials (SIBAL fabric, PMMA film, slab and rod, Nomex), as a function of
oxygen and airflow, with honest uncertainty and every NASA test point on the map. A Fire Safety Copilot answers questions only through the model. Its key
honest finding: none of the 126 BASS-II tests reaches the Artemis Exploration Atmosphere (8.2 psia / 34% O2) [C4], so
FlameMargin flags it as out of distribution for every material instead of guessing, which mirrors NASA's 2026 NESC finding that material
flammability is the most critical hurdle in that environment [C6].

## What it does
- **Prediction Engine:** P(burn) with a 90% bootstrap interval for five materials at a given O2 and forced-flow speed, plus the
  three nearest real NASA tests (test ID, the crew's words and the report page). Trained on 192 observations (166 burn,
  26 extinguished) from 85 BASS-II tests, derived with written rules; every point carries a verbatim quote and its page.
  Leave-one-test-out validation: AUC 0.82; Brier 0.087 vs 0.118 for a baseline (a Brier skill of +26%). A flame spread rate for PMMA slabs (Table 5.1).
  Per-material out-of-distribution rules (material, pressure, gravity, configuration, O2, flow, size) return no number; a
  distance check flags extrapolations.
- **Flammability Map:** P(burn) over O2 × airflow (log scale) with the 0.5 boundary, the data envelope, extrapolation zones and
  every NASA test point of the selected material; mission presets for the ISS cabin, the Artemis Exploration Atmosphere and a lunar habitat; a cabin
  ventilation slider whose low end is "Fans OFF / near-quiescent" (we do not invent a fans-off number).
- **Fire Safety Copilot:** a Gemini-based agent (English and Arabic) that can only answer through the prediction tools. Code
  checks every number and NASA test ID against tool results, checks that verdict words match the model's label, puts
  out-of-distribution warnings on the first line, refuses invented inputs, and falls back to a deterministic mode.

## Why it matters
The 34% Exploration Atmosphere is an atmosphere of increased burning rate: 31.4% O2 is the calculated upper limit that would
not increase burning rate at 8.2 psia [C5]. A 2026 NASA NESC study found that 70% of the assessed ECLSS subsystems would
require material replacements in the 8.2 psia / 34–40% O2 environment, many not yet developed [C6]. Engineers need to see
both where margins are thin and where the data simply run out.

## How we built it
- Python, pandas, pdfplumber, scikit-learn (logistic regression, Gaussian process, gradient boosting, bootstrap), Plotly, Streamlit.
- Data: NASA/TM-20210011385, Appendix A (all 126 tests), Table 7.1 and Table 5.1, extracted by the team; written derivation
  rules stored per point with a verbatim quote and page; a 20% re-check with a second extractor (26/26) and the SIBAL rows
  cross-checked against Zhao et al. 2015 (31/31); rows without an outcome kept for display only.
- Copilot: Google Gemini via the `google-genai` SDK with manual function calling over 6 tools; grounding, claim-consistency,
  input and OOD guards in code; backup key and per-session budget for the public link.
- Testing: 329 unit tests; a 15-question adversarial eval (final run: LLM 14/15, deterministic fallback 14/15; the LLM miss was the
  grounding guard withholding an ungrounded draft, the fallback miss a 3.4 s answer against a 3 s latency budget).
- Science: every claim has an ID, exact wording, primary source and verification status in our claims sheet.

## Challenges
- **Small, messy data:** 126 tests written as crew notes; many extinctions were logged as fan settings with no airflow value, so we only used what was stated in cm/s. We validated by leaving out whole tests.
- **Labels from flow ramps:** each test changes the flow at fixed O2, so we wrote explicit rules for what each event means.
- **Honesty under pressure:** v2 is worse than v1 on SIBAL's own early points (a pre-registered fix narrowed it but lost overall, so we did not ship it), and PMMA rods were never tested at ISS oxygen; we show both.
- **LLM reliability:** rules are enforced in code, with an offline path that passes every eval.

## What's next
1. Give each material its own flow behaviour (SIBAL's low-flow quenching branch) and re-validate.
2. Get the PIs' raw spread-rate data for the other materials instead of reading figures.
3. Add pressure as a feature once microgravity data at other pressures exist.
4. Add lunar data when NASA's FM2, the first combustion experiment on another world, flies [C10].

## Space Agency data used (attribution)
- NASA Glenn Research Center, *Burning and Suppression of Solids–II (BASS-II) Summary Report*, NASA/TM-20210011385, Appendix A (Tables A.1–A.6), Table 7.1 and Table 5.1 (training data).
- NASA Physical Sciences Informatics (PSI): BASS-II investigation, PSI-25, DOI 10.60555/4qc4-de67.
  https://psi.nasa.gov/physci/repo/data/investigations/PSI-25
- Science claims (primary sources listed per claim in `docs/science/claims_sheet.md`): Olson, ICES 2019; Scientific Reports 2017
  (doi:10.1038/s41598-017-18398-4); NTRS 20150008962; NTRS 20240003211; Aerospace Medicine and Human Performance 89(9), 2018;
  NASA/TM-20260003925 (NESC); NTRS 20240015307; LPSC 2026 (NTRS 20260000646); ICES-2017-224 (NTRS 20170008805); Legros et al., Combustion and Flame.

NASA does not endorse this project.

## Use of Artificial Intelligence
The IGNISPHERE team conceived FlameMargin, designed its three-layer architecture and the Copilot's safety rules (tool-only numbers, OOD-first answers, grounding checks, deterministic fallback), extracted and organized the NASA test data, selected and verified the NASA sources, and reviewed and tested every component. We used AI assistants (Claude, by Anthropic; and others for data extraction support) to help implement and test parts of the code and to draft documentation under the team's direction. Google Gemini is the runtime LLM inside the Copilot; it never produces numbers on its own, and every number comes from our model through tool calls. All scientific claims are traceable to the primary sources in `docs/science/claims_sheet.md`.

## Team
IGNISPHERE, NASA Space Apps Cairo 2026:
- Omar Issam — AI Agent & Science Lead
- Adel Elwan — Data & ML Lead (data extraction package)
- Badr Mostafa — Product & Backend Lead (deployment)
- Ahmed Mohamed Ahmed — Team member
- Sherif Alnegoly — Team member
- Raphael Robeir — Team member

## Links
- Live demo: https://flamemargin.streamlit.app/
- Repository: https://github.com/badr5556/FlameMargin
- Demo video: [FILL: video link after recording]
