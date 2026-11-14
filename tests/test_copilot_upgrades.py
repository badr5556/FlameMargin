"""Copilot on the real engine + upgrades: key rotation, session budget, claim consistency, no silent mock."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google.genai import errors as genai_errors  # noqa: E402
from google.genai import types  # noqa: E402

from src import copilot, copilot_tools  # noqa: E402


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("COPILOT_FORCE_MOCK_API", "GEMINI_API_KEY", "GEMINI_API_KEY_BACKUP", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL",
              "COPILOT_FORCE_FALLBACK", "COPILOT_SESSION_LLM_LIMIT", "FLAMEMARGIN_FANS_OFF_FLOW_CM_S"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(copilot, "REPO_ROOT", ROOT / "tests" / "_no_env_here")
    monkeypatch.setattr(copilot.time, "sleep", lambda *_: None)
    copilot_tools.BACKEND.reset()
    yield
    copilot_tools.BACKEND.reset()


def _text(t: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=t)]))])


def _calls(*calls: tuple[str, dict[str, Any]]) -> types.GenerateContentResponse:
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a, id=f"c{i}")) for i, (n, a) in enumerate(calls)]
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


class _Client:
    def __init__(self, script: list[Any]):
        self.script, self.calls = list(script), []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


def _rate_limited() -> Exception:
    return genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})


IN_DATA = {"material": "SIBAL", "o2_percent": 17.5, "pressure_psia": 14.7, "flow_velocity_cm_s": 4}
IN_DATA_Q = "Will SIBAL fabric keep burning at 17.5% O2 and 14.7 psia with 4 cm/s flow?"


# --------------------------------------------------------------------------- #
# Real backend
# --------------------------------------------------------------------------- #
def test_real_engine_is_picked_up_automatically():
    assert copilot_tools.backend_name() == "real"
    assert copilot_tools.known_materials() == ["SIBAL"]


def test_engine_unavailable_is_an_error_not_synthetic_numbers(monkeypatch):
    import importlib

    real_import = importlib.import_module

    def fake_import(name, *a, **k):
        if name in ("src.api", "api"):
            raise ImportError("simulated")
        return real_import(name, *a, **k)

    monkeypatch.setattr(copilot_tools.importlib, "import_module", fake_import)
    copilot_tools.BACKEND.reset()
    assert copilot_tools.backend_name() == "unavailable"
    r = copilot_tools.dispatch("predict", IN_DATA)
    assert r["error"]["type"] == "engine_unavailable"


def test_material_aliases_resolve_to_sibal_and_others_are_unknown():
    assert copilot_tools.dispatch("predict", {**IN_DATA, "material": "cotton-fiberglass"})["inputs_normalized"]["material"] == "SIBAL"
    r = copilot_tools.dispatch("predict", {**IN_DATA, "material": "Nomex"})
    assert r["ood_flag"] and r["value"] is None and "not in training data" in r["ood_reason"]


def test_iss_boundary_is_flagged_and_gives_no_verdict():
    r = copilot_tools.dispatch("flammability_boundary", {"material": "SIBAL", "preset": "ISS"})
    assert r["ood_flag"] and r["flammable_at_some_flow"] is None
    assert r["flows_extrapolated_cm_s"]


def test_artemis_and_lunar_presets_are_ood():
    for preset in ("Artemis", "lunar"):
        r = copilot_tools.dispatch("predict", {"material": "SIBAL", "preset": preset, "flow_velocity_cm_s": 20})
        assert r["ood_flag"] and r["burn_probability"] is None


def test_fallback_on_real_engine_is_grounded_and_in_distribution():
    res = copilot.ask(IN_DATA_Q, force_fallback=True)
    assert res.backend == "real" and res.grounding_ok and not res.ood and res.claims_consistent
    assert "GMT" in res.answer and "spread" in res.answer.lower()


@pytest.mark.parametrize("q", [
    "Is SIBAL fabric flammable in the ISS cabin atmosphere?",
    "Is SIBAL fabric safe in the Artemis atmosphere with fans off?",
    "Is SIBAL fabric safe in the lunar surface habitat at 10 cm/s?",
    "Is Kapton tape safe in the Artemis atmosphere at 10 cm/s?",
])
def test_fallback_flags_ood_first(q):
    res = copilot.ask(q, force_fallback=True)
    assert res.ood and copilot._first_line_plain(res.answer).startswith(copilot.OOD_PREFIX)
    assert res.grounding_ok


def test_fabricated_nasa_test_id_is_caught():
    r = copilot_tools.dispatch("predict", IN_DATA)
    rep = copilot.verify_grounding("Supported by GMT999-T42.", [r])
    assert not rep.ok and "GMT999-T42" in rep.unknown_ids
    assert copilot.verify_grounding(f"Supported by {r['evidence'][0]}.", [r]).ok


# --------------------------------------------------------------------------- #
# Backup key rotation
# --------------------------------------------------------------------------- #
def test_attempt_order_backup_key_before_backup_model():
    a = copilot.llm_attempts("k1", "k2", "m1", "m2")
    assert [(lbl, m) for lbl, _, m in a] == [("primary key", "m1"), ("backup key", "m1"), ("primary key", "m2"), ("backup key", "m2")]
    assert [(lbl, m) for lbl, _, m in copilot.llm_attempts("k1", None, "m1", "m1")] == [("primary key", "m1")]


def test_backup_key_is_used_when_primary_is_rate_limited(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "primary-dummy")
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", "backup-dummy")
    r = copilot_tools.dispatch("predict", IN_DATA)
    near = copilot_tools.dispatch("nearest_experiments", {**IN_DATA, "k": 3})
    good = (f"**Verdict**\nSIBAL is predicted to burn.\n**Key numbers**\nP(burn) {r['burn_probability']}.\n"
            f"**Evidence**\n{near['evidence'][0]}\n**Operational recommendation**\nLimit material.\n**Limits**\nNot a replacement for NASA-STD-6001.")
    primary = _Client([_rate_limited()])
    backup = _Client([_calls(("predict", IN_DATA), ("nearest_experiments", {**IN_DATA, "k": 3})), _text(good)])
    monkeypatch.setattr(copilot, "_get_client", lambda key: {"primary-dummy": primary, "backup-dummy": backup}[key])
    res = copilot.ask(IN_DATA_Q)
    assert res.mode == "llm" and res.grounding_ok
    assert primary.calls and backup.calls and set(backup.calls) == {copilot.get_model()}
    assert any("primary key" in n for n in res.notes)
    assert "primary-dummy" not in " ".join(res.notes) and "backup-dummy" not in " ".join(res.notes)


# --------------------------------------------------------------------------- #
# Session budget
# --------------------------------------------------------------------------- #
def test_session_llm_limit(monkeypatch):
    assert copilot.session_llm_limit() == 15
    monkeypatch.setenv("COPILOT_SESSION_LLM_LIMIT", "3")
    assert copilot.session_llm_limit() == 3
    monkeypatch.setenv("COPILOT_SESSION_LLM_LIMIT", "lots")
    assert copilot.session_llm_limit() == 15


def test_ui_enforces_the_session_budget(monkeypatch):
    """Drive render_copilot_chat with a fake Streamlit: after the limit, questions go to the fallback."""
    from src import copilot_ui

    seen: list[bool] = []

    def fake_ask(q, history=None, force_fallback=False):
        seen.append(force_fallback)
        return copilot.CopilotResult(answer="ok", mode="fallback" if force_fallback else "llm")

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeSt:
        def __init__(self):
            self.session_state: dict[str, Any] = {}
            self.q = None

        def columns(self, n):
            return [Ctx_with(self) for _ in range(n if isinstance(n, int) else len(n))]

        def __getattr__(self, name):
            return lambda *a, **k: Ctx() if name in ("chat_message", "spinner", "expander") else None

        def chat_input(self, *a, **k):
            return self.q

    def Ctx_with(st):
        c = Ctx()
        c.button = lambda *a, **k: False
        c.toggle = lambda *a, **k: False
        c.markdown = c.caption = lambda *a, **k: None
        return c

    fake = FakeSt()
    monkeypatch.setattr(copilot_ui, "st", fake)
    monkeypatch.setattr(copilot_ui, "ask", fake_ask)
    monkeypatch.setattr(copilot_ui, "get_api_key", lambda: "dummy")
    monkeypatch.setattr(copilot_ui, "session_llm_limit", lambda: 2)
    for i in range(4):
        fake.q = f"question {i}"
        copilot_ui.render_copilot_chat()
    assert seen == [False, False, True, True]
    assert fake.session_state["copilot_llm_used"] == 2
    assert "budget" in fake.session_state["copilot_history"][-1]["content"]


# --------------------------------------------------------------------------- #
# Claim consistency
# --------------------------------------------------------------------------- #
def _trace(label: str) -> list[dict[str, Any]]:
    return [{"name": "predict", "result": {"label": label, "ood_flag": False}}]


@pytest.mark.parametrize("answer,label,ok", [
    ("**Verdict**\nSIBAL will burn here.\n**Key numbers**\n-", "extinguish", False),
    ("**Verdict**\nSIBAL is predicted to self-extinguish.\n**Key numbers**\n-", "burn", False),
    ("**Verdict**\nSIBAL is predicted to BURN.\n**Key numbers**\nIt will not self-extinguish quickly", "burn", True),
    ("**Verdict**\nSIBAL is predicted to self-extinguish.\n**Key numbers**\n-", "extinguish", True),
    ("**Verdict**\nSIBAL will burn.\n**Key numbers**\n-", "uncertain", False),
    ("**Verdict**\nUncertain: too far from the data to say whether it will burn.", "uncertain", True),
    ("**Verdict**\nIt is not flammable here.", "extinguish", True),
])
def test_claim_consistency(answer, label, ok):
    assert copilot.check_claim_consistency(answer, _trace(label))[0] is ok


def test_inconsistent_llm_verdict_is_regenerated_then_withheld(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    r = copilot_tools.dispatch("predict", {**IN_DATA, "o2_percent": 16.5, "flow_velocity_cm_s": 7})
    assert r["label"] == "extinguish"
    bad = "**Verdict**\nSIBAL will burn.\n**Key numbers**\nnone"
    client = _Client([_calls(("predict", {**IN_DATA, "o2_percent": 16.5, "flow_velocity_cm_s": 7})), _text(bad), _text(bad)])
    monkeypatch.setattr(copilot, "_get_client", lambda key: client)
    res = copilot.ask("Will SIBAL burn at 16.5% O2, 14.7 psia and 7 cm/s?")
    assert res.mode == "fallback" and not res.grounding_ok and not res.claims_consistent
    assert any("claim-consistency" in n for n in res.notes)


# --------------------------------------------------------------------------- #
# Assumption guard
# --------------------------------------------------------------------------- #
def test_silent_default_gets_an_assumption_line():
    trace = [{"name": "flammability_boundary", "args": {"preset": "ISS cabin", "material": "SIBAL"}, "result": {}}]
    out, added = copilot.enforce_assumption_line("Is it safe?", "**Verdict**\nUncertain.", trace)
    assert added and out.startswith("**Assumption:**") and "SIBAL" in out and "ISS cabin" in out
    ood = f"{copilot.OOD_PREFIX} far\n\n**Verdict**\nUncertain."
    out2, _ = copilot.enforce_assumption_line("Is it safe?", ood, trace)
    assert copilot._first_line_plain(out2).startswith(copilot.OOD_PREFIX) and "**Assumption:**" in out2
    assert copilot.enforce_assumption_line("Is SIBAL safe on the ISS?", "**Verdict**\nx", trace)[1] is False
    assert copilot.enforce_assumption_line("Is it safe?", "Which material do you mean?", trace)[1] is False
