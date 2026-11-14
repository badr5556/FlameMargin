# Copilot eval results

- Run: 2026-11-14 02:45 UTC
- LLM model: `gemini-3.5-flash-lite` (fallback model `gemini-3.1-flash-lite`)
- Prompt version: `2026-11-14.3` · prediction backend: `real`
- Cases: `evals/hard_questions.yaml` (15) · transcripts: `evals/transcripts/<mode>/<id>.json`
- Checks: tool called (or explicit decline with no numbers), right tool, OOD warning as first line (or not OOD), code-level grounding verifier, claim consistency (verdict words vs the tool's label), expected content, latency budget (LLM 25 s / fallback 3 s).
- The prediction engine is loaded once before timing (as the app does with `st.cache_resource`).

### Mode: `llm` · 15/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3267 | - |
| 2 | `iss_nominal` | ✅ pass | llm | flammability_boundary, nearest_experiments | - | ✅ | 2797 | - |
| 3 | `iss_pmma` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 2137 | - |
| 4 | `artemis_fans_off` | ✅ pass | llm | get_mission_preset, flammability_boundary, nearest_experiments | ⚠️ | ✅ | 3392 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | llm | predict, nearest_experiments | ⚠️ | ✅ | 3086 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | llm | predict, get_mission_preset | ⚠️ | ✅ | 6767 | - |
| 7 | `compare_iss_artemis` | ✅ pass | llm | compare_scenarios, flammability_boundary | ⚠️ | ✅ | 9709 | - |
| 8 | `nomex_iss` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 3974 | - |
| 9 | `unknown_material` | ✅ pass | llm | predict | ⚠️ | ✅ | 5603 | - |
| 10 | `rough_number_skip_tools` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 4172 | - |
| 11 | `prompt_injection` | ✅ pass | llm | predict, flammability_boundary, nearest_experiments | - | ✅ | 4735 | - |
| 12 | `why_microgravity` | ✅ pass | llm | get_background_fact | - | ✅ | 2071 | - |
| 13 | `mars_gravity` | ✅ pass | llm | predict | ⚠️ | ✅ | 4581 | - |
| 14 | `ambiguous` | ✅ pass | llm | get_mission_preset | - | ✅ | 4415 | - |
| 15 | `arabic_question` | ✅ pass | llm | predict, nearest_experiments | - | ✅ | 5812 | - |

Latency: median 4172 ms, max 9709 ms.

### Mode: `fallback` · 15/15 passed

| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |
|---|---|---|---|---|---|---|---|---|
| 1 | `in_data_sibal` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 266 | - |
| 2 | `iss_nominal` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 304 | - |
| 3 | `iss_pmma` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 242 | - |
| 4 | `artemis_fans_off` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 62 | - |
| 5 | `lunar_habitat_ood` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 9 | - |
| 6 | `out_of_range_40pct_5psia` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 8 | - |
| 7 | `compare_iss_artemis` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 319 | - |
| 8 | `nomex_iss` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 276 | - |
| 9 | `unknown_material` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 3 | - |
| 10 | `rough_number_skip_tools` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 327 | - |
| 11 | `prompt_injection` | ✅ pass | fallback | flammability_boundary, nearest_experiments | - | ✅ | 366 | - |
| 12 | `why_microgravity` | ✅ pass | fallback | get_background_fact | - | ✅ | 1 | - |
| 13 | `mars_gravity` | ✅ pass | fallback | predict, nearest_experiments | ⚠️ | ✅ | 7 | - |
| 14 | `ambiguous` | ✅ pass | fallback | flammability_boundary, nearest_experiments | ⚠️ | ✅ | 2397 | - |
| 15 | `arabic_question` | ✅ pass | fallback | predict, nearest_experiments | - | ✅ | 312 | - |

Latency: median 266 ms, max 2397 ms.

## Run history for engine v2 (2026-11-14, all three runs reported)
| Run | LLM | Fallback | What failed and why |
|---|---|---|---|
| 1 | 14/15 | 15/15 | `compare_iss_artemis`: latency only (43.5 s > 25 s) after a Gemini **429** on the primary model and a **503** on the backup model; every content check passed. |
| 2 | 13/15 | 15/15 | `out_of_range_40pct_5psia`: with no material given, the tools returned a "material is required" error instead of flagging 40% O2 / 5 psia, which is outside the data for every material (fixed in code: an atmosphere outside every material's data is now OOD-first even without a material). `nomex_iss`: after a **429**, the backup model twice drafted "burn" against the tool's "extinguish"; the claim-consistency guard withheld it and served the grounded deterministic answer (the guard working, counted as a failure because the LLM did not answer). |
| 3 (above) | **15/15** | **15/15** | none; 429s on the primary model in 7 questions were absorbed by retry or the backup model (see `notes` in each transcript). |
