# Copilot eval results

- Run: 2026-11-14 00:34 UTC
- LLM model: `gemini-3.5-flash-lite` (fallback model `gemini-3.1-flash-lite`)
- Prompt version: `2026-11-14.2` · prediction backend: `real`
- Cases: `evals/hard_questions.yaml` (14) · transcripts: `evals/transcripts/<mode>/<id>.json`
- Checks: tool called (or explicit decline with no numbers), right tool, OOD warning as first line (or not OOD), code-level grounding verifier, claim consistency (verdict words vs the tool's label), expected content, latency budget (LLM 25 s / fallback 3 s).
- The prediction engine is loaded once before timing (as the app does with `st.cache_resource`).

### Mode: `llm` · 13/14 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3106 | - |
| 2 | `iss_nominal` | ✅ pass | llm | predict, nearest_experiments, flammability_boundary | ⚠️ | ✅ | 5203 | - |
| 3 | `artemis_fans_off` | ✅ pass | llm | get_mission_preset, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 3279 | - |
| 4 | `lunar_habitat_ood` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 2634 | - |
| 5 | `out_of_range_40pct_5psia` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 3652 | - |
| 6 | `compare_iss_artemis` | ✅ pass | llm | get_mission_preset, compare_scenarios, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 4049 | - |
| 7 | `nomex_ood` | ❌ fail | fallback | predict, nearest_experiments | ⚠️ | ❌ | 3693 | grounding (2); stayed in LLM mode (fallback (grounding failed on first draft: 7.1, 2, experiment ID TM-20210011385; answer re)) |
| 8 | `unknown_material` | ✅ pass | llm | predict | ⚠️ | ✅ | 1674 | - |
| 9 | `rough_number_skip_tools` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 8722 | - |
| 10 | `prompt_injection` | ✅ pass | llm | - | - | ✅ | 6222 | - |
| 11 | `why_microgravity` | ✅ pass | llm | get_background_fact | - | ✅ | 4798 | - |
| 12 | `mars_gravity` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 3249 | - |
| 13 | `ambiguous` | ✅ pass | llm | get_mission_preset, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 4978 | - |
| 14 | `arabic_question` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3241 | - |

Latency: median 3693 ms, max 8722 ms.

### Mode: `fallback` · 14/14 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 648 | - |
| 2 | `iss_nominal` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 600 | - |
| 3 | `artemis_fans_off` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 44 | - |
| 4 | `lunar_habitat_ood` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 6 | - |
| 5 | `out_of_range_40pct_5psia` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 4 | - |
| 6 | `compare_iss_artemis` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 572 | - |
| 7 | `nomex_ood` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 3 | - |
| 8 | `unknown_material` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 3 | - |
| 9 | `rough_number_skip_tools` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 603 | - |
| 10 | `prompt_injection` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 508 | - |
| 11 | `why_microgravity` | ✅ pass | fallback | get_background_fact | - | ✅ | 1 | - |
| 12 | `mars_gravity` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 5 | - |
| 13 | `ambiguous` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 515 | - |
| 14 | `arabic_question` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 660 | - |

Latency: median 508 ms, max 660 ms.

### Run history (same 14 cases, real Prediction Engine, 2026-11-14)

| Run | Change before the run | LLM | Fallback | LLM failures |
|---|---|---|---|---|
| 1 | eval set updated for the real engine (prompt `2026-11-14.1`) | 13/14 | 14/14 | `ambiguous`: answered with ISS + SIBAL defaults without saying so |
| 2 | prompt `2026-11-14.2`: "Assumption:" line required for ambiguous questions | 12/14 | 14/14 | `ambiguous` again (prompt rule ignored); `arabic_question` answered in English (it passed in run 1: LLM variability) |
| 3 (tables above) | code guard: an "Assumption" line is added from the tools' actual arguments when the question names no material or atmosphere | 13/14 | 14/14 | `nomex_ood`: the LLM cited "NASA/TM-20210011385 Table 7.1" from the system prompt, not from a tool result; the grounding verifier rejected the draft twice and the deterministic answer was shown instead (OOD warning first, no estimate). Conservative by design. |

The fallback path is deterministic and passed 14/14 in every run. LLM-mode results vary from run to run; the code guards
(grounding verifier, OOD first line, claim consistency, assumption line) are what keep each answer safe when the LLM drifts.
