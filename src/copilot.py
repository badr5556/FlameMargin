"""FlameMargin Fire Safety Copilot (Layer 3): agent core.

    from src.copilot import ask
    res = ask("Is SIBAL fabric safe in the Artemis atmosphere with fans off?")
    print(res.answer, res.tool_calls, res.ood, res.grounding_ok, res.mode)

CLI:
    python -m src.copilot "question"            # LLM if a key is available, else fallback
    python -m src.copilot --fallback "question" # force the deterministic path
    python -m src.copilot --json "question"     # machine-readable output

Pipeline
    question -> Gemini manual function-calling loop (<= 6 rounds, parallel calls,
    tool errors returned as structured results) -> code guards:
      1. grounding verifier: every number in the answer must match a tool result
         (or the user's own question); one regeneration with feedback, then
         fallback-formatted tool outputs with grounding_ok=False
      2. OOD guard: if any tool result is OOD, the first line must be the warning
      3. mock-data disclosure line when the mock API is the backend
    Any LLM failure (no key, network, 429/5xx after retry, empty output) ->
    deterministic fallback: rule-based intent parser + direct tool calls +
    the same 5-part template. The demo never dies.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src import copilot_tools as tools
from src.copilot_prompt import PROMPT_VERSION, SYSTEM_PROMPT

DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemini-3.1-flash-lite"
MAX_ROUNDS = 6
TEMPERATURE = 0.2
REQUEST_TIMEOUT_MS = 30_000
LLM_BUDGET_S = float(os.environ.get("COPILOT_LLM_BUDGET_S", "60"))
OOD_PREFIX = "⚠️ Out of distribution:"
MOCK_DISCLOSURE = "_Data source: placeholder mock model (synthetic, not NASA data) until the Layer 1 API is connected._"
SAFETY_DISCLAIMER = "Decision support only, not a replacement for NASA-STD-6001 material testing."
REPO_ROOT = Path(__file__).resolve().parent.parent


# =========================================================================== #
# Result type
# =========================================================================== #
@dataclass
class CopilotResult:
    answer: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    ood: bool = False
    ood_reasons: list[str] = field(default_factory=list)
    grounding_ok: bool = True
    mode: str = "fallback"  # "llm" | "fallback"
    latency_ms: int = 0
    model: str | None = None
    backend: str = ""
    ungrounded: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    claims_consistent: bool = True
    prompt_version: str = PROMPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# =========================================================================== #
# Config / secrets (the key is never printed or logged)
# =========================================================================== #
def _config_value(name: str) -> str | None:
    """os.environ -> st.secrets -> .env (python-dotenv). Returns None if unset."""
    v = os.environ.get(name, "").strip()
    if v:
        return v
    try:
        if "streamlit" in sys.modules:
            import streamlit as st

            v = str(st.secrets.get(name, "")).strip()
            if v:
                return v
    except Exception:  # noqa: BLE001 - no secrets.toml is fine
        pass
    try:
        from dotenv import dotenv_values

        v = str(dotenv_values(REPO_ROOT / ".env").get(name) or "").strip()
        if v:
            return v
    except Exception:  # noqa: BLE001
        pass
    return None


def get_api_key() -> str | None:
    return _config_value("GEMINI_API_KEY")


def get_backup_api_key() -> str | None:
    """Optional second key (GEMINI_API_KEY_BACKUP), tried before the backup model and before fallback."""
    k = _config_value("GEMINI_API_KEY_BACKUP")
    return k if k and k != get_api_key() else None


DEFAULT_SESSION_LLM_LIMIT = 15


def session_llm_limit() -> int:
    """LLM questions allowed per UI session (COPILOT_SESSION_LLM_LIMIT, default 15): the public link runs on a free-tier key."""
    try:
        return max(0, int(_config_value("COPILOT_SESSION_LLM_LIMIT") or DEFAULT_SESSION_LLM_LIMIT))
    except ValueError:
        return DEFAULT_SESSION_LLM_LIMIT


def llm_attempts(key: str, backup_key: str | None, model: str, fallback_model: str) -> list[tuple[str, str, str]]:
    """(key label, key, model) in the order they are tried: primary key, backup key, then the backup model."""
    keys = [("primary key", key)] + ([("backup key", backup_key)] if backup_key else [])
    out = []
    for m in dict.fromkeys([model, fallback_model]):
        out += [(label, k, m) for label, k in keys]
    return out


def get_model() -> str:
    return _config_value("GEMINI_MODEL") or DEFAULT_MODEL


def get_fallback_model() -> str:
    return _config_value("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL


_CLIENT: Any = None
_CLIENT_KEY_ID: int | None = None


def _get_client(key: str) -> Any:
    global _CLIENT, _CLIENT_KEY_ID
    if _CLIENT is None or _CLIENT_KEY_ID != hash(key):
        from google import genai
        from google.genai import types

        _CLIENT = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
        _CLIENT_KEY_ID = hash(key)
    return _CLIENT


# =========================================================================== #
# Grounding verifier
# =========================================================================== #
# Identifiers that contain digits (O2, CO2, FM2, MOCK-BASS-II-07, NASA-STD-6001, ...) are not quantities.
_IDENT_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_]*(?:[-_][A-Za-z0-9]+)*")
# Experiment IDs that must appear verbatim in tool results: MOCK-BASS-II-07 style, Table 7.1 IDs like GMT45-T4, and the
# Appendix A test numbers (B6, F1, P12, M10, O13a, T5, ...). "O2" (the gas) is never read as Olson's test O2.
_EXPERIMENT_ID_RE = re.compile(
    r"(?<![\w-])(?:[A-Z][A-Za-z]*(?:-[A-Za-z0-9]+)*-\d+[A-Za-z0-9]*|GMT\d+-T\d+[a-z]?|[BFPMT]\d{1,2}[ab]?|O(?:1\d|[13-9])[ab]?)(?![\w-])")
_LIST_MARKER_RE = re.compile(r"^(\s*(?:[#>*\-]\s*)*)\d+[.)](?=\s)", re.MULTILINE)
_FRACTION_G_RE = re.compile(r"(?<![\d.])(\d+)\s*/\s*(\d+)(?=\s*g\b)")
_NUMBER_RE = re.compile(r"(?<![\d.٫])(\d+(?:[.٫]\d+)?)(\s*(?:%|٪|percent|بالمئة))?")
ID_WHITELIST = {"NASA-STD-6001"}
TRIVIAL_NUMBERS = {0.0, 1.0}


@dataclass
class NumberToken:
    text: str
    value: float
    decimals: int
    percent: bool


@dataclass
class GroundingReport:
    ok: bool
    ungrounded: list[str]
    checked: int
    unknown_ids: list[str] = field(default_factory=list)


def extract_numbers(text: str) -> list[NumberToken]:
    """Quantities in free text. Handles %, ranges (a–b → two numbers), 1/6 g, Arabic-Indic digits."""
    if not text:
        return []
    s = _LIST_MARKER_RE.sub(r"\1", text)
    tokens: list[NumberToken] = []

    def _frac(m: re.Match[str]) -> str:
        a, b = int(m.group(1)), int(m.group(2))
        if b:
            tokens.append(NumberToken(m.group(0), a / b, 3, False))
        return " "

    s = _FRACTION_G_RE.sub(_frac, s)
    s = _IDENT_RE.sub(lambda m: " " if re.search(r"\d", m.group(0)) else m.group(0), s)
    for m in _NUMBER_RE.finditer(s):
        raw = m.group(1).replace("٫", ".")
        try:
            val = float(raw)
        except ValueError:
            continue
        dec = len(raw.split(".")[1]) if "." in raw else 0
        tokens.append(NumberToken(m.group(0).strip(), val, dec, bool(m.group(2))))
    return tokens


def _collect_values(obj: Any, out: list[float], texts: list[str]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        texts.append(obj)
        out.extend(t.value for t in extract_numbers(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_values(v, out, texts)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_values(v, out, texts)


def _matches(tok: NumberToken, allowed: list[float]) -> bool:
    tol = 0.5 * 10 ** (-tok.decimals) + 1e-9
    for v in allowed:
        if abs(abs(tok.value) - abs(v)) <= tol:
            return True
        if tok.percent and abs(tok.value - abs(v) * 100.0) <= tol:
            return True
    return False


def _contains_token(haystack: str, token: str) -> bool:
    """Whole-token match, so MOCK-BASS-II-2 does not match MOCK-BASS-II-24."""
    return re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", haystack) is not None


def verify_grounding(answer: str, tool_results: list[Any], question: str = "") -> GroundingReport:
    """Every number in ``answer`` must match a tool-result value (or the user's question) within rounding.

    Allowed conversions: percent <-> fraction (0.87 ↔ 87%), and anything the normalization layer already
    converted (both units are present in the tool results, e.g. pressure_psia and pressure_kpa).
    Experiment-ID-like tokens (e.g. MOCK-BASS-II-07) must appear verbatim in the tool results.
    """
    allowed: list[float] = list(TRIVIAL_NUMBERS)
    texts: list[str] = []
    _collect_values(tool_results, allowed, texts)
    allowed.extend(t.value for t in extract_numbers(question))
    toks = extract_numbers(answer)
    bad = [t.text for t in toks if not _matches(t, allowed)]
    blob = "\n".join(texts) + "\n" + json.dumps(tool_results, ensure_ascii=False, default=str)
    unknown_ids = [
        i for i in dict.fromkeys(_EXPERIMENT_ID_RE.findall(answer))
        if i not in ID_WHITELIST and not _contains_token(blob, i) and not _contains_token(question, i)
    ]
    return GroundingReport(ok=not bad and not unknown_ids, ungrounded=list(dict.fromkeys(bad)), checked=len(toks), unknown_ids=unknown_ids)


# =========================================================================== #
# Claim-consistency check: verdict words must not contradict the tool's label
# =========================================================================== #
_SAYS_BURN_RE = re.compile(
    r"\b(will|would|is predicted to|predicted to|expected to|likely to|keeps?|continues? to)\s+(burn|keep burning|sustain)|"
    r"\b(is|are|remains?)\s+flammable\b|\bFLAMMABLE\b|\bverdict\W+burn\b|سيحترق|قابل للاشتعال",
    re.IGNORECASE)
_SAYS_EXTINGUISH_RE = re.compile(
    r"\bself-extinguish|\b(will|would|is predicted to|predicted to|expected to|likely to)\s+(extinguish|go out|quench)|"
    r"\b(not|non-?)\s*flammable\b|\bwon'?t burn\b|\bwill not burn\b|\bverdict\W+extinguish|ينطفئ|غير قابل للاشتعال",
    re.IGNORECASE)
_NEGATED_BURN_RE = re.compile(r"\b(not|never|no longer|won'?t|cannot|can'?t)\s+(be\s+)?(burn|flammable|sustain)", re.IGNORECASE)


def _verdict_text(answer: str) -> str:
    """The Verdict section (or, without headers, the first paragraph after any OOD line)."""
    m = re.search(r"\*\*\s*Verdict\s*\*\*(.*?)(?=\*\*\s*(Key numbers|Evidence|Operational recommendation|Limits)\s*\*\*|\Z)",
                  answer, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1)
    paras = [p for p in answer.split("\n\n") if p.strip() and not _first_line_plain(p).startswith(OOD_PREFIX)]
    return paras[0] if paras else ""


def check_claim_consistency(answer: str, tool_calls: list[dict[str, Any]]) -> tuple[bool, str]:
    """Returns (ok, problem). Only single-verdict answers are checked (one predicted label across all tools)."""
    labels = set()
    for c in tool_calls:
        r = c.get("result") or {}
        if not isinstance(r, dict) or "error" in r:
            continue
        rows = r["value"] if c.get("name") == "compare_scenarios" and isinstance(r.get("value"), list) else [r]
        for x in rows:
            if isinstance(x, dict) and x.get("label") in ("burn", "extinguish", "uncertain"):
                labels.add(x["label"])
    if len(labels) != 1:
        return True, ""
    label = labels.pop()
    v = _verdict_text(answer)
    says_burn = bool(_SAYS_BURN_RE.search(v)) and not _NEGATED_BURN_RE.search(v)
    says_ext = bool(_SAYS_EXTINGUISH_RE.search(v))
    if label == "extinguish" and says_burn and not says_ext:
        return False, "the tools predict EXTINGUISH but the verdict says the material burns"
    if label == "burn" and says_ext and not says_burn:
        return False, "the tools predict BURN but the verdict says the material extinguishes"
    if label == "uncertain" and (says_burn ^ says_ext) and not re.search(r"uncertain|cannot|can't|no verdict|not enough|unknown|extrapolat|لا يمكن|غير مؤكد", v, re.IGNORECASE):
        return False, "the tools return UNCERTAIN (extrapolation) but the verdict states a definite outcome"
    return True, ""


# =========================================================================== #
# OOD guard
# =========================================================================== #
def collect_ood(tool_calls: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for c in tool_calls:
        r = c.get("result") or {}
        if not isinstance(r, dict) or "error" in r:
            continue
        if r.get("ood_flag"):
            rs = r.get("ood_reasons") or ([r["ood_reason"]] if r.get("ood_reason") else ["model flagged input as OOD"])
            reasons.extend(str(x) for x in rs)
    uniq = list(dict.fromkeys(reasons))
    return bool(uniq), uniq


def _first_line_plain(answer: str) -> str:
    for line in answer.splitlines():
        if line.strip():
            return re.sub(r"^[\s>#*_`]+", "", line).strip()
    return ""


def enforce_ood_first_line(answer: str, ood: bool, reasons: list[str]) -> tuple[str, bool]:
    """Return (answer, prepended?)."""
    if not ood or _first_line_plain(answer).startswith(OOD_PREFIX):
        return answer, False
    return f"{OOD_PREFIX} {'; '.join(reasons)}\n\n{answer}", True


# =========================================================================== #
# LLM path (google-genai, manual function calling)
# =========================================================================== #
class LLMUnavailable(RuntimeError):
    """Transient/unrecoverable LLM failure -> try next model or fallback."""


def _is_transient(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if isinstance(code, int):
        return code == 429 or code >= 500
    name = type(e).__name__.lower()
    return any(k in name for k in ("timeout", "connect", "network", "remoteprotocol", "readerror"))


def _history_to_contents(history: list[dict[str, Any]] | None) -> list[Any]:
    from google.genai import types

    contents = []
    for m in (history or [])[-10:]:
        role = m.get("role", "user")
        text = m.get("content") or m.get("text") or ""
        if not text:
            continue
        contents.append(types.Content(role="model" if role in ("assistant", "model") else "user", parts=[types.Part(text=str(text))]))
    return contents


def _make_config(final_no_tools: bool = False) -> Any:
    from google.genai import types

    decls = [
        types.FunctionDeclaration(name=d["name"], description=d["description"], parameters_json_schema=d["parameters"])
        for d in tools.get_tool_declarations()
    ]
    cfg = dict(
        system_instruction=SYSTEM_PROMPT,
        temperature=TEMPERATURE,
        tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if final_no_tools:
        cfg["tool_config"] = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="NONE"))
    return types.GenerateContentConfig(**cfg)


def _generate(client: Any, model: str, contents: list[Any], config: Any, notes: list[str]) -> Any:
    """One generate call with a single retry + backoff on 429/5xx/timeouts."""
    for attempt in range(2):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            msg = f"{model}: {type(e).__name__}{f' {code}' if code else ''}"
            if _is_transient(e) and attempt == 0:
                notes.append(msg + " (retrying)")
                time.sleep(1.5)
                continue
            raise LLMUnavailable(msg) from e
    raise LLMUnavailable(f"{model}: retries exhausted")


_FLOW_TOOLS = ("predict", "compare_scenarios")


def _flow_values(name: str, args: dict[str, Any]) -> list[Any]:
    if name == "predict":
        return [args.get("flow_velocity_cm_s")]
    if name == "compare_scenarios" and isinstance(args.get("scenarios"), list):
        return [s.get("flow_velocity_cm_s") for s in args["scenarios"] if isinstance(s, dict)]
    return []


def check_input_grounding(name: str, args: dict[str, Any], operator_text: str) -> dict[str, Any] | None:
    """Inputs must be grounded too: the LLM may not invent a flow velocity the operator never gave.

    Returns a structured tool error, or None when the call is fine. 'fans off' is always allowed
    (the tool layer resolves or rejects it).
    """
    if name not in _FLOW_TOOLS:
        return None
    # Numbers the operator attached to O2 or pressure cannot justify a flow ("10 psia" is not "10 cm/s").
    flow_text = _P_RE.sub(" ", _O2_RE.sub(" ", operator_text))
    allowed = [t.value for t in extract_numbers(flow_text)]
    for m in _FLOW_RE.finditer(operator_text):  # operator flows converted to cm/s (e.g. "5 mm/s" -> 0.5)
        try:
            allowed.append(tools.parse_flow_cm_s(f"{m.group(1)} {m.group(2)}")[0])
        except tools.ToolInputError:
            pass
    for v in _flow_values(name, args):
        if v in (None, "") or tools.is_fans_off(v):
            continue
        num = v if isinstance(v, (int, float)) and not isinstance(v, bool) else next((t.value for t in extract_numbers(str(v))), None)
        if num is None:
            continue
        try:
            cm_s = tools.parse_flow_cm_s(v)[0]
        except tools.ToolInputError:
            cm_s = num
        if not any(abs(num - a) < 1e-6 or abs(cm_s - a) < 1e-6 for a in allowed):
            return {"error": {
                "type": "unsupported_assumption",
                "message": f"flow_velocity_cm_s={v} was not given by the operator. Do not assume a flow.",
                "hint": "Call flammability_boundary (covers all flows) or ask the operator for the flow.",
            }}
    return None


def _execute_calls(function_calls: list[Any], trace: list[dict[str, Any]], operator_text: str = "") -> list[Any]:
    """Run every function call of one model turn (parallel calls supported); returns response parts."""
    from google.genai import types

    parts = []
    for fc in function_calls:
        args = dict(fc.args or {})
        t0 = time.perf_counter()
        result = check_input_grounding(fc.name, args, operator_text) or tools.dispatch(fc.name, args)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        trace.append({"name": fc.name, "args": args, "result": result, "ms": ms})
        parts.append(types.Part(function_response=types.FunctionResponse(id=getattr(fc, "id", None), name=fc.name, response=result)))
    return parts


def _response_text(resp: Any) -> str:
    try:
        cand = resp.candidates[0]
        texts = [p.text for p in (cand.content.parts or []) if getattr(p, "text", None) and not getattr(p, "thought", False)]
        return "\n".join(texts).strip()
    except (AttributeError, IndexError, TypeError):
        return ""


def _run_loop(client: Any, model: str, contents: list[Any], trace: list[dict[str, Any]], notes: list[str], deadline: float, max_rounds: int, operator_text: str = "") -> str:
    config = _make_config()
    for _ in range(max_rounds):
        if time.monotonic() > deadline:
            raise LLMUnavailable("LLM time budget exceeded")
        resp = _generate(client, model, contents, config, notes)
        fcs = resp.function_calls or []
        cand_content = resp.candidates[0].content if resp.candidates else None
        if not fcs:
            text = _response_text(resp)
            if cand_content is not None:
                contents.append(cand_content)
            if not text:
                raise LLMUnavailable(f"{model}: empty answer")
            return text
        contents.append(cand_content)  # keeps thought signatures for the next round
        from google.genai import types

        contents.append(types.Content(role="user", parts=_execute_calls(fcs, trace, operator_text)))
    # Round budget spent: force a text answer from what we have.
    resp = _generate(client, model, contents, _make_config(final_no_tools=True), notes)
    text = _response_text(resp)
    if not text:
        raise LLMUnavailable(f"{model}: no final answer after {max_rounds} rounds")
    if resp.candidates:
        contents.append(resp.candidates[0].content)
    return text


def _llm_answer(question: str, history: list[dict[str, Any]] | None, key: str, model: str, notes: list[str]) -> tuple[str, list[dict[str, Any]], GroundingReport, bool]:
    """Returns (answer, trace, grounding report, regenerated?). Raises LLMUnavailable."""
    from google.genai import types

    client = _get_client(key)
    deadline = time.monotonic() + LLM_BUDGET_S
    contents = _history_to_contents(history) + [types.Content(role="user", parts=[types.Part(text=question)])]
    trace: list[dict[str, Any]] = []
    operator_text = "\n".join([str(m.get("content") or m.get("text") or "") for m in (history or []) if m.get("role") == "user"] + [question])
    answer = _run_loop(client, model, contents, trace, notes, deadline, MAX_ROUNDS, operator_text)
    report = verify_grounding(answer, [c["result"] for c in trace], question)
    consistent, problem = check_claim_consistency(answer, trace)
    if report.ok and consistent:
        return answer, trace, report, False
    # One regeneration with explicit feedback.
    parts = []
    if not report.ok:
        problems = report.ungrounded + [f"experiment ID {i}" for i in report.unknown_ids]
        parts.append("GROUNDING CHECK FAILED. These values in your answer do not appear in any tool result from this turn: "
                     + ", ".join(problems) + ". Use ONLY numbers and IDs that appear in tool results (call tools again if "
                     "needed). Do not compute new numbers yourself.")
        notes.append("grounding failed on first draft: " + ", ".join(problems))
    if not consistent:
        parts.append(f"CLAIM CONSISTENCY CHECK FAILED: {problem}. Your verdict words must match the tool's label.")
        notes.append("claim-consistency failed on first draft: " + problem)
    contents.append(types.Content(role="user", parts=[types.Part(text=" ".join(parts) + " Rewrite the answer; keep the same structure.")]))
    answer2 = _run_loop(client, model, contents, trace, notes, deadline + 20, 3, operator_text)
    report2 = verify_grounding(answer2, [c["result"] for c in trace], question)
    consistent2, problem2 = check_claim_consistency(answer2, trace)
    if not consistent2:
        report2 = GroundingReport(ok=False, ungrounded=report2.ungrounded + [f"inconsistent verdict: {problem2}"],
                                  checked=report2.checked, unknown_ids=report2.unknown_ids)
    return answer2, trace, report2, True


# =========================================================================== #
# Fallback path (deterministic)
# =========================================================================== #
_COMPARE_RE = re.compile(r"\b(compare|comparison|vs\.?|versus|difference)\b|قارن|مقارنة|مقابل|الفرق", re.IGNORECASE)
_WHY_RE = re.compile(r"\b(why|how come|explain|reason)\b|ليه|لماذا|ليش|ازاي|إزاي|اشرح", re.IGNORECASE)
_O2_RE = re.compile(r"(\d+(?:[.٫]\d+)?)\s*(?:%|٪|percent)\s*(?:o2|o₂|oxygen|أكسجين|اكسجين)?", re.IGNORECASE)
_O2_RE2 = re.compile(r"(?:o2|o₂|oxygen|أكسجين|اكسجين)\s*(?:of|=|at|:)?\s*(\d+(?:[.٫]\d+)?)", re.IGNORECASE)
_P_RE = re.compile(r"(\d+(?:[.٫]\d+)?)\s*(psia|psi|kpa|atm|bar|mmhg|torr)\b", re.IGNORECASE)
_FLOW_RE = re.compile(r"(\d+(?:[.٫]\d+)?)\s*(cm/s|mm/s|m/s)", re.IGNORECASE)
_GRAV_WORDS = [
    (r"\b(mars|martian)\b|المريخ|مريخ", "mars"),
    (r"\b(lunar|moon)\b|1/6\s*g|القمر|قمر", "lunar"),
    (r"\b(earth|1\s*g|terrestrial)\b|الأرض|الارض", "earth"),
]


def parse_intent(q: str) -> dict[str, Any]:
    low = q.lower()
    intent: dict[str, Any] = {"presets": [], "notes": []}
    found = []
    for canonical, aliases in tools.PRESET_ALIASES.items():
        for a in [canonical.lower(), *aliases]:
            m = re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", low)
            if m:
                found.append((m.start(), canonical))
                break
    intent["presets"] = [c for _, c in sorted(found)]
    intent["material_text"] = None
    known = tools.known_materials()
    intent["material"] = tools.find_material_in_text(q, known)
    if intent["material"] is None:
        m = re.search(r"\b(?i:is|of|for|material|about)\s+([A-Z][\w\-]+)", q)
        if m and m.group(1).lower() not in {"it", "this", "the", "my", "a", "an", "iss", "artemis", "lunar", "mars", "moon", "earth", "nasa", "orion", "gateway", "ventilation", "o2", "oxygen", "exploration"}:
            intent["material_text"] = m.group(1)
    m = _O2_RE.search(q) or _O2_RE2.search(q)
    intent["o2"] = m.group(1) + "%" if m else None
    m = _P_RE.search(q)
    intent["pressure"] = f"{m.group(1)} {m.group(2)}" if m else None
    m = _FLOW_RE.search(q)
    intent["flow"] = f"{m.group(1)} {m.group(2)}" if m else None
    intent["fans_off"] = tools.is_fans_off(q)
    intent["gravity"] = next((g for pat, g in _GRAV_WORDS if re.search(pat, low)), None)
    intent["compare"] = bool(_COMPARE_RE.search(q))
    intent["why"] = bool(_WHY_RE.search(q))
    intent["arabic"] = bool(re.search(r"[؀-ۿ]", q))
    return intent


def _call(name: str, args: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    t0 = time.perf_counter()
    r = tools.dispatch(name, args)
    trace.append({"name": name, "args": args, "result": r, "ms": round((time.perf_counter() - t0) * 1000, 1)})
    return r


def _fmt_interval(iv: Any, unit: str = "") -> str:
    if isinstance(iv, (list, tuple)) and len(iv) == 2 and all(isinstance(x, (int, float)) for x in iv):
        return f"{iv[0]:g}–{iv[1]:g}{unit}"
    return "n/a"


def _scenario_label(inp: dict[str, Any]) -> str:
    bits = []
    if inp.get("preset"):
        bits.append(inp["preset"])
    if inp.get("o2_percent") is not None:
        bits.append(f"{inp['o2_percent']:g}% O2")
    if inp.get("pressure_psia") is not None:
        bits.append(f"{inp['pressure_psia']:g} psia")
    if inp.get("flow_velocity_cm_s") is not None:
        bits.append(f"{inp['flow_velocity_cm_s']:g} cm/s flow")
    if inp.get("gravity"):
        bits.append({"micro": "µg"}.get(inp["gravity"], inp["gravity"] + " gravity"))
    return ", ".join(bits)


def _evidence_lines(near: dict[str, Any] | None) -> list[str]:
    if not near or "error" in near or not isinstance(near.get("value"), list):
        return ["No nearby experiments returned."]
    out = []
    for e in near["value"]:
        if not isinstance(e, dict):
            continue
        cond = ", ".join(
            x for x in [
                str(e.get("material", "")),
                f"{e['o2_percent']:g}% O2" if isinstance(e.get("o2_percent"), (int, float)) else "",
                f"{e['pressure_psia']:g} psia" if isinstance(e.get("pressure_psia"), (int, float)) else "",
                f"{e['flow_velocity_cm_s']:g} cm/s" if isinstance(e.get("flow_velocity_cm_s"), (int, float)) else "",
            ] if x
        )
        src = e.get("campaign") or (f"{e['pi']}, Table {e['pi_table']}, p. {e['source_page']}" if e.get("pi") else "?")
        out.append(f"- {e.get('id', '?')} ({src}; {cond}) → {e.get('outcome', '?')}")
    return out or ["No nearby experiments returned."]


def _render(sections: list[tuple[str, list[str] | str]], ood: bool, reasons: list[str]) -> str:
    lines = []
    if ood:
        lines += [f"{OOD_PREFIX} {'; '.join(reasons)}", "Treat every number below as an extrapolation, not a validated prediction.", ""]
    for title, body in sections:
        lines.append(f"**{title}**")
        lines += body if isinstance(body, list) else [body]
        lines.append("")
    return "\n".join(lines).strip()


def _limits(trace: list[dict[str, Any]], extra: list[str] | None = None, verdict: bool = True) -> list[str]:
    out = list(extra or [])
    results = [c["result"] for c in trace if isinstance(c.get("result"), dict)]
    if any("mock" in str(r.get("source", "")).lower() or r.get("backend") == "mock" for r in results):
        out.append("Numbers come from a placeholder mock model (synthetic, not NASA data) until the Layer 1 API is connected.")
    if any(r.get("coverage") == "partial" for r in results):
        out.append("Partial training coverage here: intervals are wider than for ISS-like conditions.")
    if any(r.get("coverage") == "extrapolation" or r.get("ood_level") == "extrapolation" for r in results):
        out.append("Extrapolation: the condition is far from the labelled NASA tests, so P(burn) is not supported by data there.")
    if any(r.get("backend") == "real" for r in results):
        out.append("Model scope: the five BASS-II materials (SIBAL fabric, PMMA film, PMMA slab, PMMA rod, Nomex), ISS "
                   "microgravity at 1 atm only (NASA/TM-20210011385); spread rate only for PMMA slabs (Table 5.1).")
    if verdict:
        out.append(SAFETY_DISCLAIMER)
    return [f"- {x}" for x in out]


def _fallback_why(q: str, trace: list[dict[str, Any]]) -> list[tuple[str, list[str] | str]]:
    r = _call("get_background_fact", {"topic": q}, trace)
    if "error" in r:
        r = _call("get_background_fact", {"topic": "microgravity_flame_shape"}, trace)
    facts = r.get("matches", [])
    body = [f"- {f['fact']}" for f in facts]
    srcs = [f"- {f['source']}" + (" (pending team verification)" if not f.get("verified") else "") for f in facts]
    return [("Answer", body or ["No curated fact matches this question."]), ("Sources", srcs or ["-"])]


def _fallback_boundary_block(args: dict[str, Any], trace: list[dict[str, Any]], label: str | None = None) -> tuple[list[str], list[str], str]:
    """Returns (verdict lines, key-number lines, status: flammable|nonflammable|unknown)."""
    b = _call("flammability_boundary", args, trace)
    tag = f"{label}: " if label else ""
    if "error" in b:
        return [f"{tag}No boundary available: {b['error']['message']}"], [], "unknown"
    if b.get("value") is None:
        return [f"{tag}No prediction: {b.get('ood_reason')}. Known materials: {', '.join(b.get('known_materials', []))}."], [], "unknown"
    inp = b.get("inputs_normalized", {})
    mat = inp.get("material", "material")
    key = []
    lim, flow_at = b.get("min_o2_percent_limit"), b.get("flow_at_min_limit_cm_s")
    statuses_b = {p.get("limit_status") for p in b["value"] if isinstance(p, dict)}
    if lim is not None and "limit_status" in str(b["value"][:1]):
        lowest = next((p for p in b["value"] if p.get("flow_velocity_cm_s") == flow_at), {})
        if lowest.get("limit_status") == "burns_at_all_tested_o2":
            key.append(f"- {tag}At {flow_at:g} cm/s, P(burn) is already ≥ 0.5 at the lowest modeled O2 ({lim:g}%).")
        else:
            key.append(f"- {tag}Lowest O2 where P(burn) ≥ 0.5 for {mat}: {lim:g}% at {flow_at:g} cm/s, {inp.get('pressure_psia', 0):g} psia.")
        if "no_burn_in_tested_o2" in statuses_b:
            nb = [p["flow_velocity_cm_s"] for p in b["value"] if p.get("limit_status") == "no_burn_in_tested_o2"]
            key.append(f"- {tag}P(burn) < 0.5 across the whole modeled O2 range for flows {', '.join(f'{x:g}' for x in nb)} cm/s (low-flow quenching side).")
    elif lim is not None:
        band = ""
        try:
            idx = [p["flow_velocity_cm_s"] for p in b["value"]].index(flow_at)
            band = f" (90% band {_fmt_interval(b['interval'][idx], '%')})"
        except (ValueError, KeyError, IndexError, TypeError):
            pass
        key.append(f"- {tag}Minimum limiting O2 for {mat}: {lim:g}%{band} at {flow_at:g} cm/s flow, {inp.get('pressure_psia', 0):g} psia.")
    if b.get("at_o2_percent") is None:
        return [f"{tag}{mat}: flammability boundary computed (no cabin O2 given to compare against)."], key, "unknown"
    o2 = b["at_o2_percent"]
    flows = b.get("flows_where_flammable_cm_s") or []
    if b.get("flammable_at_some_flow") is None:
        return [f"{tag}**No verdict for {mat} at {o2:g}% O2**: every modeled flow is outside or far from the labelled NASA data."], key, "unknown"
    if b.get("flammable_at_some_flow"):
        verdict = f"{tag}**{mat} is FLAMMABLE** at {o2:g}% O2 for modeled flows from {min(flows):g} to {max(flows):g} cm/s."
        status = "flammable"
        nf = b.get("flows_where_not_flammable_cm_s") or []
        if nf and "limit_status" in str(b["value"][:1]):
            verdict += f" Predicted to self-extinguish at {', '.join(f'{x:g}' for x in nf)} cm/s."
    else:
        why = (f"{o2:g}% O2 is below its minimum limiting O2 of {lim:g}%" if lim is not None
               else f"P(burn) < 0.5 at {o2:g}% O2 at every modeled flow inside its data")
        verdict = f"{tag}**{mat} is not flammable at any modeled flow**: {why}."
        status = "nonflammable"
    return [verdict], key, status


def _fallback_predict_block(args: dict[str, Any], trace: list[dict[str, Any]]) -> tuple[list[str], list[str], str]:
    r = _call("predict", args, trace)
    if "error" in r:
        return [f"No prediction: {r['error']['message']}"], [], "unknown"
    inp = r.get("inputs_normalized", {})
    if r.get("value") is None and r.get("label") is None:
        return [f"No prediction: {r.get('ood_reason')}. Known materials: {', '.join(r.get('known_materials', []))}."], [], "unknown"
    if r.get("label") is None:
        return [f"No prediction at {_scenario_label(inp)}: {r.get('note') or 'outside the tested conditions'}"], [], "unknown"
    label = str(r.get("label", "?"))
    if label == "uncertain":
        verdict = (f"**UNCERTAIN for {inp.get('material')}** at {_scenario_label(inp)}: too far from the labelled NASA tests "
                   "for a burn/extinguish verdict.")
    else:
        verdict = f"**{inp.get('material')} is predicted to {label.upper()}** at {_scenario_label(inp)}."
    key = []
    if r.get("burn_probability") is not None:
        key.append(f"- Burn probability P(burn): {r['burn_probability']:g} (90% interval {_fmt_interval(r.get('burn_probability_interval'))})")
        if r.get("ood_level") == "extrapolation":
            key.append("- This point is far from the labelled NASA tests: a P(burn) near 0.5 here means 'no information', not '50% risk'.")
    if r.get("value") is not None and r.get("unit") == "mm/s":
        key.append(f"- Flame spread rate: {r['value']:g} mm/s (90% interval {_fmt_interval(r.get('interval'), ' mm/s')})")
    elif "spread_rate_reason" in r:
        key.append(f"- Flame spread rate: not predicted ({r['spread_rate_reason']}).")
    if r.get("limiting_o2_percent") is not None:
        key.append(f"- Limiting O2 at this flow: {r['limiting_o2_percent']:g}% (margin {r.get('o2_margin_percent_points', 0):g} percentage points)")
    return [verdict], key, {"burn": "flammable", "extinguish": "nonflammable"}.get(label, "unknown")


def _recommendation(status: str, ood: bool, fans_off: bool, trace: list[dict[str, Any]]) -> list[str]:
    rec = []
    if ood:
        rec.append("- Do not use this output for a go/no-go decision; it is outside the validated data. Apply the most conservative material controls and request testing.")
    if status == "flammable":
        rec.append("- Treat the material as flammable in this atmosphere: minimize exposed quantity and keep it away from ignition sources.")
        if fans_off:
            # No verified claim says what ventilation shutdown does; our data do not measure residual flow with fans off.
            rec.append("- The residual flow with fans off is not measured in our data, so the model cannot say whether a flame "
                       "would quench: treat that case as unknown and keep the other controls in place.")
    elif status == "nonflammable":
        rec.append("- Predicted to self-extinguish under these conditions; margin shrinks if O2 rises or pressure drops, so re-check after any atmosphere change.")
    else:
        rec.append("- No reliable prediction: treat as unknown and default to conservative controls until data or testing is available.")
    return rec


def fallback_answer(question: str, trace: list[dict[str, Any]] | None = None) -> tuple[str, list[dict[str, Any]]]:
    trace = [] if trace is None else trace
    it = parse_intent(question)
    assumptions: list[str] = []

    if it["why"] and not (it["material"] or it["presets"] or it["o2"] or it["material_text"]):
        return _render(_fallback_why(question, trace), False, []), trace

    material = it["material"] or it["material_text"]
    materials = [material] if material else tools.known_materials()
    if not material:
        assumptions.append("No material specified: showing every material in the model.")
    presets = it["presets"]
    if not presets and not (it["o2"] or it["pressure"]):
        presets = ["ISS cabin"]
        assumptions.append("No atmosphere specified: assuming the ISS cabin preset.")

    base: dict[str, Any] = {}
    if it["o2"]:
        base["o2_percent"] = it["o2"]
    if it["pressure"]:
        base["pressure_psia"] = it["pressure"]
    if it["gravity"]:
        base["gravity"] = it["gravity"]
    if (it["o2"] is None or it["pressure"] is None) and not presets:
        presets = ["ISS cabin"]
        assumptions.append("Missing O2 or pressure: filling the rest from the ISS cabin preset.")

    flow: Any = it["flow"]
    if it["fans_off"] and not flow:
        f = _call("predict", {**base, "preset": presets[0] if presets else None, "material": materials[0], "flow_velocity_cm_s": "fans off"}, trace)
        if "error" in f and f["error"]["type"] == "fans_off_undefined":
            assumptions.append("'Fans off' has no agreed flow value yet (Flammability Map constant missing): showing the full low-flow boundary instead of guessing a flow.")
            trace.pop()  # the failed probe is reported via the assumption line, not as evidence
        else:
            trace.pop()
            flow = "fans off"

    verdict: list[str] = []
    key: list[str] = []
    statuses: list[str] = []
    scen_presets = presets if (it["compare"] and len(presets) >= 2) else (presets[:1] or [None])

    if flow and it["compare"] and len(scen_presets) >= 2 and material:
        scen = [{"preset": p, **base, "flow_velocity_cm_s": flow} for p in scen_presets]
        c = _call("compare_scenarios", {"material": material, "scenarios": scen}, trace)
        if "error" in c:
            verdict.append(f"Comparison unavailable: {c['error']['message']}")
            statuses.append("unknown")
        else:
            for r in c.get("value", []):
                inp = next((x for x in c.get("inputs_normalized", []) if x.get("label") == r.get("scenario")), {})
                lab = str(r["label"]).upper() if r.get("label") else "NO PREDICTION (outside the tested conditions)"
                verdict.append(f"- {r.get('scenario')}: **{lab}** ({_scenario_label(inp)})")
                if r.get("value") is not None and r.get("unit") == "mm/s":
                    key.append(f"- {r.get('scenario')}: spread {r['value']:g} mm/s (90% interval {_fmt_interval(r.get('interval'), ' mm/s')}), burn probability {r.get('burn_probability', 0):g}")
                elif r.get("burn_probability") is not None:
                    key.append(f"- {r.get('scenario')}: P(burn) {r['burn_probability']:g} (90% interval {_fmt_interval(r.get('burn_probability_interval'))})")
                statuses.append({"burn": "flammable", "extinguish": "nonflammable"}.get(r.get("label"), "unknown"))
            for d in c.get("deltas", []):
                names = {"spread_rate_delta_mm_s": "spread-rate change (mm/s)", "spread_rate_ratio": "spread-rate ratio", "burn_probability_delta": "burn-probability change"}
                parts = [f"{names.get(k, k.replace('_', ' '))} {v:+g}" if k.endswith("delta") or "delta_" in k else f"{names.get(k, k)} {v:g}" for k, v in d.items() if isinstance(v, (int, float))]
                if parts:
                    key.append(f"- {d.get('scenario')} vs {d.get('vs')}: " + ", ".join(parts))
    else:
        for p in scen_presets:
            for mat in materials:
                args = {**base, "material": mat}
                if p:
                    args["preset"] = p
                label = p if len(scen_presets) > 1 else None
                if flow:
                    v, k, s = _fallback_predict_block({**args, "flow_velocity_cm_s": flow}, trace)
                else:
                    if "o2_percent" not in args and p:
                        pr = tools.get_mission_preset(p)
                        args["o2_percent"] = pr.get("o2_percent")
                    v, k, s = _fallback_boundary_block(args, trace, label)
                verdict += v
                key += k
                statuses.append(s)

    # Evidence for the first scenario
    near_args: dict[str, Any] = {**base, "material": materials[0], "k": 3}
    if scen_presets and scen_presets[0]:
        near_args["preset"] = scen_presets[0]
    if flow and flow != "fans off":
        near_args["flow_velocity_cm_s"] = flow
    near = _call("nearest_experiments", near_args, trace)

    ood, reasons = collect_ood(trace)
    status = "flammable" if "flammable" in statuses else ("nonflammable" if statuses and all(s == "nonflammable" for s in statuses) else "unknown")
    sections: list[tuple[str, list[str] | str]] = []
    if assumptions:
        sections.append(("Assumptions", [f"- {a}" for a in assumptions]))
    sections += [
        ("Verdict", verdict or ["No verdict available."]),
        ("Key numbers", key or ["- No numeric prediction available for this input."]),
        ("Evidence", _evidence_lines(near)),
        ("Operational recommendation", _recommendation(status, ood, it["fans_off"], trace)),
        ("Limits", _limits(trace)),
    ]
    if it["why"]:
        bg = _call("get_background_fact", {"topic": question}, trace)
        if "matches" in bg:
            sections.insert(len(sections) - 1, ("Background", [f"- {f['fact']} ({f['source']}" + ("" if f.get("verified") else ", pending verification") + ")" for f in bg["matches"][:2]]))
    answer = _render(sections, ood, reasons)
    if it["arabic"]:
        answer = "_(Fallback mode: deterministic template, English only.)_\n\n" + answer
    return answer, trace


_STATES_ASSUMPTION_RE = re.compile(r"assum|\?|؟|افترض|افتراض|which material|what material|clarify|please (specify|provide)", re.IGNORECASE)


def enforce_assumption_line(question: str, answer: str, trace: list[dict[str, Any]]) -> tuple[str, bool]:
    """Code guard: if the operator named no material and no atmosphere, the answer must say what was assumed.

    Built only from the arguments the tools were actually called with (never invented). Returns (answer, added?)."""
    it = parse_intent(question)
    if it["material"] or it["material_text"] or it["presets"] or it["o2"] or it["pressure"]:
        return answer, False
    if _STATES_ASSUMPTION_RE.search(answer):
        return answer, False
    mats = list(dict.fromkeys(str(c["args"]["material"]) for c in trace if isinstance(c.get("args"), dict) and c["args"].get("material")))
    presets = list(dict.fromkeys(str(c["args"]["preset"]) for c in trace if isinstance(c.get("args"), dict) and c["args"].get("preset")))
    if not mats and not presets:
        return answer, False
    used = "; ".join(x for x in (f"material: {', '.join(mats)}" if mats else "", f"atmosphere preset: {', '.join(presets)}" if presets else "") if x)
    line = f"**Assumption:** your question named no material or atmosphere, so the tools were run with {used}. Ask again with your own conditions to change this."
    lines = answer.splitlines()
    if lines and _first_line_plain(answer).startswith(OOD_PREFIX):
        idx = next(i for i, ln in enumerate(lines) if ln.strip())
        return "\n".join(lines[: idx + 1] + ["", line] + lines[idx + 1:]), True
    return f"{line}\n\n{answer}", True


# =========================================================================== #
# Public API
# =========================================================================== #
def _finalize(answer: str, trace: list[dict[str, Any]], notes: list[str], question: str = "") -> tuple[str, bool, list[str]]:
    ood, reasons = collect_ood(trace)
    answer, prepended = enforce_ood_first_line(answer, ood, reasons)
    answer, assumed = enforce_assumption_line(question, answer, trace)
    if assumed:
        notes.append("assumption line added by code guard")
    if prepended:
        notes.append("OOD warning prepended by code guard")
    results = [c.get("result") for c in trace if isinstance(c.get("result"), dict)]
    uses_mock = any(r.get("backend") == "mock" or "mock" in str(r.get("source", "")).lower() for r in results)
    if uses_mock and not re.search(r"mock|placeholder|synthetic", answer, re.IGNORECASE):
        answer = f"{answer}\n\n{MOCK_DISCLOSURE}"
    return answer, ood, reasons


def ask(question: str, history: list[dict[str, Any]] | None = None, *, force_fallback: bool = False) -> CopilotResult:
    """Answer an operator question through the tools. Never raises for normal inputs."""
    t0 = time.perf_counter()
    question = (question or "").strip()
    notes: list[str] = []
    backend = tools.backend_name()
    if tools.BACKEND.load_error and backend == "unavailable":
        notes.append("src/api.py could not be imported: prediction tools return engine_unavailable")
    if not question:
        return CopilotResult(answer="Ask a question about material flammability (e.g. 'Will SIBAL fabric burn at 17.5% O2, 14.7 psia and 4 cm/s?').", backend=backend, notes=notes)

    key = None if (force_fallback or os.environ.get("COPILOT_FORCE_FALLBACK") == "1") else get_api_key()
    if key:
        for key_label, k, model in llm_attempts(key, get_backup_api_key(), get_model(), get_fallback_model()):
            try:
                answer, trace, report, regenerated = _llm_answer(question, history, k, model, notes)
            except LLMUnavailable as e:
                notes.append(f"LLM unavailable ({key_label}): {e}")
                continue
            except Exception as e:  # noqa: BLE001 - SDK/import errors must not kill the demo
                notes.append(f"LLM error: {type(e).__name__}")
                break
            if regenerated:
                notes.append("answer regenerated after grounding feedback")
            if not report.ok:
                # Still ungrounded after one regeneration: show fallback-formatted tool outputs instead.
                fb, fb_trace = fallback_answer(question)
                fb, ood, reasons = _finalize(fb, fb_trace, notes, question)
                notes.append("LLM answer withheld (ungrounded numbers); showing deterministic tool outputs")
                return CopilotResult(
                    answer=fb, tool_calls=trace + fb_trace, ood=ood, ood_reasons=reasons, grounding_ok=False, mode="fallback",
                    latency_ms=round((time.perf_counter() - t0) * 1000), model=model, backend=backend,
                    ungrounded=report.ungrounded + report.unknown_ids, notes=notes,
                    claims_consistent=not any(u.startswith("inconsistent verdict") for u in report.ungrounded),
                )
            answer, ood, reasons = _finalize(answer, trace, notes, question)
            return CopilotResult(
                answer=answer, tool_calls=trace, ood=ood, ood_reasons=reasons, grounding_ok=True, mode="llm",
                latency_ms=round((time.perf_counter() - t0) * 1000), model=model, backend=backend, notes=notes,
            )
    elif not force_fallback and os.environ.get("COPILOT_FORCE_FALLBACK") != "1":
        notes.append("no GEMINI_API_KEY found: fallback mode")

    answer, trace = fallback_answer(question)
    answer, ood, reasons = _finalize(answer, trace, notes, question)
    report = verify_grounding(answer, [c["result"] for c in trace], question)
    consistent, problem = check_claim_consistency(answer, trace)
    if not consistent:
        notes.append("fallback claim-consistency check: " + problem)
    if not report.ok:
        notes.append("fallback self-check found ungrounded numbers: " + ", ".join(report.ungrounded + report.unknown_ids))
    return CopilotResult(
        answer=answer, tool_calls=trace, ood=ood, ood_reasons=reasons, grounding_ok=report.ok, mode="fallback",
        latency_ms=round((time.perf_counter() - t0) * 1000), model=None, backend=backend,
        ungrounded=report.ungrounded + report.unknown_ids, notes=notes, claims_consistent=consistent,
    )


# =========================================================================== #
# CLI
# =========================================================================== #
def _summarize(r: Any) -> str:
    if not isinstance(r, dict):
        return str(r)[:160]
    if "error" in r:
        return f"ERROR {r['error'].get('type', '')}: {r['error'].get('message', '')}"
    out = []
    for k in ("name", "label", "burn_probability", "value", "interval", "min_o2_percent_limit", "flammable_at_some_flow", "matches", "ood_flag", "ood_reason"):
        if k in r and r[k] is not None:
            v = r[k]
            if isinstance(v, list) and (len(v) > 2 or (v and isinstance(v[0], (list, dict)))):
                v = f"[{len(v)} items]"
            out.append(f"{k}={v}")
    return ", ".join(out)


def _print_result(res: CopilotResult) -> None:
    bar = "─" * 72
    badges = [
        f"mode={res.mode.upper()}" + (f" ({res.model})" if res.model else ""),
        "OOD ⚠️" if res.ood else "in-distribution",
        "grounding ✅" if res.grounding_ok else "grounding ❌",
        f"backend={res.backend}",
        f"{res.latency_ms} ms",
    ]
    print(bar)
    print(res.answer)
    print(bar)
    print(" | ".join(badges))
    print(f"\nTool trace ({len(res.tool_calls)} calls):")
    for i, c in enumerate(res.tool_calls, 1):
        r = c["result"]
        summary = _summarize(r)
        print(f"  {i}. {c['name']}({json.dumps(c['args'], ensure_ascii=False)})  [{c['ms']} ms]")
        print(f"     → {summary}")
    if res.notes:
        print("\nNotes: " + " | ".join(res.notes))
    if res.ungrounded:
        print("Ungrounded: " + ", ".join(res.ungrounded))


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m src.copilot", description="FlameMargin Fire Safety Copilot")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--fallback", action="store_true", help="force the deterministic (no-LLM) path")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    a = ap.parse_args(argv)
    res = ask(" ".join(a.question), force_fallback=a.fallback)
    if a.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_result(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
