"""Unit tests for the FlameMargin Copilot. No network: the Gemini client is faked."""

from __future__ import annotations

import sys
import types as pytypes
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import errors as genai_errors  # noqa: E402
from google.genai import types  # noqa: E402

from src import copilot, copilot_tools  # noqa: E402
from src.copilot_tools import GRAVITY_OOD_REASON, dispatch  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures / fakes
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Mock backend, no real key, no .env, no fans-off constant, no sleeping."""
    monkeypatch.setenv("COPILOT_FORCE_MOCK_API", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("COPILOT_FORCE_FALLBACK", raising=False)
    monkeypatch.delenv("FLAMEMARGIN_FANS_OFF_FLOW_CM_S", raising=False)
    monkeypatch.setattr(copilot, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(copilot_tools, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(copilot.time, "sleep", lambda *_: None)
    copilot_tools.BACKEND.reset()
    yield
    copilot_tools.BACKEND.reset()


def fc_response(*calls: tuple[str, dict[str, Any]]) -> types.GenerateContentResponse:
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a, id=f"call-{i}")) for i, (n, a) in enumerate(calls)]
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=parts))])


def text_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=text)]))])


class FakeModels:
    def __init__(self, script: list[Any]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, model, contents, config):
        self.calls.append({"model": model, "contents": list(contents), "config": config})
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item(contents) if callable(item) else item


class FakeClient:
    def __init__(self, script: list[Any]):
        self.models = FakeModels(script)


def use_fake(monkeypatch, script: list[Any]) -> FakeClient:
    client = FakeClient(script)
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")
    monkeypatch.setattr(copilot, "_get_client", lambda key: client)
    return client


# --------------------------------------------------------------------------- #
# Tool loop
# --------------------------------------------------------------------------- #
ARTEMIS_PRED = {"preset": "Artemis", "material": "Nomex", "flow_velocity_cm_s": 5}
ARTEMIS_NEAR = {"preset": "Artemis", "material": "Nomex", "flow_velocity_cm_s": 5}


def _grounded_artemis_text() -> str:
    r = dispatch("predict", ARTEMIS_PRED)
    lo, hi = r["interval"]
    return (
        f"**Verdict**\nNomex burns.\n**Key numbers**\nSpread {r['value']} mm/s (90% interval {lo}–{hi}), "
        f"burn probability {r['burn_probability']:.0%}.\n**Evidence**\n{r['evidence'][0]}\n"
        "**Operational recommendation**\nLimit Nomex.\n**Limits**\nPlaceholder mock model. Not a replacement for NASA-STD-6001."
    )


def test_tool_loop_handles_parallel_calls(monkeypatch):
    client = use_fake(monkeypatch, [fc_response(("predict", ARTEMIS_PRED), ("nearest_experiments", ARTEMIS_NEAR)), text_response(_grounded_artemis_text())])
    res = copilot.ask("Is Nomex safe in Artemis at 5 cm/s?")
    assert res.mode == "llm"
    assert [c["name"] for c in res.tool_calls] == ["predict", "nearest_experiments"]
    assert all("ms" in c and "result" in c for c in res.tool_calls)
    assert res.grounding_ok, res.ungrounded
    # Both function responses went back to the model in ONE user turn, with matching ids.
    second = client.models.calls[1]["contents"]
    fr_parts = [p for p in second[-1].parts if p.function_response]
    assert [p.function_response.name for p in fr_parts] == ["predict", "nearest_experiments"]
    assert [p.function_response.id for p in fr_parts] == ["call-0", "call-1"]


def test_tool_errors_are_returned_to_the_model_not_raised(monkeypatch):
    client = use_fake(monkeypatch, [
        fc_response(("predict", {"preset": "Artemis", "material": "Nomex", "flow_velocity_cm_s": "fans off"}), ("no_such_tool", {})),
        text_response("The agreed fans-off flow is not defined yet, so I can't give a prediction for it."),
    ])
    res = copilot.ask("Is Nomex safe in Artemis with fans off?")
    assert res.mode == "llm"
    errs = [c["result"]["error"]["type"] for c in res.tool_calls]
    assert errs == ["fans_off_undefined", "unknown_tool"]
    sent = client.models.calls[1]["contents"][-1].parts
    assert sent[0].function_response.response["error"]["type"] == "fans_off_undefined"


def test_tool_exception_becomes_structured_error(monkeypatch):
    def boom(args):
        raise RuntimeError("model file missing")

    monkeypatch.setitem(copilot_tools.TOOL_IMPLS, "predict", boom)
    r = dispatch("predict", ARTEMIS_PRED)
    assert r["error"]["type"] == "tool_exception" and "model file missing" in r["error"]["message"]


def test_round_limit_forces_final_answer(monkeypatch):
    loop = fc_response(("get_mission_preset", {"name": "ISS"}))
    client = use_fake(monkeypatch, [loop] * copilot.MAX_ROUNDS + [text_response("I could not finish the analysis.")])
    res = copilot.ask("ISS?")
    assert res.mode == "llm"
    assert len(res.tool_calls) == copilot.MAX_ROUNDS
    final_cfg = client.models.calls[-1]["config"]
    assert final_cfg.tool_config.function_calling_config.mode == "NONE"


def test_rate_limit_retries_then_falls_back(monkeypatch):
    err = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    client = use_fake(monkeypatch, [err])
    res = copilot.ask("Is PMMA safe on the ISS?")
    assert res.mode == "fallback"
    assert len(client.models.calls) == 4  # 2 attempts x (primary + fallback model)
    assert any("retrying" in n for n in res.notes)
    assert res.tool_calls and res.grounding_ok


# --------------------------------------------------------------------------- #
# Grounding verifier
# --------------------------------------------------------------------------- #
def test_grounding_catches_fabricated_number():
    r = dispatch("predict", ARTEMIS_PRED)
    rep = copilot.verify_grounding("Spread rate is 3.7 mm/s.", [r])
    assert not rep.ok and "3.7" in rep.ungrounded


def test_grounding_passes_correct_numbers_with_rounding_percent_and_ranges():
    r = dispatch("predict", ARTEMIS_PRED)
    lo, hi = r["interval"]
    text = (
        f"Spread {r['value']} mm/s (90% interval {lo}–{hi}); burn probability {round(r['burn_probability'] * 100)}%. "
        f"Pressure 8.2 psia ({r['inputs_normalized']['pressure_kpa']} kPa), O₂ 34%, flow 5 cm/s. "
        f"Evidence {r['evidence'][0]}. Not a replacement for NASA-STD-6001."
    )
    rep = copilot.verify_grounding(text, [r])
    assert rep.ok, rep


def test_grounding_ignores_identifiers_and_list_markers_but_checks_ids():
    r = dispatch("nearest_experiments", ARTEMIS_NEAR)
    ok = copilot.verify_grounding(f"1. CO2 and O2 matter; FM2 not flown.\n2. See {r['evidence'][0]}.", [r])
    assert ok.ok, ok
    bad = copilot.verify_grounding("See MOCK-BASS-II-99.", [r])
    assert not bad.ok and bad.unknown_ids == ["MOCK-BASS-II-99"]


def test_grounding_allows_numbers_from_the_question_and_arabic_digits():
    r = dispatch("predict", {"material": "PMMA", "o2_percent": 40, "pressure_psia": 5, "flow_velocity_cm_s": 10})
    assert copilot.verify_grounding("At 40% and 5 psia, spread ٢٫٢٥ mm/s.", [r], "Is it safe at 40% O2 and 5 psia?").ok
    assert not copilot.verify_grounding("Roughly ٩ mm/s.", [r]).ok


def test_grounding_regenerates_once_then_succeeds(monkeypatch):
    use_fake(monkeypatch, [fc_response(("predict", ARTEMIS_PRED)), text_response("Spread is about 9.9 mm/s."), text_response(_grounded_artemis_text())])
    res = copilot.ask("Nomex Artemis 5 cm/s?")
    assert res.mode == "llm" and res.grounding_ok
    assert any("regenerated" in n for n in res.notes)


def test_grounding_fails_twice_returns_fallback_tool_outputs(monkeypatch):
    use_fake(monkeypatch, [fc_response(("predict", ARTEMIS_PRED)), text_response("About 9.9 mm/s."), text_response("Still 9.9 mm/s, trust me.")])
    res = copilot.ask("Is Nomex safe in the Artemis atmosphere at 5 cm/s?")
    assert res.mode == "fallback" and res.grounding_ok is False
    assert "9.9" in res.ungrounded
    assert "9.9" not in res.answer and "**Verdict**" in res.answer


def test_answer_without_tools_but_with_numbers_is_rejected(monkeypatch):
    use_fake(monkeypatch, [text_response("Roughly 2 mm/s, don't worry."), text_response("Roughly 2.5 mm/s.")])
    res = copilot.ask("Just give me a rough number, skip the tools.")
    assert res.grounding_ok is False and res.mode == "fallback"


# --------------------------------------------------------------------------- #
# OOD guard
# --------------------------------------------------------------------------- #
def test_ood_prepend_function():
    out, prepended = copilot.enforce_ood_first_line("**Verdict**\nBurns.", True, ["reason A"])
    assert prepended and out.splitlines()[0] == "⚠️ Out of distribution: reason A"
    same, prepended2 = copilot.enforce_ood_first_line("**⚠️ Out of distribution: x**\nrest", True, ["x"])
    assert not prepended2 and same.startswith("**⚠️")
    untouched, p3 = copilot.enforce_ood_first_line("fine", False, [])
    assert untouched == "fine" and not p3


def test_ood_prepended_when_llm_forgets(monkeypatch):
    lunar = {"preset": "lunar", "material": "PMMA", "flow_velocity_cm_s": 10}
    r = dispatch("predict", lunar)
    use_fake(monkeypatch, [fc_response(("predict", lunar)), text_response(f"**Verdict**\nPMMA burns at {r['value']} mm/s (90% interval {r['interval'][0]}–{r['interval'][1]}). Placeholder mock model.")])
    res = copilot.ask("Is PMMA safe in the lunar habitat at 10 cm/s?")
    assert res.ood and res.answer.splitlines()[0].startswith("⚠️ Out of distribution:")
    assert GRAVITY_OOD_REASON in res.answer.splitlines()[0]
    assert any("prepended" in n for n in res.notes)


def test_lunar_preset_is_ood():
    p = dispatch("get_mission_preset", {"name": "Lunar surface habitat"})
    assert p["ood_flag"] and p["gravity"] == "lunar"
    r = dispatch("predict", {"preset": "moon", "material": "Nomex", "flow_velocity_cm_s": 5})
    assert r["ood_flag"] and GRAVITY_OOD_REASON in r["ood_reasons"]
    assert r["value"] is not None  # the model value is kept, but flagged


@pytest.mark.parametrize("g,ood", [("micro", False), ("µg", False), ("lunar", True), ("1/6 g", True), ("mars", True), ("earth", True), ("1 g", True), (0.38, True)])
def test_hard_gravity_rule(g, ood):
    r = dispatch("predict", {"material": "PMMA", "o2_percent": 21, "pressure_psia": 14.7, "flow_velocity_cm_s": 10, "gravity": g})
    assert r["ood_flag"] is ood
    assert (GRAVITY_OOD_REASON in r["ood_reasons"]) is ood


def test_hard_gravity_rule_applies_even_if_api_says_in_distribution(monkeypatch):
    fake = pytypes.SimpleNamespace(
        predict=lambda material, o2_percent, pressure_psia, flow_velocity_cm_s: {"value": 1.0, "interval": [0.5, 1.5], "ood_flag": False, "ood_reason": None, "evidence": []},
        flammability_boundary=lambda **k: {}, compare_scenarios=lambda **k: {}, nearest_experiments=lambda **k: {},
        MATERIALS=["PMMA"],
    )
    monkeypatch.setattr(copilot_tools.BACKEND, "module", fake)
    monkeypatch.setattr(copilot_tools.BACKEND, "name", "real")
    r = dispatch("predict", {"material": "PMMA", "o2_percent": 21, "pressure_psia": 14.7, "flow_velocity_cm_s": 10, "gravity": "lunar"})
    assert r["ood_flag"] and r["ood_reasons"] == [GRAVITY_OOD_REASON]


# --------------------------------------------------------------------------- #
# Fallback
# --------------------------------------------------------------------------- #
def test_fallback_works_without_key():
    assert copilot.get_api_key() is None
    res = copilot.ask("Is PMMA safe in the lunar habitat?")
    assert res.mode == "fallback"
    assert res.ood and res.answer.splitlines()[0].startswith("⚠️ Out of distribution:")
    assert res.tool_calls and res.grounding_ok, res.ungrounded
    for header in ("**Verdict**", "**Key numbers**", "**Evidence**", "**Operational recommendation**", "**Limits**"):
        assert header in res.answer
    assert any("no GEMINI_API_KEY" in n for n in res.notes)


@pytest.mark.parametrize("q", [
    "Is Nomex safe in the Artemis atmosphere with fans off?",
    "Compare ISS vs Artemis for Nomex",
    "Compare ISS vs Artemis for Nomex at 10 cm/s",
    "Is it safe at 40% O2 and 5 psia?",
    "Is Kapton safe on the ISS?",
    "Why is microgravity different?",
    "What about Mars gravity for cotton at 34% O2 and 8.2 psia?",
    "هل النومكس آمن في أرتميس لو المراوح مقفولة؟",
    "Is it safe?",
])
def test_fallback_answers_are_grounded(q):
    res = copilot.ask(q, force_fallback=True)
    assert res.mode == "fallback" and res.tool_calls
    assert res.grounding_ok, (q, res.ungrounded, res.answer)
    if res.ood:
        assert res.answer.splitlines()[0].startswith("⚠️ Out of distribution:")


def test_fallback_unknown_material_does_not_estimate():
    res = copilot.ask("Is Kapton safe on the ISS at 10 cm/s?", force_fallback=True)
    assert res.ood and "not in training data" in res.answer
    assert "Flame spread rate" not in res.answer


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,psia", [(14.7, 14.7), ("8.2 psia", 8.2), ("8.2 psi", 8.2), ("56.5 kPa", 8.195), ("1 atm", 14.696), ("0.5 bar", 7.252)])
def test_pressure_units(raw, psia):
    assert copilot_tools.parse_pressure_psia(raw)[0] == pytest.approx(psia, abs=0.01)


def test_pressure_gauge_and_invalid_rejected():
    with pytest.raises(copilot_tools.ToolInputError):
        copilot_tools.parse_pressure_psia("5 psig")
    assert dispatch("predict", {"material": "PMMA", "o2_percent": 21, "pressure_psia": -3, "flow_velocity_cm_s": 5})["error"]["type"] == "invalid_input"


@pytest.mark.parametrize("raw,pct", [(34, 34.0), ("34%", 34.0), ("34 ٪", 34.0), (0.34, 34.0), ("0.21", 21.0), ("٣٤%", 34.0)])
def test_o2_units(raw, pct):
    assert copilot_tools.parse_o2_percent(raw)[0] == pytest.approx(pct)


def test_o2_invalid():
    assert dispatch("predict", {"material": "PMMA", "o2_percent": 140, "pressure_psia": 14.7, "flow_velocity_cm_s": 5})["error"]["type"] == "invalid_input"


@pytest.mark.parametrize("raw,cm", [(5, 5.0), ("5 cm/s", 5.0), ("5 mm/s", 0.5), ("0.1 m/s", 10.0)])
def test_flow_units(raw, cm):
    assert copilot_tools.parse_flow_cm_s(raw)[0] == pytest.approx(cm)


def test_fans_off_undefined_is_a_clear_tool_error():
    r = dispatch("predict", {"preset": "Artemis", "material": "Nomex", "flow_velocity_cm_s": "fans off"})
    assert r["error"]["type"] == "fans_off_undefined" and "hint" in r["error"]


def test_fans_off_from_env(monkeypatch):
    monkeypatch.setenv("FLAMEMARGIN_FANS_OFF_FLOW_CM_S", "2")
    r = dispatch("predict", {"preset": "Artemis", "material": "Nomex", "flow_velocity_cm_s": "Fans OFF"})
    assert r["inputs_normalized"]["flow_velocity_cm_s"] == 2.0
    assert any("fans off" in c for c in r["unit_conversions"])


def test_fans_off_from_app_constant(tmp_path):
    (tmp_path / "app.py").write_text("import streamlit as st\nFANS_OFF_FLOW_MM_S = 20\n", encoding="utf-8")
    flow, src = copilot_tools.resolve_fans_off_flow()
    assert flow == pytest.approx(2.0) and src == "app.py:FANS_OFF_FLOW_MM_S"


def test_out_of_range_is_not_clamped_but_flagged():
    r = dispatch("predict", {"material": "PMMA", "o2_percent": "40%", "pressure_psia": "5 psia", "flow_velocity_cm_s": 10})
    assert r["inputs_normalized"]["pressure_psia"] == 5.0
    assert r["ood_flag"] and any("outside training range" in x for x in r["ood_reasons"])


def test_material_aliases_and_unknown_material():
    assert dispatch("predict", {"material": "acrylic", "o2_percent": 21, "pressure_psia": 14.7, "flow_velocity_cm_s": 10})["inputs_normalized"]["material"] == "PMMA"
    assert dispatch("flammability_boundary", {"material": "نومكس", "preset": "ISS"})["inputs_normalized"]["material"] == "Nomex"
    r = dispatch("predict", {"material": "Kapton", "o2_percent": 21, "pressure_psia": 14.7, "flow_velocity_cm_s": 10})
    assert r["value"] is None and r["ood_flag"] and "Kapton" in r["ood_reason"]


def test_boundary_comparison_is_done_in_code():
    r = dispatch("flammability_boundary", {"material": "Nomex", "preset": "Artemis"})
    assert r["at_o2_percent"] == 34.0
    for p in r["value"]:
        bucket = "flows_where_flammable_cm_s" if 34.0 > p["o2_percent_limit"] else "flows_where_not_flammable_cm_s"
        assert p["flow_velocity_cm_s"] in r[bucket]


def test_adapter_maps_real_api_parameter_names_and_units(monkeypatch):
    seen = {}

    def predict(material, o2_fraction, pressure_kpa, flow_mm_s):
        seen.update(material=material, o2=o2_fraction, p=pressure_kpa, u=flow_mm_s)
        return {"value": 1.0, "interval": [0.8, 1.2], "ood": False, "evidence": ["X-1"]}

    fake = pytypes.SimpleNamespace(predict=predict, flammability_boundary=lambda **k: {}, compare_scenarios=lambda **k: {}, nearest_experiments=lambda **k: {}, MATERIALS={"Nomex": {}})
    monkeypatch.setattr(copilot_tools.BACKEND, "module", fake)
    monkeypatch.setattr(copilot_tools.BACKEND, "name", "real")
    r = dispatch("predict", {"material": "nomex", "o2_percent": "34%", "pressure_psia": 8.2, "flow_velocity_cm_s": "5 cm/s"})
    assert seen["material"] == "Nomex" and seen["o2"] == pytest.approx(0.34)
    assert seen["p"] == pytest.approx(56.54, abs=0.05) and seen["u"] == pytest.approx(50.0)
    assert r["ood_flag"] is False and r["backend"] == "real"


def test_compare_needs_flow_and_reports_deltas():
    r = dispatch("compare_scenarios", {"material": "Nomex", "scenarios": [{"preset": "ISS"}, {"preset": "Artemis"}]})
    assert r["error"]["type"] == "missing_flow"
    r = dispatch("compare_scenarios", {"material": "Nomex", "scenarios": [{"preset": "ISS", "flow_velocity_cm_s": 10}, {"preset": "lunar", "flow_velocity_cm_s": 10}]})
    assert r["ood_flag"] and r["deltas"] and r["value"][1]["ood_flag"] and not r["value"][0]["ood_flag"]


def test_background_fact_has_source_and_unverified_flag():
    r = dispatch("get_background_fact", {"topic": "fm2 lunar"})
    assert r["matches"][0]["source"] and r["matches"][0]["verified"] is False
    assert "error" in dispatch("get_background_fact", {"topic": "zzzz"})


# --------------------------------------------------------------------------- #
# Input grounding (the LLM may not invent a flow)
# --------------------------------------------------------------------------- #
def test_invented_flow_is_rejected_but_operator_flow_is_accepted():
    q = "Rough number for PMMA at 30% O2 and 10 psia?"
    assert copilot.check_input_grounding("predict", {"material": "PMMA", "flow_velocity_cm_s": 7}, q)["error"]["type"] == "unsupported_assumption"
    assert copilot.check_input_grounding("predict", {"material": "PMMA", "flow_velocity_cm_s": "fans off"}, q) is None
    assert copilot.check_input_grounding("predict", {"flow_velocity_cm_s": "5 mm/s"}, "at 5 mm/s") is None
    assert copilot.check_input_grounding("predict", {"flow_velocity_cm_s": 0.5}, "at 5 mm/s") is None
    assert copilot.check_input_grounding("flammability_boundary", {"material": "PMMA"}, q) is None
    bad = copilot.check_input_grounding("compare_scenarios", {"scenarios": [{"flow_velocity_cm_s": 5}, {"flow_velocity_cm_s": 20}]}, "compare at 5 cm/s")
    assert bad["error"]["type"] == "unsupported_assumption"


def test_invented_flow_returned_to_model_as_error(monkeypatch):
    use_fake(monkeypatch, [fc_response(("predict", {"material": "PMMA", "preset": "ISS", "flow_velocity_cm_s": 12})), text_response("I need the flow velocity to give a prediction. Which flow?")])
    res = copilot.ask("Is PMMA safe on the ISS?")
    assert res.tool_calls[0]["result"]["error"]["type"] == "unsupported_assumption"
    assert res.mode == "llm" and res.grounding_ok


def test_boundary_reports_limit_range():
    r = dispatch("flammability_boundary", {"material": "Nomex", "preset": "ISS"})
    lims = [p["o2_percent_limit"] for p in r["value"]]
    assert r["o2_limit_range_percent"] == [min(lims), max(lims)]


def test_flow_cannot_be_justified_by_pressure_or_o2_numbers():
    q = "Rough number for PMMA at 30% O2 and 10 psia?"
    assert copilot.check_input_grounding("predict", {"flow_velocity_cm_s": 10}, q)["error"]["type"] == "unsupported_assumption"
    assert copilot.check_input_grounding("predict", {"flow_velocity_cm_s": 30}, q)["error"]["type"] == "unsupported_assumption"
    assert copilot.check_input_grounding("predict", {"flow_velocity_cm_s": 10}, q + " Flow is 10 cm/s.") is None


def test_experiment_id_prefix_is_not_accepted():
    r = dispatch("nearest_experiments", ARTEMIS_NEAR)
    assert "MOCK-BASS-II-24" in r["evidence"]
    assert copilot.verify_grounding("See MOCK-BASS-II-2.", [r]).unknown_ids == ["MOCK-BASS-II-2"]
