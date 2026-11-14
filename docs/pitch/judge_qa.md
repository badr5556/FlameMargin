# Judge Q&A: the 15 hardest questions

Short, honest answers. Claim IDs refer to `docs/science/claims_sheet.md`; numbers come from `models/metrics.json`,
`docs/model_card.md` and `evals/results.md`. Rule: if the true answer is "we don't know", say that first.

### 1. How much data did you train on?
31 SIBAL cotton-fiberglass fabric tests from NASA/TM-20210011385 Table 7.1 (BASS-II, ISS, 1 atm). Each test ramps the
flow at fixed oxygen, so four written rules turn the 12 tests with a definitive outcome into **21 observations: 11 burn,
10 extinguished**. The other 19 rows (8 reused samples, 11 without a reported outcome) are shown on the map in grey but not used.

### 2. Are the numbers in your demo real model outputs?
Yes. Every number comes from `src/api.py`, the model trained on those 21 points, and code checks that every number in a
Copilot answer exists in a tool result. The old placeholder engine is now only a unit-test fixture.

### 3. How good is the model?
Leave-one-test-out (both points of a test held out together): Brier **0.229** for the Gaussian process vs **0.263** for a
majority-class baseline; balanced accuracy 0.668 vs 0.318; log-loss 0.651 vs 0.719. That is a modest gain, and we say so:
two-thirds of its out-of-fold predictions are between 0.4 and 0.6. It's a proof of pipeline on real NASA data, not a
flight-qualification tool.

### 4. Why is the baseline's accuracy only 0.333, below a coin flip?
Leave-one-out artefact: when you hold out a test, the training majority shifts against that test's own points. That's why
we pick models by Brier and log-loss, where the baseline sits near a coin flip. It's explained in the model card.

### 5. Your ISS preset says "extrapolation". Isn't 21% oxygen normal?
It is normal for the ISS, but in the extraction none of the 21% O2 tests reports a definitive outcome; the highest labelled
oxygen is 18.7%. So the distance check flags 21% as far from labelled data and the interval becomes 0 to 1. We'd rather
say "no information" than borrow confidence. If the PDF shows outcomes for those rows, adding them fixes it.

### 6. What happens outside your data?
Hard rules first: material other than SIBAL, pressure outside 14.7 ± 0.3 psia, gravity other than microgravity, O2 outside
16.4–21%, flow outside 2–53 cm/s. Any of them → **no number**, with a reason for each. Then a nearest-neighbour distance
check flags extrapolations inside those ranges. In the Copilot, code forces the warning onto the first line.

### 7. So Artemis is out of distribution?
Yes, on both pressure (8.2 psia) and oxygen (34%). [C4] That's our key honest finding: NASA's microgravity data in this
dataset don't reach the Exploration Atmosphere, which matches the 2026 NESC finding that material flammability is the most
critical hurdle there. [C6]

### 8. What about the Moon?
Also out of distribution. SIBAL, which extinguishes immediately in Earth gravity, burned downward at lunar gravity in
centrifuge and parabolic-flight tests [C7], and no long-duration fire experiment has been done in actual lunar gravity;
NASA's FM2 will be the first. [C10] That's the first data we would add.

### 9. LLMs hallucinate. Why trust the Copilot?
We don't trust the LLM; the code does the checking. Every number and NASA test ID must exist in a tool result; verdict words
must match the model's label; out-of-distribution warnings go first; the LLM may not invent a flow (in one eval it tried to
assume 10 cm/s and was rejected). If a draft fails twice, the user sees deterministic tool outputs instead.

### 10. What if Gemini is down or rate-limited on a public link?
Primary key, then a backup key, then a backup model, then a deterministic fallback with the same tools and template. Each
browser session gets 15 LLM questions, then the fallback. Final eval run: LLM 13/14, fallback 14/14 (the LLM "failure" was
the guard blocking a citation the model took from its prompt instead of a tool).

### 11. Does your model respect physics?
Partly, and we report where it doesn't: P(burn) should not fall as oxygen rises at fixed flow. The shipped model has a small
dip near 17.5% and falls back toward 0.5 above 18.7%, because a Gaussian process reverts to its prior far from data. The
logistic model is monotone but scored worse. It's in the model card and tested.

### 12. Why do you not predict flame spread rate?
The extraction has no spread-rate values, so we don't. The regression dataset is an empty schema on purpose.

### 13. Where do your science facts come from?
Every claim has an ID, an exact wording, a primary source and a status in the claims sheet. Ten are verified against the
primary abstract or PDF and one was corrected because it was too strong (C10); four science claims are still pending and the
Copilot says so when it cites them. Our own data claim (D1) stays pending until the 31-row check is done.

### 14. Did you use AI to build this?
Yes, disclosed in the README: the team designed the system and its safety rules, extracted the data and verified the sources;
AI assistants helped implement, test and draft documentation; Gemini is the runtime LLM and never produces numbers itself.

### 15. What would you do with three more months?
1. Finish the 31-row verification and add the other BASS-II tables (PMMA, more velocities). 2. Bound the GP length scale and
re-validate. 3. Add pressure as a feature once data at other pressures exist. 4. Add FM2 lunar data when it exists. [C10]
5. Ask a NASA fire-safety engineer to review the outputs.

---

## Our known weaknesses (say them before a judge does)
| Weakness | How we handle it |
|---|---|
| 21 points, one material, one pressure | Leave-one-test-out metrics next to a baseline; hard OOD rules; nearest NASA tests shown with every answer |
| Extraction not yet verified row by row | 31-row checklist for two teammates; claim D1 stays PENDING until done |
| ISS 21% O2 has no labelled outcome | Flagged as extrapolation with a [0, 1] interval and label "uncertain" |
| GP intervals often touch 0.5 (37% of bootstrap fits collapse) | Reported in the model card; bounded length scale is the next step |
| No fans-off flow value | Not invented; slider labelled "Fans OFF / near-quiescent" with verified context only (C3, C8b) |
