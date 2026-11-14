"""Run the hard-question eval set against the Copilot and save evidence for the judges.

    python evals/run_evals.py                 # LLM mode if a key is available, else fallback
    python evals/run_evals.py --mode both     # LLM and fallback, side by side
    python evals/run_evals.py --mode fallback --only lunar_habitat_ood

Outputs:
    evals/results.md                         summary tables (pass/fail per check)
    evals/transcripts/<mode>/<id>.json       full answer + tool trace per question
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src import copilot, copilot_tools  # noqa: E402
from src.copilot_prompt import PROMPT_VERSION  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_LATENCY = {"llm": 25_000, "fallback": 3_000}
DECLINE_RE = re.compile(r"cannot|can't|unable|won't|will not|not able|لا يمكن|لا أستطيع|مقدرش", re.IGNORECASE)
ARABIC_RE = re.compile(r"[؀-ۿ]")
CLARIFY_RE = re.compile(r"\?|؟|assum|افترض|افتراض|which material|what material|specify|clarify|please provide|need to know|let me know", re.IGNORECASE)


def check(case: dict[str, Any], res: copilot.CopilotResult, requested_mode: str) -> dict[str, tuple[bool, str]]:
    exp = case.get("expect", {})
    ans = res.answer
    low = ans.lower()
    called = [c["name"] for c in res.tool_calls]
    first = copilot._first_line_plain(ans)
    out: dict[str, tuple[bool, str]] = {}
    if exp.get("tools_called"):
        out["tool called"] = (bool(called), f"{len(called)} calls")
    if exp.get("tool_or_decline"):
        # With no tool calls, grounding_ok means every number in the answer came from the question itself.
        declined = bool(DECLINE_RE.search(ans)) and res.grounding_ok
        out["tool or decline"] = (bool(called) or declined, "tools" if called else ("declined" if declined else "neither"))
    if exp.get("must_call_any"):
        ok = any(n in called for n in exp["must_call_any"])
        out["right tool"] = (ok, "/".join(exp["must_call_any"]))
    if exp.get("must_call_all"):
        missing = [n for n in exp["must_call_all"] if n not in called]
        out["evidence tool"] = (not missing, "missing " + ",".join(missing) if missing else "ok")
    if "ood_first_line" in exp:
        if exp["ood_first_line"]:
            out["OOD first line"] = (res.ood and first.startswith(copilot.OOD_PREFIX), first[:60])
        else:
            out["not OOD"] = (not res.ood, "; ".join(res.ood_reasons)[:60] or "in-distribution")
    if exp.get("grounding_ok"):
        out["grounding"] = (res.grounding_ok, ", ".join(map(str, res.ungrounded)) or "ok")
    out["claims consistent"] = (res.claims_consistent and copilot.check_claim_consistency(ans, res.tool_calls)[0], "")
    if exp.get("contains_any"):
        ok = any(s.lower() in low for s in exp["contains_any"])
        out["content"] = (ok, " | ".join(exp["contains_any"])[:60])
    if exp.get("not_contains"):
        bad = [s for s in exp["not_contains"] if s.lower() in low]
        out["forbidden text"] = (not bad, ",".join(bad) or "ok")
    if exp.get("clarify_or_assume"):
        out["clarify/assume"] = (bool(CLARIFY_RE.search(ans)), "")
    if exp.get("arabic_answer") and res.mode == "llm":
        out["Arabic answer"] = (len(ARABIC_RE.findall(ans)) > 40, "")
    budget = (exp.get("max_latency_ms") or {}).get(requested_mode, DEFAULT_LATENCY[requested_mode])
    out["latency"] = (res.latency_ms <= budget, f"{res.latency_ms} ms ≤ {budget}")
    if requested_mode == "llm":
        out["stayed in LLM mode"] = (res.mode == "llm", res.mode + (f" ({'; '.join(res.notes)[:80]})" if res.mode != "llm" else ""))
    return out


def run(mode: str, cases: list[dict[str, Any]], pause_s: float) -> list[dict[str, Any]]:
    rows = []
    tdir = EVAL_DIR / "transcripts" / mode
    tdir.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(cases):
        if mode == "llm" and i:
            time.sleep(pause_s)  # stay polite with free-tier rate limits
        res = copilot.ask(case["question"], force_fallback=(mode == "fallback"))
        checks = check(case, res, mode)
        passed = all(ok for ok, _ in checks.values())
        rows.append({"case": case, "res": res, "checks": checks, "passed": passed})
        (tdir / f"{case['id']}.json").write_text(
            json.dumps({"id": case["id"], "question": case["question"], "behavior": case.get("behavior"),
                        "passed": passed, "checks": {k: {"ok": ok, "detail": d} for k, (ok, d) in checks.items()},
                        **res.to_dict()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        failed = [k for k, (ok, _) in checks.items() if not ok]
        print(f"[{mode:8}] {'PASS' if passed else 'FAIL'}  {case['id']:28} {res.mode:8} {res.latency_ms:6} ms  "
              f"tools={len(res.tool_calls)} ood={res.ood} grounded={res.grounding_ok}" + (f"  ✗ {failed}" if failed else ""))
    return rows


def table(mode: str, rows: list[dict[str, Any]]) -> str:
    n_pass = sum(r["passed"] for r in rows)
    lines = [
        f"### Mode: `{mode}` · {n_pass}/{len(rows)} passed",
        "",
        "| # | Case | Result | Answered by | Tools | OOD | Grounded | Latency (ms) | Failed checks |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        res = r["res"]
        failed = [f"{k} ({d})" if d else k for k, (ok, d) in r["checks"].items() if not ok]
        lines.append(
            f"| {i} | `{r['case']['id']}` | {'✅ pass' if r['passed'] else '❌ fail'} | {res.mode} | "
            f"{', '.join(dict.fromkeys(c['name'] for c in res.tool_calls)) or '-'} | {'⚠️' if res.ood else '-'} | "
            f"{'✅' if res.grounding_ok else '❌'} | {res.latency_ms} | {'; '.join(failed).replace('|', '/') or '-'} |"
        )
    lat = sorted(r["res"].latency_ms for r in rows)
    if lat:
        lines += ["", f"Latency: median {lat[len(lat) // 2]} ms, max {lat[-1]} ms."]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "llm", "fallback", "both"], default="auto")
    ap.add_argument("--only", nargs="*", help="case ids to run")
    ap.add_argument("--pause", type=float, default=3.0, help="seconds between LLM questions")
    ap.add_argument("--out", default=str(EVAL_DIR / "results.md"))
    a = ap.parse_args()

    cases = yaml.safe_load((EVAL_DIR / "hard_questions.yaml").read_text(encoding="utf-8"))
    if a.only:
        cases = [c for c in cases if c["id"] in a.only]
    has_key = bool(copilot.get_api_key())
    modes = {"auto": ["llm" if has_key else "fallback"], "both": ["llm", "fallback"]}.get(a.mode, [a.mode])
    if "llm" in modes and not has_key:
        print("No GEMINI_API_KEY found: skipping LLM mode.")
        modes = [m for m in modes if m != "llm"] or ["fallback"]

    if copilot_tools.backend_name() == "real":
        # Warm-up, as the app does with st.cache_resource: load the model and the boundary cache before timing.
        from src import api

        api.get_engine()
        api.flammability_boundary("SIBAL", 14.7)
    sections = []
    for m in modes:
        rows = run(m, cases, a.pause)
        sections.append(table(m, rows))
        print()
        print(sections[-1])
        print()

    header = [
        "# Copilot eval results",
        "",
        f"- Run: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- LLM model: `{copilot.get_model()}` (fallback model `{copilot.get_fallback_model()}`)" if has_key else "- LLM: no key, fallback only",
        f"- Prompt version: `{PROMPT_VERSION}` · prediction backend: `{copilot_tools.backend_name()}`",
        f"- Cases: `evals/hard_questions.yaml` ({len(cases)}) · transcripts: `evals/transcripts/<mode>/<id>.json`",
        "- Checks: tool called (or explicit decline with no numbers), right tool, OOD warning as first line (or not OOD), code-level grounding verifier, "
        "claim consistency (verdict words vs the tool's label), expected content, latency budget (LLM 25 s / fallback 3 s).",
        "- The prediction engine is loaded once before timing (as the app does with `st.cache_resource`).",
        "",
    ]
    if copilot_tools.backend_name() == "mock":
        header += ["> Predictions come from the **mock API** (synthetic placeholder) until `src/api.py` lands. "
                   "These evals test the Copilot's behavior (grounding, OOD handling, tool use), not the model's accuracy.", ""]
    Path(a.out).write_text("\n".join(header) + "\n" + "\n\n".join(sections) + "\n", encoding="utf-8")
    print(f"Saved {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
