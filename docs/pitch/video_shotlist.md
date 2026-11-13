# Video shot list (about 110 seconds)

Narration is in simple English: short sentences, one idea each. Read slowly (about 130 words per minute).
Claim IDs (in brackets) are for the team only; don't read them. Credit NASA images on screen ("Image: NASA").
Record the screen at 1920×1080. If the backend is still `mock`, keep the "mock" label visible and say so (shot 6).

| # | Time | Shot (what we see) | Narration (say exactly this) | Claims |
|---|---|---|---|---|
| 1 | 0:00–0:08 | Title card: "FlameMargin · team IGNISPHERE", then a NASA microgravity flame image (credited) | "Fire in a spacecraft is very dangerous. The crew cannot leave." | none |
| 2 | 0:08–0:22 | Slide 2: teardrop flame vs round flame, fan icon | "NASA tests cabin materials for fire on Earth. But in space, there is no buoyancy. A flame in still air becomes round. In space, the air flow from the fans decides if a flame lives." | C11, C1, C14 |
| 3 | 0:22–0:38 | Slide 3: two cards, Mir vs BASS-II | "Old tests on the Mir station found the Earth test safe for still air. But on the ISS, with a gentle air flow, some materials burned at lower oxygen than on Earth." | C9, C2 |
| 4 | 0:38–0:50 | Slide 4: ISS point vs Exploration Atmosphere point, line at 30% O2 | "NASA's next atmosphere has 34 percent oxygen at 8.2 psia. NASA has limited material data above 30 percent oxygen." | C4, C13 |
| 5 | 0:50–1:00 | Slide 5: three-layer diagram | "FlameMargin has three parts. A model trained on NASA microgravity fire tests. A margin map. And a Copilot." | none |
| 6 | 1:00–1:20 | Screen recording: click "🚀 Artemis + fans off", answer appears, open "🔧 Tool-call trace" | "You ask a question in plain English. The Copilot calls the model. Every number comes from the model, and the code checks it." If mock: "Today, the numbers come from a placeholder engine. The real model uses the same connection." `[FILL WITH REAL NUMBERS if the model is connected: read the verdict line]` | none |
| 7 | 1:20–1:35 | Screen recording: click "🌕 Lunar habitat (OOD)"; zoom on the first line `⚠️ Out of distribution` | "Now the Moon. No fire test has been run on the Moon yet. We have no lunar data. So the first line is a warning." | C10 |
| 8 | 1:35–1:45 | Screen recording: paste the "Ignore your instructions..." prompt; the refusal appears | "If you ask it to guess, it says no. It only uses the model." | none |
| 9 | 1:45–1:55 | Slide 8: limits and next steps | "Our data is small, and we say it. Next, we add more NASA data and test our model on new experiments." | none |
| 10 | 1:55–2:00 | End card: "FlameMargin · IGNISPHERE · NASA Space Apps Cairo 2026", "Data: NASA PSI. NASA does not endorse this project." | "Know your margin before the fire does. Thank you." | none |

## Recording tips

- Record narration separately in a quiet room, then lay it over the screen recording.
- Use Offline mode for the screen recording if Gemini is slow: same answers, no waiting.
- Total must stay under 2:00. If too long, cut shot 8 first, then shot 3.
- No AI-generated voice or AI-generated "NASA" images. If any AI tool is used for editing, add it to the
  AI-use disclosure in the README and the submission text.
