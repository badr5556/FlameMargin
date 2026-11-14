"""P0.1: in the Copilot tab the chat input renders inline, so messages must stay above it, oldest first."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

Q1 = "Will SIBAL fabric keep burning at 17.5% O2 and 14.7 psia with 4 cm/s flow?"
Q2 = "Is SIBAL fabric safe in the lunar surface habitat at 10 cm/s?"


def _chat_in_tab():
    import sys
    from pathlib import Path

    import streamlit as st

    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    from src.copilot_ui import render_copilot_chat

    (tab,) = st.tabs(["Copilot"])
    with tab:
        render_copilot_chat(key_prefix="t")


def _order(at: AppTest) -> list[str]:
    """Element types inside the tab, flattened in render order (chat messages and the chat input)."""
    out: list[str] = []

    def walk(node) -> None:
        t = getattr(node, "type", "")
        if t == "chat_message":
            out.append(f"{node.name}:{node.markdown[0].value[:40]}")
            return
        if t == "chat_input":
            out.append("INPUT")
            return
        for c in (node.children.values() if hasattr(node, "children") else []):
            walk(c)

    walk(at.tabs[0])
    return out


def _app(monkeypatch) -> AppTest:
    monkeypatch.setenv("COPILOT_FORCE_FALLBACK", "1")  # never call the LLM in tests
    monkeypatch.chdir(ROOT)
    at = AppTest.from_function(_chat_in_tab, default_timeout=120)
    at.run()
    return at


def test_two_messages_render_in_order_above_the_input(monkeypatch):
    at = _app(monkeypatch)
    at.chat_input[0].set_value(Q1).run()
    at.chat_input[0].set_value(Q2).run()
    assert not at.exception
    order = _order(at)
    assert order[-1] == "INPUT", order
    msgs = order[:-1]
    assert [m.split(":", 1)[0] for m in msgs] == ["user", "assistant", "user", "assistant"], order
    assert msgs[0] == "user:" + Q1[:40] and msgs[2] == "user:" + Q2[:40]


def test_suggested_question_takes_the_same_path(monkeypatch):
    at = _app(monkeypatch)
    at.chat_input[0].set_value(Q1).run()
    next(b for b in at.button if b.label.startswith("🌕")).click().run()
    assert not at.exception
    order = _order(at)
    assert order[-1] == "INPUT", order
    assert [m.split(":", 1)[0] for m in order[:-1]] == ["user", "assistant", "user", "assistant"], order
    assert order[2].startswith("user:Is SIBAL fabric safe in the lunar")
