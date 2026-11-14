"""P0.2: greetings and off-topic messages get a short reply (no tools, no numbers) in both modes and both languages."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from src import copilot  # noqa: E402


def _no_llm(*a, **k):  # any LLM call is a test failure
    raise AssertionError("small talk must not call the LLM")


@pytest.fixture(params=["fallback", "llm"])
def mode(request, monkeypatch):
    if request.param == "llm":
        monkeypatch.delenv("COPILOT_FORCE_FALLBACK", raising=False)
        monkeypatch.setattr(copilot, "get_api_key", lambda: "test-key-not-real")
        monkeypatch.setattr(copilot, "_llm_answer", _no_llm)
    else:
        monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    return request.param


@pytest.mark.parametrize("q,kind", [("hi", "greeting"), ("Hello!", "greeting"), ("thanks", "greeting"),
                                    ("What can you do?", "greeting"), ("What is FlameMargin?", "greeting"),
                                    ("What's the capital of France?", "off_topic")])
def test_english_small_talk(q, kind, mode):
    r = copilot.ask(q)
    assert r.mode == "smalltalk" and r.tool_calls == []
    assert not re.search(r"\d", r.answer), "no numbers in a small-talk reply"
    assert len(r.suggestions) == 3 and all(s in r.answer for s in r.suggestions)
    assert not re.search(r"[؀-ۿ]", r.answer)
    assert any(kind in n for n in r.notes)
    assert "Verdict" not in r.answer and "P(burn)" not in r.answer


@pytest.mark.parametrize("q", ["مرحبا", "السلام عليكم، ازيك؟", "شكرا"])
def test_arabic_small_talk(q, mode):
    r = copilot.ask(q)
    assert r.mode == "smalltalk" and r.tool_calls == []
    assert not re.search(r"\d", r.answer)
    assert re.search(r"[؀-ۿ]", r.answer) and len(r.suggestions) == 3


@pytest.mark.parametrize("q", ["hi, will SIBAL fabric burn at 18% O2 and 14.7 psia with 4 cm/s?",
                               "اهلا، هل قماش SIBAL قابل للاشتعال في جو محطة الفضاء؟",
                               "Is it safe?", "Why is fire in microgravity different from fire on Earth?"])
def test_real_questions_are_not_small_talk(q, monkeypatch):
    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    assert copilot.small_talk_kind(q) is None
    r = copilot.ask(q)
    assert r.mode == "fallback" and r.tool_calls


def test_greeting_plus_question_answers_the_question(monkeypatch):
    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    r = copilot.ask("hi, will SIBAL fabric burn at 18% O2 and 14.7 psia with 4 cm/s?")
    assert any(c["name"] == "predict" for c in r.tool_calls) and "SIBAL" in r.answer


def test_examples_are_answerable_questions(monkeypatch):
    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")
    for q in copilot.SMALLTALK_EXAMPLES["en"] + copilot.SMALLTALK_EXAMPLES["ar"]:
        assert copilot.small_talk_kind(q) is None
        assert copilot.ask(q).tool_calls


def test_every_eval_question_still_reaches_the_tools():
    import yaml

    data = yaml.safe_load((ROOT / "evals" / "hard_questions.yaml").read_text(encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    assert cases and all(copilot.small_talk_kind(c["question"]) is None for c in cases)


def test_off_topic_follow_up_reaches_the_llm_when_there_is_history(monkeypatch):
    monkeypatch.delenv("COPILOT_FORCE_FALLBACK", raising=False)
    monkeypatch.setattr(copilot, "get_api_key", lambda: "test-key-not-real")
    called = []

    def fake_llm(question, history, key, model, notes):
        called.append(question)
        raise copilot.LLMUnavailable("test")

    monkeypatch.setattr(copilot, "_llm_answer", fake_llm)
    r = copilot.ask("are you sure?", history=[{"role": "user", "content": "Is SIBAL fabric flammable on the ISS?"},
                                              {"role": "assistant", "content": "..."}])
    assert called and r.mode != "smalltalk"
    assert copilot.ask("hi", history=[{"role": "user", "content": "x"}]).mode == "smalltalk"
