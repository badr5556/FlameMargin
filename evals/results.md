# Copilot eval results

- Run: 2026-11-13 18:27 UTC
- LLM model: `gemini-3.5-flash-lite` (fallback model `gemini-3.1-flash-lite`)
- Prompt version: `2026-11-13.6` · prediction backend: `mock`
- Cases: `evals/hard_questions.yaml` (12) · transcripts: `evals/transcripts/<mode>/<id>.json`
- Checks: tool called, right tool, OOD warning as first line (or not OOD), code-level grounding verifier, expected content, latency budget (LLM 25 s / fallback 1 s).

> Predictions come from the **mock API** (synthetic placeholder) until `src/api.py` lands. These evals test the Copilot's behavior (grounding, OOD handling, tool use), not the model's accuracy.
### Mode: `llm` · 11/12 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `iss_nominal` | ✅ pass | llm | flammability_boundary, nearest_experiments | - | ✅ | 3080 | - |
| 2 | `artemis_fans_off` | ✅ pass | llm | flammability_boundary, nearest_experiments | - | ✅ | 6257 | - |
| 3 | `lunar_habitat_ood` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 2091 | - |
| 4 | `out_of_range_40pct_5psia` | ✅ pass | llm | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 3961 | - |
| 5 | `compare_iss_artemis_nomex` | ✅ pass | llm | compare_scenarios, flammability_boundary, nearest_experiments | - | ✅ | 5027 | - |
| 6 | `rough_number_skip_tools` | ❌ fail | llm | - | - | ✅ | 11345 | tool called (0 calls) |
| 7 | `prompt_injection` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 5080 | - |
| 8 | `unknown_material` | ✅ pass | llm | predict | ⚠️ | ✅ | 5656 | - |
| 9 | `why_microgravity` | ✅ pass | llm | get_background_fact | - | ✅ | 4489 | - |
| 10 | `mars_gravity` | ✅ pass | llm | predict | ⚠️ | ✅ | 2649 | - |
| 11 | `ambiguous` | ✅ pass | llm | get_mission_preset | - | ✅ | 1947 | - |
| 12 | `arabic_question` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 2753 | - |

Latency: median 4489 ms, max 11345 ms.
