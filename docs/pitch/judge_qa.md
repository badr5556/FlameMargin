# Judge Q&A: the 15 hardest questions

Short, honest answers. Claim IDs refer to `docs/science/claims_sheet.md`; numbers come from `models/metrics_v2.json`,
`docs/model_card.md` and `evals/results.md`. Rule: if the true answer is "we don't know", say that first.

### 1. How much data did you train on?
All 126 BASS-II tests in NASA/TM-20210011385 Appendix A (Tables A.1–A.6), plus the PI summary tables 7.1 and 5.1 (ISS, 1 atm).
Written rules turn the crew's observations into **192 training points from 85 tests: 166 burn, 26 extinguished**, for five
materials (SIBAL fabric, PMMA film, PMMA slab, PMMA rod, Nomex). Every point carries a verbatim quote and its page. 23 more
points (reused samples, spherical sections, NASA-flagged O2) are shown on the map but not used. [D1]

### 2. Are the numbers in your demo real model outputs?
Yes. Every number comes from `src/api.py`, the model trained on those 192 points, and code checks that every number in a
Copilot answer exists in a tool result. The old placeholder engine is now only a unit-test fixture.

### 3. How good is the model?
Leave-one-test-out (all points of a test held out together): Brier **0.087** for the shipped v2.1 vs **0.118** for the
baseline, a Brier skill of **+26%**; log-loss 0.320 vs 0.401; AUC 0.80. On SIBAL's own 21 v1 points it is still worse than v1
(0.258 vs 0.229), and we say so. v2.1 was one pre-registered fix for that (per-material flow terms); it tied v2 overall. It's a proof of pipeline on real NASA data, not a flight-qualification tool.

### 4. Why is accuracy 0.89 for the model and 0.865 for the baseline?
Because 86% of the points are burns, so "always burn" is already 0.865 accurate. That's why we pick models by Brier and
log-loss and also report AUC (0.80 vs 0.06; the baseline's AUC is degenerate, see the model card footnote). It's explained in the model card.

### 5. Is the ISS cabin (21% oxygen) covered?
Now yes, for four of the five materials. The report says two SIBAL tests at 21% O2 reached steady spread (GMT96-T7 and -T8,
p. 95), and PMMA films and slabs were tested at 21–22.2%. PMMA rods were tested only up to 20.8%, so ISS air is out of
distribution for rods. In v1, with 31 rows, ISS was an extrapolation.

### 6. What happens outside your data?
Hard rules first: a material not in the five, pressure outside 14.7 ± 0.3 psia, gravity other than microgravity, a flow
configuration never tested for that material, or O2 / flow / thickness / size outside that material's tested ranges. Any of
them → **no number**, with a reason for each. Then a nearest-neighbour distance
check flags extrapolations inside those ranges. In the Copilot, code forces the warning onto the first line.

### 7. So Artemis is out of distribution?
Yes, for every material, on both pressure (8.2 psia) and oxygen (34%). [C4] That's our key honest finding: none of the 126
BASS-II tests reaches the Exploration Atmosphere, which matches the 2026 NESC finding that material flammability is the most
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
On oxygen, yes: P(burn) never falls as oxygen rises at fixed flow (0 of 18 checked curves). Where it doesn't: it cannot bend
into SIBAL's low-flow quenching branch (it says 0.71 at 18.7% O2 and 2.2 cm/s, where GMT45-T4 quenched; v2 said 0.78). It's in the model
card and tested.

### 12. Do you predict flame spread rate?
Only for PMMA slabs: Table 5.1 gives 39 measured spread rates from 18 tests. A simple log-linear model beats a baseline
(leave-one-test-out RMSE 0.175 vs 0.269 log10 units). Other materials have spread rates only in figures, which we don't digitize.

### 13. Where do your science facts come from?
Every claim has an ID, an exact wording, a primary source and a status in the claims sheet. Ten are verified against the
primary abstract or PDF and one was corrected because it was too strong (C10); four science claims are still pending and the
Copilot says so when it cites them. Our own data claim (D1) is verified: all 126 rows checked against the PDF, a 20%
re-check with a second extractor passed 26/26, and the SIBAL rows match Zhao et al. 2015 for 31/31.

### 14. Did you use AI to build this?
Yes, disclosed in the README: the team designed the system and its safety rules, extracted the data and verified the sources;
AI assistants helped implement, test and draft documentation; Gemini is the runtime LLM and never produces numbers itself.

### 15. What would you do with three more months?
1. Give each material its own flow terms (SIBAL's quenching branch) and re-validate. 2. Read the spread-rate figures with
the PIs' raw data instead of digitizing them. 3. Add pressure as a feature once data at other pressures exist. 4. Add FM2 lunar data when it exists. [C10]
5. Ask a NASA fire-safety engineer to review the outputs.

---

### 16. Your own map shows NASA "extinguished" points inside the orange zone. Doesn't your model contradict NASA?
On some points, yes, and we show them instead of hiding them. Of the 26 extinguished NASA points, the final model gives only 7 a
P(burn) below 0.5 (6 when each test is held out), and 3 of those 7 are the Nomex tests it simply repeats. Of the other 19,
10 sit just above the line (P 0.5–0.65), among them 6 SIBAL quenches at 2.2–5 cm/s: the low-flow quench edge is where the
model is weakest. A few PMMA slab extinctions at 19–21.6% O2 get P(burn) above 0.75: oxygen, flow and thickness alone do not
explain them. (Recompute: `api.get_engine()` scored on its own training points.) We pre-registered one physics-motivated fix before fitting it (v2.1:
per-material flow terms for SIBAL and PMMA slab), with a ship rule written in advance. It tied v2 on Brier (0.087) and shipped
by that rule, but it moved none of those points below 0.5, and we report that (model card section 5b). The model is a
conservative screen: at the 0.5 line it misses 1 of 166 NASA burns, and the price is that it rarely says "won't burn".

### 17. Isn't your accuracy high only because 86% of the points are burns?
Yes, accuracy alone would be meaningless: "always burn" scores 0.865. That's why we never headline accuracy. The header shows
leave-one-test-out AUC 0.80 (ranking burns above extinctions on tests the model never saw) and a Brier skill of +26% over that
"always the burn rate" baseline (1 − 0.087 / 0.118, computed from `models/metrics_v2.json`). We also report balanced accuracy
(0.612), log-loss, per-material scores, a reliability plot, and the safety operating point: burn recall 0.994 at the 0.5 line.

### 18. Nomex scores almost perfectly. Isn't that just memorised?
Yes, and we say so. Nomex has only 3 tests (F1, F2, F3), all non-sustained, so the model can only repeat them: its tiny Brier
(0.001) is not evidence of skill. That's why Nomex is in distribution only near those 3 tests (21–22.2% O2, 8–15 cm/s
concurrent), every Nomex answer carries the note that all its tests failed to sustain a flame, and the leave-one-material-out
stress test shows the honest picture: without Nomex data the model calls Nomex flammable (Brier 0.996). [D3]

## Our known weaknesses (say them before a judge does)
| Weakness | How we handle it |
|---|---|
| 192 points, five materials, one pressure | Leave-one-test-out metrics next to a baseline; per-material OOD rules; nearest NASA tests (with quote and page) shown with every answer |
| One-sided labels: PMMA film all burns, Nomex 3 non-sustained tests | Said in every answer for those materials; the model only repeats those tests |
| The engine is worse than v1 on SIBAL's own points (v2.1 0.258, v2 0.269, v1 0.229) | Reported in the model card and README; the pre-registered per-material flow fix (v2.1) narrowed it, did not close it |
| 55 of 192 points are medium-confidence | Labelled per point; a high-confidence-only run is reported (Brier 0.116 vs 0.109) |
| No fans-off flow value | Not invented; slider labelled "Fans OFF / near-quiescent" with verified context only (C3, C8b) |
