# Judge Q&A: the 15 hardest questions

Short, honest answers. Claim IDs refer to `docs/science/claims_sheet.md`. Rule: if the true answer is "we don't
know yet", say that first, then say what we did about it.

### 1. How much data did you train on?
Honest answer: small. Microgravity fire tests are expensive, so each NASA campaign has few tests. That is
exactly why our model reports intervals and an out-of-distribution flag instead of a single number.
`[FILL WITH REAL NUMBERS: rows used, campaigns, materials, once Layer 1 is merged]`

### 2. Are the numbers in your demo real model outputs?
`[Pick the line that is true on demo day]`
- If `src/api.py` is connected: "Yes, from the model trained on [dataset]. Every number in an answer is checked
  in code against a tool result."
- If not: "No. Today the Copilot runs on a placeholder engine (`copilot_mock_api.py`), and every answer says
  'mock' on screen. The real model plugs into the same interface without changing the Copilot."

### 3. How do you know the model is right? (validity)
`[FILL: held-out accuracy / calibration once Layer 1 reports it]`. Until then, we do not claim accuracy. What
we can show today is that the **Copilot** behaves correctly: 12 adversarial questions (OOD, prompt injection,
unknown material, Arabic, "skip the tools") pass 12/12 in both LLM and offline modes (`evals/results.md`).

### 4. Why not just use NASA's Earth test (NASA-STD-6001B Test 1)?
We don't replace it; it is the certification test. [C11] But it is run in normal gravity, and the evidence
shows the answer depends on air flow: older Mir tests found it conservative for still air [C9], while
BASS-II found materials burning below their Earth limits with gentle ventilation [C2]. FlameMargin helps
explore the flow-dependent margin between tests. Decision support, not certification.

### 5. Isn't the Earth test conservative? I've read Mir results saying so.
Yes, for the plastics tested in still or very slow air on Mir. [C9] We list that as counter-evidence in our
own fact base. Our reading of both results together: conservative for still air, not always for ventilated
microgravity. [C14] That's why flow velocity is an input.

### 6. What happens outside your training data?
The tool layer flags it, and code forces the warning to be the first line of the answer. Inputs are not
clamped: a 40% O2 / 5 psia question is answered with an OOD warning, not silently moved into range. Physically
impossible inputs are rejected.

### 7. What about the Moon? Artemis is going there.
No fire test has been run on the Moon yet. [C10] Short partial-gravity tests suggest some materials can burn
in lunar gravity that don't burn in 1 g [C7], so we refuse to extrapolate quietly: any gravity other than
microgravity is always flagged OOD, by a hard rule in code. When NASA's FM2 experiment flies, that data is the
first thing we would add.

### 8. LLMs hallucinate. Why should an astronaut trust your Copilot?
They shouldn't trust the LLM, and the design assumes that. The LLM never produces numbers: it calls tools.
Code then checks every number in the draft against the tool results; if one doesn't match, the answer is
regenerated once, and if it still fails, the Copilot shows the raw tool outputs instead. It also refuses
"ignore your instructions" requests (we test that).

### 9. What if Gemini is down or rate-limited?
Retry once, then a smaller model, then a deterministic rule-based fallback that calls the same tools and uses
the same answer template. There's also an "Offline mode" switch. Fallback answers in milliseconds.

### 10. Your grounding check proves the number exists. Does it prove the sentence is right?
No, and we say so in our design doc. A number could be quoted out of context. Mitigation: comparisons and
limits are computed in code and passed to the LLM as finished results, so it has nothing to calculate.

### 11. What is actually novel here?
Three things together: (1) a model that treats **flow velocity** and **gravity** as first-class inputs, which
is where microgravity differs from the Earth test; (2) honest uncertainty and OOD flags instead of a single
yes/no; (3) a Copilot whose guardrails are enforced in code, not just in a prompt. We don't claim new
combustion science.

### 12. Where do your science facts come from, and did you check them?
Every claim is in a claims sheet with its NASA source and status. We were strict: anything we could not open
ourselves is marked "not verified", and we corrected claims that were stronger than the source (for example,
we dropped a "70% of systems" number we could not trace). [C6]

### 13. Who did what on the team?
`[FILL: names]` Layer 1 data and model: teammate A. Layer 2 map / dashboard: teammate B. Layer 3 Copilot,
science fact-check and pitch: Omar. `[Add the others.]`

### 14. Did you use AI to build this?
Yes, disclosed in the README: Gemini runs the Copilot at runtime; Claude Code helped write the Copilot code,
tests and docs, and ran the web searches for the fact-check. The team directed and reviewed everything.

### 15. What would you do with three more months?
1. Load all relevant PSI campaigns (BASS, BASS-II, Saffire) with traceable test IDs. 2. Validate on held-out
tests and publish calibration. 3. Add pressure-dependent physics features. 4. Add lunar data from FM2 when it
exists. [C10] 5. Get a NASA fire-safety engineer to review the outputs.

---

## Our known weaknesses (say them before a judge does)

| Weakness | How we handle it |
|---|---|
| Small dataset | Intervals + OOD flag + nearest real experiments shown with each answer |
| Mock numbers until Layer 1 is merged | Labelled "mock" in every answer and in the UI; same interface for the real model |
| No lunar / Mars data | Hard OOD rule in code; never a silent extrapolation |
| Science claims not yet verified by opening primary sources | Claims sheet with status per claim; safe wording only |
| "Fans off" has no agreed flow value | The Copilot refuses to invent one and answers from the low-flow boundary |
