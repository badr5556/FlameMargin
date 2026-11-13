# Space Apps project page text (ready to paste)

Before pasting: replace every `[FILL ...]`, and delete any sentence whose claim was marked `WRONG` in
`docs/science/claims_sheet.md`. Claim IDs in brackets are for the team; remove them before pasting.

---

## Project name
FlameMargin

## High-level summary (short)

FlameMargin shows how close a spacecraft cabin material is to burning, in a given oxygen level, pressure, air
flow and gravity. NASA screens materials with an upward flame test on Earth [C11], but in microgravity there
is no buoyancy and the air flow decides whether a flame survives [C1, C14]. FlameMargin learns from NASA
microgravity combustion experiments, maps each material's margin to burning, and adds a Fire Safety Copilot
that answers operator questions only from the model's outputs and warns first when a question is outside the
data, such as lunar gravity.

## What it does

- **Prediction engine (Layer 1):** for a material, O2 %, pressure and air flow, predicts burn or extinguish,
  a limiting O2 with an uncertainty interval, and the nearest real NASA experiments. Inputs outside the
  training data are flagged out of distribution. `[Status: integration in progress]`
- **Margin map (Layer 2):** the O2 limit versus air flow for each material, with mission presets for the ISS
  cabin, NASA's recommended Exploration Atmosphere (8.2 psia, 34% O2) [C4], and a lunar habitat.
  `[Status: integration in progress]`
- **Fire Safety Copilot (Layer 3):** an LLM agent (English and Arabic) that can only answer through the
  prediction tools. Code, not just the prompt, checks that every number in an answer exists in a tool result,
  puts out-of-distribution warnings on the first line, refuses to invent missing inputs, and falls back to a
  deterministic mode if the LLM is unavailable.

## Why it matters

In the BASS-II experiments on the ISS, with a gentle air flow, some materials kept burning at lower oxygen than
their limits measured on Earth [C2], while older Mir tests found the Earth test conservative for still air
[C9]. NASA's recommended Exploration Atmosphere uses 34% oxygen at 8.2 psia [C4], and NASA reports limited
material flammability data above 30% oxygen [C13]. No fire test has been run on the Moon yet [C10]. Engineers
need a fast way to see where the margins are thin and where the data run out.

## How we built it

- Python, Streamlit, pandas `[FILL: ML library used by Layer 1]`.
- Data: NASA Physical Sciences Informatics (BASS-II, PSI-25) and published NASA results (see attribution).
- Copilot: Google Gemini via the `google-genai` SDK with manual function calling over 6 tools; grounding,
  input-grounding and OOD guards in code; 67 unit tests; a 12-question adversarial eval (prompt injection,
  lunar and Mars OOD, out-of-range inputs, unknown material, Arabic) passing 12/12 in LLM and offline modes.
- Science: every claim we use is listed in a claims sheet with its NASA source and verification status.

## Challenges

- **Small, heterogeneous data:** microgravity tests are rare and spread across reports, videos and sensor
  logs, not one clean table.
- **Integrating three layers during the hackathon:** we defined a fixed API contract first, so the Copilot could be
  built and tested against a clearly labelled placeholder engine while the model was being trained.
- **Honesty under pressure:** we dropped claims we could not trace to a source, and we label every placeholder
  number as "mock".
- **LLM reliability:** we enforced the rules in code and built an offline fallback for rate limits.

## What's next

1. Load all relevant PSI campaigns (BASS, BASS-II, Saffire) with traceable test IDs.
2. Validate on held-out experiments and publish calibration.
3. Add lunar-gravity data when NASA's FM2 experiment flies [C10].
4. Review the outputs with a spacecraft fire-safety expert.

## Space Agency data used (attribution)

- NASA Physical Sciences Informatics (PSI): BASS-II investigation, PSI-25, DOI 10.60555/4qc4-de67.
  https://psi.nasa.gov/physci/repo/data/investigations/PSI-25
- NASA Technical Reports Server (ntrs.nasa.gov): BASS-II Summary Report NASA/TM-20210011385; SIBAL fabric
  results NTRS 20150008962; Saffire results ICES-2017-224 (NTRS 20170008805); Exploration Atmosphere
  NTRS 20240003211; NESC assessment NASA/TM-20260003925; lunar and Martian gravity flammability, LPSC 2026
  (NTRS 20260000646).
- NASA-STD-6001B, Test 1 (Upward Flame Propagation).
- NASA Scientific Visualization Studio, "NASA Studies Fire in Microgravity" (SVS 31394).
- `[FILL: any other dataset Layer 1 actually used]`

NASA does not endorse this project.

## Use of Artificial Intelligence

- **Google Gemini** runs the Copilot at runtime: it interprets questions, chooses tools and writes answers.
  It generates no numbers of its own; code checks every number against the prediction tools.
- **Claude Code (Anthropic)** was used during development to help write the Copilot code, tests and
  evaluation suite, to run AI-assisted web searches for our science fact-check and data-source survey, and to
  draft the README and pitch text. The team directed and reviewed all of it.
- No AI-generated images, video or voices are presented as NASA data. `[FILL: add any other AI tool the team used]`

## Team
IGNISPHERE, NASA Space Apps Cairo 2026. `[FILL: names and roles]`

## Links
- Repository: https://github.com/badr5556/FlameMargin
- Demo video: `[FILL]`
