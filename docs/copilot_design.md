# FlameMargin Copilot: design and guardrails (Layer 3)

**One line:** an LLM agent that answers fire-safety questions **only through the prediction engine's tools**,
with code (not just the prompt) enforcing that every number is grounded and out-of-distribution warnings come first.

## Architecture

```
operator question (EN / AR)
        │
        ▼
 src/copilot.py ── ask() ───────────────────────────────────────────────────────────────┐
   │  Gemini (google-genai), temperature 0.2, MANUAL function-calling loop               │
   │  ≤ 6 rounds · parallel calls · tool errors returned as structured results           │
   │  retry once on 429/5xx → secondary Flash-Lite model → deterministic fallback        │
   ▼                                                                                     │
 src/copilot_tools.py  (the only door to numbers)                                         │
   normalization: "34%" / 0.34 · kPa/atm/bar → psia · mm/s, m/s → cm/s · "fans off" ·     │
   material aliases (EN/AR) · mission presets · physical-validity errors                  │
   HARD RULE: gravity ≠ µg ⇒ ood_flag=True "no training data at this gravity level        │
   (FM2 not yet flown)", whatever the model says                                          │
   adapter: src/api.py (Layer 1) if importable, else src/copilot_mock_api.py              │
   tools: predict · flammability_boundary · compare_scenarios · nearest_experiments ·     │
          get_mission_preset · get_background_fact (src/copilot_facts.py, sourced)        │
        │                                                                                 │
        ▼                                                                                 │
 code guards on the draft answer ◄────────────────────────────────────────────────────────┘
   1. input grounding: a flow velocity the operator never gave → tool error "unsupported_assumption"
   2. output grounding: verify_grounding() → every number must match a tool value (or the question)
      within rounding; experiment IDs must exist in tool results → 1 regeneration with the list of
      ungrounded values → else show deterministic tool outputs, grounding_ok=False
   3. OOD guard: any OOD result ⇒ first line "⚠️ Out of distribution: <reason>" (prepended if missing)
   4. mock disclosure line while the mock API is the backend
        │
        ▼
 CopilotResult {answer, tool_calls[name,args,result,ms], ood, ood_reasons, grounding_ok, mode, latency_ms}
        │
        ▼
 src/copilot_ui.py: chat + badges (LLM/Fallback · OOD · grounding · data source) + tool trace
```

## Guardrails: prompt vs. code

| Rule | In the prompt | Enforced in code |
|---|---|---|
| Numbers only from tools | ✅ rule 1 | ✅ `verify_grounding` + regeneration + withhold |
| Don't invent inputs | ✅ | ✅ `check_input_grounding` (flow velocity) |
| OOD first | ✅ rule 2 | ✅ `enforce_ood_first_line` |
| Non-µg gravity is OOD | ✅ | ✅ `copilot_tools._merge_ood` (hard rule, every tool) |
| Out-of-range inputs not clamped | n/a | ✅ passed through and flagged OOD; physically impossible inputs are errors |
| No LLM number comparisons | ✅ | ✅ boundary result lists flammable / non-flammable flows computed in code |
| Report intervals; cite experiments | ✅ rules 3–4 | partly: intervals and IDs are in every tool result; IDs verified |
| Conservative recommendations | ✅ rule 8 | fallback template only |
| Mock data disclosed | ✅ rule 9 | ✅ footer + UI badge |

**Fallback mode** (no key, network blocked, 429/5xx, or grounding failure): a rule-based intent parser
(presets, material, O₂, pressure, flow, gravity, compare, fans off, why; English + Arabic keywords) calls
the same tools and renders the same 5-part template (**Verdict → Key numbers → Evidence →
Operational recommendation → Limits**), OOD first. It passes the same grounding verifier.

## Evidence

- `pytest tests/test_copilot.py`: offline unit tests with a faked Gemini client.
- `python evals/run_evals.py --mode both` → `evals/results.md` + per-question transcripts for 12
  adversarial questions (lunar / Mars OOD, 5 psia out of range, prompt injection, "skip the tools",
  unknown material, ambiguity, Arabic).

## Known limits

- The grounding verifier proves numbers **exist** in tool results, not that the sentence around them is
  **semantically right** (e.g. a cherry-picked range). Mitigation: comparisons are computed in code.
- Until `src/api.py` lands, all predictions are synthetic (mock), and are labelled as such everywhere.
- "Fans off" has no agreed flow value yet (see `docs/copilot_integration.md`).
- Background facts were re-worded against `docs/science/claims_sheet.md` (2026-11-13) but stay `verified: False`:
  the primary sources could not be opened from the build environment, only search extracts of them.
- Decision support only, not a replacement for NASA-STD-6001 material testing.

## AI-use disclosure (Space Apps)

- **Runtime:** the Copilot uses Google Gemini (default `gemini-3.5-flash-lite`, via the `google-genai`
  SDK) to understand questions, choose tools and write answers. All predictions come from the FlameMargin
  model through tools; the LLM generates no numbers of its own (enforced by the code guards above).
- **Development:** the Layer 3 code, tests, evals and these docs were written with an AI coding assistant
  (Claude Code, Anthropic) under the direction of, and reviewed by, the Layer 3 owner (Omar, team IGNISPHERE).
- Background facts started from the team brief; they were fact-checked with AI-assisted web search (Claude Code)
  against search-engine extracts of the primary sources and corrected where the brief was too strong
  (`docs/science/claims_sheet.md`). They remain marked unverified until a human opens each source.
