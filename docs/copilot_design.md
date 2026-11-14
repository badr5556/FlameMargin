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
   (dataset is ISS microgravity only ...)", whatever the model says                       │
   adapter: src/api.py (Layer 1); if not importable -> engine_unavailable errors      │
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
   4. mock disclosure line (unit tests only: the mock is a test fixture)
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

- `python -m pytest -q`: offline unit tests (faked Gemini client) for the Copilot, the engine contract, OOD rules,
  data derivation rules and facts.
- `python evals/run_evals.py --mode both` → `evals/results.md` + per-question transcripts for 14 adversarial
  questions on the real engine (ISS extrapolation, Artemis / lunar / Mars OOD, 40% O2 and 5 psia, prompt injection,
  "skip the tools", Nomex and Kapton, ambiguity, Arabic). Final run: LLM 13/14, fallback 14/14; all three runs are listed.

## Upgrades (2026-11-14)

- **Real engine:** `src/api.py` is used automatically; the mock is a unit-test fixture only. If the engine cannot be
  imported, prediction tools return `engine_unavailable`: no synthetic numbers are ever shown.
- **Per-session LLM budget:** `COPILOT_SESSION_LLM_LIMIT` (default 15) questions per browser session, then the
  deterministic fallback with a note (the public link runs on a free-tier key).
- **Backup key rotation:** `GEMINI_API_KEY_BACKUP` is tried before the backup model and before the fallback.
- **Claim-consistency check:** verdict words must not contradict the tool's label (burn / extinguish / uncertain);
  one regeneration with feedback, then deterministic tool outputs.
- **Assumption line:** if the operator named no material and no atmosphere, code adds a line stating the defaults the
  tools actually used.

## Known limits

- The grounding verifier proves numbers **exist** in tool results, not that the sentence around them is
  **semantically right**. Mitigations: comparisons are computed in code, and the claim-consistency check covers verdicts.
- The engine covers one material at 1 atm in microgravity; most real questions are (correctly) out of distribution.
- "Fans off" has no agreed flow value, on purpose: our data do not measure residual flow with fans off.
- Background facts carry `verified` flags that mirror `docs/science/claims_sheet.md` (C1, C9, C12, C13 still pending).
- Decision support only, not a replacement for NASA-STD-6001 material testing.

## AI-use disclosure

The IGNISPHERE team conceived FlameMargin, designed its three-layer architecture and the Copilot's safety rules (tool-only numbers, OOD-first answers, grounding checks, deterministic fallback), extracted and organized the NASA test data, selected and verified the NASA sources, and reviewed and tested every component. We used AI assistants (Claude, by Anthropic; and others for data extraction support) to help implement and test parts of the code and to draft documentation under the team's direction. Google Gemini is the runtime LLM inside the Copilot; it never produces numbers on its own, and every number comes from our model through tool calls. All scientific claims are traceable to the primary sources in `docs/science/claims_sheet.md`.
