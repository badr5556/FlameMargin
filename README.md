# FlameMargin

**Team IGNISPHERE · NASA Space Apps Cairo 2026 · Challenge: *Flame in Freefall: AI-Powered Fire Safety
Insights from Microgravity Combustion Data***

FlameMargin estimates how close a cabin material is to burning in a given spacecraft atmosphere
(O2, pressure, air flow, gravity), shows the margin on a map, and lets an operator ask questions in plain
English or Arabic through a Copilot that only answers from the model's outputs.

> ### ⚠️ Project status (2026-11-13)
> - **Layer 3 (Copilot): working on `main`.** Chat UI, tool layer, code-level guardrails, 67 unit tests,
>   12-question adversarial eval (12/12 pass in both LLM and offline modes; `evals/results.md`).
> - **Layers 1 and 2 (prediction model and map/dashboard): integration in progress.** `src/api.py` and
>   `app.py` are not on `main` yet.
> - **Until `src/api.py` lands, every number the Copilot shows comes from a placeholder mock**
>   (`src/copilot_mock_api.py`). It is synthetic, NOT NASA data, and it is labelled "mock" in every answer
>   and in the UI. The Copilot switches to the real model automatically when `src/api.py` exists.
> - **Science claims are not yet verified against opened primary sources.** See
>   `docs/science/claims_sheet.md` for each claim's status.

## Problem

Spacecraft cabin materials are screened for flammability on Earth, with an upward-flame test in normal
gravity (claim C11). In microgravity, flames behave differently because there is no buoyant flow, and the
air flow from ventilation becomes the variable that decides whether a material burns (C1, C2, C9, C14).
NASA's planned Exploration Atmosphere uses more oxygen at lower pressure than the ISS (C4, C12), a
region where material flammability data are limited (C13).

## Why microgravity matters

Every statement below has a claim ID in [`docs/science/claims_sheet.md`](docs/science/claims_sheet.md).
All are currently `NOT VERIFIED` (sources found but not yet opened by a human); we use only the safe wording.

- Without gravity there is no buoyant flow, so a candle flame in still air becomes round instead of
  teardrop-shaped. (C1)
- In the BASS-II experiments on the ISS, with a gentle ventilation flow, some materials kept burning at lower
  oxygen levels than their limits measured on Earth. (C2)
- On the ISS, flames on SIBAL cotton-fiberglass fabric went out when the air flow was lowered to about
  1-5 cm/s, and at a higher flow when oxygen was lower. (C3)
- Counter-evidence: older Mir tests found the Earth test conservative for the plastics they tested, compared
  with still or very slow air in microgravity. (C9) Our reading of C2 + C9: the Earth test looks conservative
  against still air, but not against ventilated microgravity. That is why flow velocity is a model input. (C14,
  team synthesis)
- NASA's recommended Exploration Atmosphere is 8.2 psia with 34% O2 (C4). At 8.2 psia, the calculated O2
  limit for no increase in burning rate is 31.4% (C5), and NASA reports limited material flammability data
  above 30% O2 (C13).
- Some materials that do not burn in Earth gravity can burn in microgravity or in partial gravity like the
  Moon's (C7). No fire test has been run on the Moon yet; NASA's FM2 experiment is planned to do this (C10).

## What FlameMargin does (3 layers)

| Layer | What it does | Owner | Status on `main` |
|---|---|---|---|
| 1. Prediction engine (`src/api.py`) | Learns from microgravity combustion test data; predicts burn / extinguish, a limiting O2 and an uncertainty interval for a material at given O2, pressure, flow and gravity; flags out-of-distribution inputs; returns nearest real experiments | Teammate A | In progress |
| 2. Margin map (`app.py`) | Flammability boundary (O2 limit vs. flow) per material, with mission presets: ISS cabin, Artemis Exploration Atmosphere, Lunar habitat | Teammate B | In progress |
| 3. Fire Safety Copilot (`src/copilot*.py`) | LLM agent that answers operator questions **only through Layer 1 tools**; code checks that every number in the answer exists in a tool result; out-of-distribution warning comes first; offline rule-based fallback | Omar | **Done** (on mock data) |

## Data sources

See [`docs/data_sources.md`](docs/data_sources.md). Main source: NASA Physical Sciences Informatics (PSI),
BASS-II investigation (PSI-25), plus published results on the NASA Technical Reports Server. The repo file
`combustion_sample.csv` is a 3-row placeholder, not NASA data.

## Method

1. **Data (Layer 1, in progress):** per-test rows with material, O2, pressure, flow velocity, gravity and
   outcome, traced back to PSI record and report page.
2. **Model (Layer 1, in progress):** classifier for burn / extinguish plus an O2-limit estimate with an
   uncertainty interval; out-of-distribution flag outside the training envelope. Any gravity other than
   microgravity is always flagged OOD, because the training data contain no lunar or Mars tests.
3. **Map (Layer 2, in progress):** boundary curves per material and preset.
4. **Copilot (Layer 3, done):** Google Gemini with manual function calling over 6 tools (`predict`,
   `flammability_boundary`, `compare_scenarios`, `nearest_experiments`, `get_mission_preset`,
   `get_background_fact`). Guardrails are enforced in code, not only in the prompt: number grounding,
   input grounding (no invented flow values), OOD-first line, mock disclosure. Details:
   [`docs/copilot_design.md`](docs/copilot_design.md).

## Limits (honest)

- **No real model numbers yet.** Until `src/api.py` is connected, Copilot outputs are synthetic.
- **Small data.** Microgravity combustion tests are expensive, so each campaign has few tests. Intervals will
  be wide, and that is the honest answer.
- **No lunar or Mars data.** Any non-microgravity question is out of distribution and flagged as such.
- **Science claims are pending human verification** (`docs/science/claims_sheet.md`).
- The grounding check proves that a number exists in a tool result, not that the sentence around it is right.
- FlameMargin is decision support for exploring margins. It does not replace NASA-STD-6001B material testing.

## How to run

```bash
git clone https://github.com/badr5556/FlameMargin.git
```

```bash
cd FlameMargin
```

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate
```

(Windows: `.venv\Scripts\activate`)

```bash
pip install -r requirements.txt
```

Create a `.env` file (copy `.env.example`) and set your own key. Never commit it.

```bash
cp .env.example .env
```

Then edit `.env`: `GEMINI_API_KEY=<your key>`. Without a key, the Copilot runs in offline (rule-based) mode.

Run the Copilot UI (the `app.py` dashboard is not on `main` yet):

```bash
streamlit run src/copilot_ui.py
```

Run the tests and the evals:

```bash
python -m pytest -q tests/test_copilot.py
```

```bash
python evals/run_evals.py --mode fallback
```

## Repo structure

```
README.md                  this file
LICENSE                    MIT
requirements.txt           Python dependencies
.env.example               template for GEMINI_API_KEY / GEMINI_MODEL
main.py, combustion_sample.csv   early data-loading scratch (Layer 1 placeholder)
src/
  copilot.py               Copilot agent loop, guardrails, offline fallback
  copilot_tools.py         tool layer: unit parsing, presets, OOD rule, adapter to src/api.py or mock
  copilot_mock_api.py      SYNTHETIC placeholder for src/api.py (not NASA data)
  copilot_prompt.py        system prompt
  copilot_facts.py         sourced background facts (claim IDs, all unverified for now)
  copilot_ui.py            Streamlit chat UI
tests/test_copilot.py      unit tests (offline, faked LLM)
evals/                     adversarial question set, runner, results, transcripts
docs/
  copilot_design.md        Copilot architecture and guardrails
  copilot_integration.md   API contract for Layers 1 and 2
  data_sources.md          datasets, formats, licences
  science/claims_sheet.md  fact-check of every science claim
  pitch/                   pitch, demo script, slides outline, judge Q&A, video shot list, submission text
```

## AI-use disclosure

Space Apps asks teams to disclose AI use. We used:

- **Google Gemini (runtime):** the Copilot uses Gemini through the `google-genai` SDK to understand questions,
  choose tools and write answers (`src/copilot.py`). It produces no numbers of its own: code checks every
  number against tool results.
- **Claude Code (Anthropic) (development):** used by Omar to help write the Copilot code, tests and evals
  (`src/copilot*.py`, `tests/`, `evals/`), to run AI-assisted web searches for the fact-check
  (`docs/science/claims_sheet.md`, `docs/data_sources.md`), and to draft this README and the pitch material
  in `docs/pitch/`. All of it was directed and reviewed by the team; every science claim is listed with its
  source and verification status.
- No AI-generated images, video or voice are used as NASA data.

## NASA data attribution

This project uses data from NASA's Physical Sciences Informatics (PSI) system, including the BASS-II
investigation (PSI-25, DOI 10.60555/4qc4-de67), and results published on the NASA Technical Reports Server
(ntrs.nasa.gov). Sources for each science claim are in `docs/science/claims_sheet.md`. NASA does not endorse
this project.

## License

MIT, see [`LICENSE`](LICENSE). Copyright (c) 2026 IGNISPHERE.
