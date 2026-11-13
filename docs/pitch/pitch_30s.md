# 30-second pitch

Rules for this file: only claims from `docs/science/claims_sheet.md`, in their **safe wording**. Claim IDs are
in brackets for the team; do not read them aloud. All claims are still `NOT VERIFIED` until someone opens the
sources (see the sheet). If a claim gets marked `WRONG`, delete its sentence here.

## 30 seconds (about 80 words, slow pace)

> Before a material flies to the ISS, NASA tests it for fire **on Earth**, in normal gravity. [C11]
> But in space there is no buoyancy, so the **air flow** decides if a flame lives or dies. [C1, C14]
> On the ISS, some materials kept burning at **lower oxygen** than their Earth limits. [C2]
> And NASA's next atmosphere, **34% oxygen at 8.2 psia**, is above most of the material data NASA has. [C4, C13]
> FlameMargin learns from NASA's microgravity fire experiments and shows each material's **margin to burning**.
> Our Copilot answers only from the model, and it says **"no data"** when we have none, like on the Moon. [C10]

## 10 seconds

> Space materials are fire-tested on Earth, but in space the air flow decides if a fire lives. [C11, C14]
> FlameMargin turns NASA's microgravity fire data into a margin-to-burning map, with a Copilot that never invents numbers.

## Words to avoid on stage

| Don't say | Why | Say instead |
|---|---|---|
| "Turning off the fans may not stop the fire" | No source found (C2, unsupported part) | "Low air flow can still keep a flame alive." (C9 extract: very low flows sustained burning on Mir) |
| "70% of systems need new materials" | Number not traceable (C6) | "NASA has limited flammability data above 30% oxygen." (C13) |
| "There is no lunar fire data at all" | Too strong: short partial-gravity tests exist (C10) | "No fire test has been run on the Moon yet." |
| "NASA says the Earth test is wrong" | Mir data say it was conservative for some plastics (C9) | "The Earth test looks safe for still air, but not always for moving air." (C14, team synthesis) |
| "Our model predicts..." (before `src/api.py` is connected) | Numbers are mock | "This is our placeholder engine; the real model plugs into the same interface." |
| "Verified by NASA" | Nothing is verified yet, and NASA does not endorse us | "Sourced from NASA papers; see our claims sheet." |
