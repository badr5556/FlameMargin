# 30-second pitch

Rules: only claims marked VERIFIED or CORRECTED in `docs/science/claims_sheet.md`, in their exact wording or weaker.
Claim IDs in brackets are for the team; do not read them aloud. Every number below is in `models/metrics.json`,
the claims sheet, or the live app.

## 30 seconds (about 85 words, slow pace)

> NASA screens spacecraft materials for fire in normal Earth gravity. [C11]
> But BASS-II tests on the ISS showed materials can burn at **lower oxygen in microgravity**. [C2]
> NASA's next cabin air, **34% oxygen at 8.2 psia**, is an atmosphere of increased burning rate. [C4, C5]
> FlameMargin turns NASA's own ISS fire tests into a **live flammability map** with honest uncertainty.
> And it tells you when NASA's data **don't cover** your cabin: today, that includes Artemis.
> That is the hurdle NASA's 2026 NESC study calls most critical. [C6]

## 10 seconds

> FlameMargin turns NASA's microgravity fire tests into a flammability map, and it says "no data" for the Artemis
> atmosphere instead of guessing. [C4, C6]

## Words to avoid on stage

| Don't say | Why | Say instead |
|---|---|---|
| "Turning off the fans may not stop the fire" | No source supports it (deleted from C2) | "Our data don't measure the residual flow with fans off, so we don't guess." |
| "There is no lunar fire data at all" | Wrong: short partial-gravity tests exist (C7, C10) | "No long-duration fire experiment has been done in actual lunar gravity; FM2 will be the first." [C10] |
| "Our model is accurate" / "validated" | 21 points; Brier 0.229 vs 0.263 baseline | "It beats a baseline modestly, and it tells you where it knows nothing." |
| "It predicts flame spread rate" | No spread-rate data in the extraction | "It predicts the probability that a flame is sustained." |
| "Verified by NASA" / "NASA-approved" | NASA does not endorse us; extraction pending row verification (D1) | "Built on NASA's BASS-II report, Table 7.1." |
| Any single "fans-off" airflow number | Not in our data; C8b is typical circulation, not fans-off | "Typical spacecraft air circulation is about 20–25 cm/s." [C8b] |
