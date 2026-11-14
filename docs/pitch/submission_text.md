# Space Apps project page text (ready to paste)

Claim IDs in brackets are for the team; remove them before pasting. Numbers come from `models/metrics.json` and `evals/results.md`.

---

## Project name
FlameMargin

## High-level summary (short)
NASA relies on NASA-STD-6001B Test 1, conducted in normal Earth gravity, to screen material flammability for flight [C11],
yet BASS-II flame extinctions on the ISS indicated that materials can burn at a lower oxygen concentration in microgravity
[C2]. FlameMargin turns NASA's own ISS fire tests (BASS-II, NASA/TM-20210011385 Table 7.1) into a live flammability map:
the probability that a flame survives on SIBAL cotton-fiberglass fabric, as a function of oxygen and airflow, with honest
uncertainty and every NASA test point on the map. A Fire Safety Copilot answers questions only through the model. Its key
honest finding: NASA's microgravity data in this dataset do not reach the Artemis Exploration Atmosphere (8.2 psia / 34% O2)
[C4], so FlameMargin flags it as out of distribution instead of guessing, which mirrors NASA's 2026 NESC finding that material
flammability is the most critical hurdle in that environment [C6].

## What it does
- **Prediction Engine:** P(burn) with a 90% bootstrap interval for SIBAL fabric at a given O2 and forced-flow speed, plus the
  three nearest real NASA tests (test ID and report page). Trained on 21 observations (11 burn, 10 extinguished) derived from
  12 BASS-II tests with four written rules. Leave-one-test-out validation: Brier 0.229 vs 0.263 for a majority-class baseline.
  Hard out-of-distribution rules (material, pressure, gravity, O2, flow) return no number; a distance check flags extrapolations.
- **Flammability Map:** P(burn) over O2 × airflow (log scale) with the 0.5 boundary, the data envelope, extrapolation zones and
  all 31 NASA tests; mission presets for the ISS cabin, the Artemis Exploration Atmosphere and a lunar habitat; a cabin
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
- Python, pandas, scikit-learn (Gaussian process classifier, logistic regression, bootstrap), Plotly, Streamlit.
- Data: NASA/TM-20210011385, Section 7.1, Table 7.1 (31 SIBAL tests), extracted by the team; four written derivation rules
  stored per point; rows without an outcome kept for display only.
- Copilot: Google Gemini via the `google-genai` SDK with manual function calling over 6 tools; grounding, claim-consistency,
  input and OOD guards in code; backup key and per-session budget for the public link.
- Testing: 167 unit tests; a 14-question adversarial eval (final run: LLM 13/14, deterministic fallback 14/14).
- Science: every claim has an ID, exact wording, primary source and verification status in our claims sheet.

## Challenges
- **Tiny data:** 31 rows, 12 with a usable outcome. We validated by leaving out whole tests and reported a modest gain over a baseline.
- **Labels from flow ramps:** each test changes the flow at fixed O2, so we wrote explicit rules for what each event means.
- **Honesty under pressure:** even the ISS at 21% O2 is an extrapolation for our labelled data, and we show it that way.
- **LLM reliability:** rules are enforced in code, with an offline path that passes every eval.

## What's next
1. Two teammates verify the 31 extracted rows against the PDF (checklist in the repo).
2. Extract the other BASS-II tables (more materials and flow steps) and re-validate.
3. Bound the Gaussian process length scale and publish calibration on more tests.
4. Add lunar data when NASA's FM2, the first combustion experiment on another world, flies [C10].

## Space Agency data used (attribution)
- NASA Glenn Research Center, *Burning and Suppression of Solids–II (BASS-II) Summary Report*, NASA/TM-20210011385, Section 7.1, Table 7.1 (training data).
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
