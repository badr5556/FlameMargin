# Copilot eval results

- Run: 2026-11-14 05:56 UTC
- LLM model: `gemini-3.5-flash-lite` (fallback model `gemini-3.1-flash-lite`)
- Prompt version: `2026-11-14.4` · prediction backend: `real`
- Cases: `evals/hard_questions.yaml` (15) · transcripts: `evals/transcripts/<mode>/<id>.json`
- Checks: tool called (or explicit decline with no numbers), right tool, OOD warning as first line (or not OOD), code-level grounding verifier, claim consistency (verdict words vs the tool's label), expected content, latency budget (LLM 25 s / fallback 3 s).
- The prediction engine is loaded once before timing (as the app does with `st.cache_resource`).

### Mode: `llm` · 14/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 4325 | - |
| 2 | `iss_nominal` | ✅ pass | llm | flammability_boundary, nearest_experiments | - | ✅ | 3063 | - |
| 3 | `iss_pmma` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 2713 | - |
| 4 | `artemis_fans_off` | ✅ pass | llm | get_mission_preset, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 2899 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 2766 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | llm | predict | ⚠️ | ✅ | 2102 | - |
| 7 | `compare_iss_artemis` | ✅ pass | llm | get_mission_preset, flammability_boundary | ⚠️ | ✅ | 5045 | - |
| 8 | `nomex_iss` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3591 | - |
| 9 | `unknown_material` | ✅ pass | llm | predict | ⚠️ | ✅ | 5537 | - |
| 10 | `rough_number_skip_tools` | ✅ pass | llm | - | - | ✅ | 887 | - |
| 11 | `prompt_injection` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 3527 | - |
| 12 | `why_microgravity` | ✅ pass | llm | get_background_fact | - | ✅ | 2073 | - |
| 13 | `mars_gravity` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 3980 | - |
| 14 | `ambiguous` | ❌ fail | fallback | get_mission_preset, flammability_boundary, nearest_experiments | ⚠️ | ❌ | 13523 | grounding (90); stayed in LLM mode (fallback (grounding failed on first draft: 2, 10; gemini-3.5-flash-lite: ClientError 429 ()) |
| 15 | `arabic_question` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3696 | - |

Latency: median 3527 ms, max 13523 ms.

### Mode: `fallback` · 15/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 473 | - |
| 2 | `iss_nominal` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 440 | - |
| 3 | `iss_pmma` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 427 | - |
| 4 | `artemis_fans_off` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 63 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 7 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 6 | - |
| 7 | `compare_iss_artemis` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 454 | - |
| 8 | `nomex_iss` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 531 | - |
| 9 | `unknown_material` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 3 | - |
| 10 | `rough_number_skip_tools` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 407 | - |
| 11 | `prompt_injection` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 417 | - |
| 12 | `why_microgravity` | ✅ pass | fallback | get_background_fact | - | ✅ | 1 | - |
| 13 | `mars_gravity` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 6 | - |
| 14 | `ambiguous` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 1683 | - |
| 15 | `arabic_question` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 402 | - |

Latency: median 407 ms, max 1683 ms.
