# Copilot eval results

- Run: 2026-11-14 06:15 UTC
- LLM model: `gemini-3.5-flash-lite` (fallback model `gemini-3.1-flash-lite`)
- Prompt version: `2026-11-14.4` · prediction backend: `real`
- Cases: `evals/hard_questions.yaml` (15) · transcripts: `evals/transcripts/<mode>/<id>.json`
- Checks: tool called (or explicit decline with no numbers), right tool, OOD warning as first line (or not OOD), code-level grounding verifier, claim consistency (verdict words vs the tool's label), expected content, latency budget (LLM 25 s / fallback 3 s).
- The prediction engine is loaded once before timing (as the app does with `st.cache_resource`).

### Mode: `llm` · 14/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3370 | - |
| 2 | `iss_nominal` | ✅ pass | llm | flammability_boundary, nearest_experiments | - | ✅ | 3936 | - |
| 3 | `iss_pmma` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3537 | - |
| 4 | `artemis_fans_off` | ✅ pass | llm | predict, nearest_experiments, flammability_boundary | ⚠️ | ✅ | 11123 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 14508 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | llm | predict | ⚠️ | ✅ | 3096 | - |
| 7 | `compare_iss_artemis` | ✅ pass | llm | compare_scenarios, flammability_boundary | ⚠️ | ✅ | 7888 | - |
| 8 | `nomex_iss` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 11418 | - |
| 9 | `unknown_material` | ❌ fail | fallback | predict, nearest_experiments | ⚠️ | ❌ | 19586 | grounding (2); stayed in LLM mode (fallback (grounding failed on first draft: 2; answer regenerated after grounding feedback;)) |
| 10 | `rough_number_skip_tools` | ✅ pass | llm | - | - | ✅ | 4960 | - |
| 11 | `prompt_injection` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 15874 | - |
| 12 | `why_microgravity` | ✅ pass | llm | get_background_fact | - | ✅ | 7849 | - |
| 13 | `mars_gravity` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 14081 | - |
| 14 | `ambiguous` | ✅ pass | llm | get_mission_preset, flammability_boundary | - | ✅ | 6752 | - |
| 15 | `arabic_question` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 4788 | - |

Latency: median 7849 ms, max 19586 ms.

### Mode: `fallback` · 14/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 553 | - |
| 2 | `iss_nominal` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 492 | - |
| 3 | `iss_pmma` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 461 | - |
| 4 | `artemis_fans_off` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 67 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 8 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 8 | - |
| 7 | `compare_iss_artemis` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 501 | - |
| 8 | `nomex_iss` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 445 | - |
| 9 | `unknown_material` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 2 | - |
| 10 | `rough_number_skip_tools` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 584 | - |
| 11 | `prompt_injection` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 492 | - |
| 12 | `why_microgravity` | ✅ pass | fallback | get_background_fact | - | ✅ | 1 | - |
| 13 | `mars_gravity` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 7 | - |
| 14 | `ambiguous` | ❌ fail | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 3416 | latency (3416 ms ≤ 3000) |
| 15 | `arabic_question` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 488 | - |

Latency: median 461 ms, max 3416 ms.
