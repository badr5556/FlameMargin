"""Streamlit chat UI for the FlameMargin Copilot.

Mount inside the main app (see docs/copilot_integration.md):

    from src.copilot_ui import render_copilot_chat
    render_copilot_chat()

Standalone demo:

    streamlit run src/copilot_ui.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:  # allows `streamlit run src/copilot_ui.py`
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from src import copilot_tools  # noqa: E402
from src.copilot import CopilotResult, ask, get_api_key, get_model  # noqa: E402

SUGGESTED_QUESTIONS = [
    ("🧪 In the data", "Will SIBAL fabric keep burning at 17.5% O2 and 14.7 psia with 4 cm/s flow?"),
    ("🛰️ ISS cabin", "Is SIBAL fabric flammable in the ISS cabin atmosphere?"),
    ("🚀 Artemis + fans off", "Is SIBAL fabric safe in the Artemis atmosphere with fans off?"),
    ("🌕 Lunar habitat (OOD)", "Is SIBAL fabric safe in the lunar surface habitat at 10 cm/s?"),
]


def _badges(res: dict[str, Any]) -> str:
    mode = "🤖 `LLM" + (f" · {res.get('model')}`" if res.get("model") else "`") if res.get("mode") == "llm" else "🧮 `Fallback (deterministic)`"
    ood = "⚠️ `Out of distribution`" if res.get("ood") else "🟢 `In distribution`"
    grounding = "✅ `All numbers grounded`" if res.get("grounding_ok") else "❌ `LLM draft failed grounding → tool outputs shown`"
    data = "🧪 `Data: mock API`" if res.get("backend") == "mock" else "📡 `Data: Prediction Engine`"
    return "  ".join([mode, ood, grounding, data, f"⏱️ `{res.get('latency_ms', 0)} ms`"])


def _render_trace(res: dict[str, Any]) -> None:
    calls = res.get("tool_calls") or []
    with st.expander(f"🔧 Tool-call trace ({len(calls)} calls)", expanded=False):
        if not calls:
            st.caption("No tools were called for this answer.")
        for i, c in enumerate(calls, 1):
            result = c.get("result")
            status = "❌ error" if isinstance(result, dict) and "error" in result else ("⚠️ OOD" if isinstance(result, dict) and result.get("ood_flag") else "✓")
            st.markdown(f"**{i}. `{c.get('name')}`** · {c.get('ms')} ms · {status}")
            st.code(json.dumps(c.get("args"), ensure_ascii=False, indent=2), language="json")
            try:
                st.json(result, expanded=False)
            except TypeError:  # older Streamlit without `expanded`
                st.json(result)
        if res.get("notes"):
            st.caption("Notes: " + " | ".join(res["notes"]))
        if res.get("ungrounded"):
            st.caption("Ungrounded values in the LLM draft: " + ", ".join(map(str, res["ungrounded"])))
        st.caption(f"Prompt version {res.get('prompt_version', '?')}")


def _render_assistant(msg: dict[str, Any]) -> None:
    st.markdown(msg["content"])
    res = msg.get("result")
    if res:
        st.caption(_badges(res))
        _render_trace(res)


def render_copilot_chat(key_prefix: str = "copilot") -> None:
    """Render the Copilot chat. Safe to call once per page; state lives in st.session_state[key_prefix + '_*']."""
    hist_key, pending_key, offline_key = f"{key_prefix}_history", f"{key_prefix}_pending", f"{key_prefix}_offline"
    st.session_state.setdefault(hist_key, [])
    history: list[dict[str, Any]] = st.session_state[hist_key]

    has_key = bool(get_api_key())
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown("#### 🔥 Fire Safety Copilot")
        st.caption(
            ("LLM: `" + get_model() + "`" if has_key else "No GEMINI_API_KEY: deterministic fallback mode")
            + f" · model backend: `{copilot_tools.backend_name()}` · every number comes from a tool call"
        )
    with head_r:
        st.toggle("Offline mode", key=offline_key, help="Skip the LLM and use the deterministic, rule-based path.")
        if st.button("Clear chat", key=f"{key_prefix}_clear", use_container_width=True):
            st.session_state[hist_key] = []
            st.rerun()

    cols = st.columns(len(SUGGESTED_QUESTIONS))
    for col, (label, q) in zip(cols, SUGGESTED_QUESTIONS):
        if col.button(label, key=f"{key_prefix}_sugg_{label}", use_container_width=True, help=q):
            st.session_state[pending_key] = q

    for msg in history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                _render_assistant(msg)
            else:
                st.markdown(msg["content"])

    typed = st.chat_input("Ask about a material, atmosphere, flow or mission…", key=f"{key_prefix}_input")
    question = typed or st.session_state.pop(pending_key, None)
    if not question:
        return

    prior = [{"role": m["role"], "content": m["content"]} for m in history]
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Calling the prediction engine…"):
            try:
                res: CopilotResult = ask(question, history=prior, force_fallback=bool(st.session_state.get(offline_key)))
                payload = res.to_dict()
                content = res.answer
            except Exception as e:  # noqa: BLE001 - the UI must never die during a demo
                payload, content = None, f"⚠️ Copilot error: {type(e).__name__}. Try again or switch to offline mode."
        msg = {"role": "assistant", "content": content, "result": payload}
        _render_assistant(msg)
    history.append(msg)


if __name__ == "__main__":
    st.set_page_config(page_title="FlameMargin Copilot", page_icon="🔥", layout="wide")
    st.title("FlameMargin · Fire Safety Copilot")
    st.caption("Layer 3 standalone demo. Decision support, not a replacement for NASA-STD-6001 material testing.")
    render_copilot_chat()
