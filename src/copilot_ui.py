"""Streamlit chat UI for the FlameMargin Copilot.

Mount inside the main app (see docs/copilot_integration.md):

    from src.copilot_ui import render_copilot_chat
    render_copilot_chat()

Full app (map + Copilot + data), also the deployed entry point:

    streamlit run src/copilot_ui.py      # same as: streamlit run app.py
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
from src.copilot import CopilotResult, ask, get_api_key, get_model, session_llm_limit  # noqa: E402

SUGGESTED_QUESTIONS = [
    ("🧪 In the data", "Will SIBAL fabric keep burning at 17.5% O2 and 14.7 psia with 4 cm/s flow?"),
    ("🛰️ ISS cabin", "Is SIBAL fabric flammable in the ISS cabin atmosphere?"),
    ("🧯 Nomex at ISS air", "Does Nomex sustain a flame at 21% O2, 14.7 psia and 10 cm/s?"),
    ("🚀 Artemis + fans off", "Is SIBAL fabric safe in the Artemis atmosphere with fans off?"),
    ("🌕 Lunar habitat (OOD)", "Is SIBAL fabric safe in the lunar surface habitat at 10 cm/s?"),
]


def _badges(res: dict[str, Any]) -> str:
    if res.get("mode") == "smalltalk":
        return "💬 `Small talk: no tools called, no numbers`"
    mode = "🤖 `LLM" + (f" · {res.get('model')}`" if res.get("model") else "`") if res.get("mode") == "llm" else "🧮 `Fallback (deterministic)`"
    ood = "⚠️ `Out of distribution`" if res.get("ood") else "🟢 `In distribution`"
    grounding = "✅ `All numbers grounded`" if res.get("grounding_ok") else "❌ `LLM draft failed grounding → tool outputs shown`"
    data = {"mock": "🧪 `Data: mock API (test fixture)`", "unavailable": "⛔ `Prediction Engine unavailable`"}.get(
        res.get("backend"), "📡 `Data: Prediction Engine v2.x (NASA BASS-II, 5 materials)`")
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


def _render_assistant(msg: dict[str, Any], suggestion_key: str | None = None, pending_key: str | None = None) -> None:
    st.markdown(msg["content"])
    res = msg.get("result")
    if res:
        st.caption(_badges(res))
        if res.get("suggestions") and suggestion_key and pending_key:
            # Clickable example questions: they go through the same pending-question path as the suggestion buttons.
            for j, q in enumerate(res["suggestions"]):
                if st.button(q, key=f"{suggestion_key}_{j}"):
                    st.session_state[pending_key] = q
        if res.get("mode") != "smalltalk":
            _render_trace(res)


def render_copilot_chat(key_prefix: str = "copilot") -> None:
    """Render the Copilot chat. Safe to call once per page; state lives in st.session_state[key_prefix + '_*']."""
    hist_key, pending_key, offline_key = f"{key_prefix}_history", f"{key_prefix}_pending", f"{key_prefix}_offline"
    used_key = f"{key_prefix}_llm_used"
    st.session_state.setdefault(hist_key, [])
    st.session_state.setdefault(used_key, 0)
    limit = session_llm_limit()
    history: list[dict[str, Any]] = st.session_state[hist_key]

    has_key = bool(get_api_key())
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown("#### 🔥 Fire Safety Copilot")
        st.caption(
            ("LLM: `" + get_model() + f"` · {max(0, limit - st.session_state[used_key])}/{limit} LLM questions left this session"
             if has_key else "No GEMINI_API_KEY: deterministic fallback mode")
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

    # Inside a tab, st.chat_input renders inline (it is not pinned to the page bottom). The history container is
    # created BEFORE the input, and new turns are written into it, so the input always stays below the last message.
    chat_box = st.container()
    with chat_box:
        for i, msg in enumerate(history):
            _render_message(msg, f"{key_prefix}_ex{i}", pending_key)

    typed = st.chat_input("Ask about a material, atmosphere, flow or mission…", key=f"{key_prefix}_input")
    question = typed or st.session_state.pop(pending_key, None)
    if not question:
        return

    # Typed questions and suggested-question buttons take this same path.
    prior = [{"role": m["role"], "content": m["content"]} for m in history]
    user_msg = {"role": "user", "content": question}
    history.append(user_msg)
    with chat_box:
        _render_message(user_msg)
        with st.chat_message("assistant"):
            with st.spinner("Calling the prediction engine…"):
                msg = _answer(question, prior, has_key, offline_key, used_key, limit)
            _render_assistant(msg)
    history.append(msg)
    if (msg.get("result") or {}).get("suggestions"):
        st.rerun()  # re-render so the example-question buttons of this reply are live


def _render_message(msg: dict[str, Any], suggestion_key: str | None = None, pending_key: str | None = None) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            _render_assistant(msg, suggestion_key, pending_key)
        else:
            st.markdown(msg["content"])


def _answer(question: str, prior: list[dict[str, Any]], has_key: bool, offline_key: str, used_key: str, limit: int) -> dict[str, Any]:
    """Run the Copilot for one question and return the assistant message (never raises)."""
    wants_llm = has_key and not st.session_state.get(offline_key)
    over_budget = wants_llm and st.session_state[used_key] >= limit
    try:
        res: CopilotResult = ask(question, history=prior, force_fallback=not wants_llm or over_budget)
        if wants_llm and not over_budget and res.mode != "smalltalk":  # small talk never calls the LLM
            st.session_state[used_key] += 1
        if over_budget:
            res.notes.append(f"per-session LLM budget reached ({limit} questions): deterministic fallback")
        payload = res.to_dict()
        content = res.answer
        if over_budget:
            content = (f"_LLM budget for this session is used up ({limit} questions, the public demo runs on a free-tier key). "
                       "Answering with the deterministic fallback, same tools and same guards._\n\n" + content)
    except Exception as e:  # noqa: BLE001 - the UI must never die during a demo
        payload, content = None, f"⚠️ Copilot error: {type(e).__name__}. Try again or switch to offline mode."
    return {"role": "assistant", "content": content, "result": payload}

if __name__ == "__main__":
    # Streamlit Cloud runs this file; serve the full 4-tab app (app.main() calls st.set_page_config once).
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import app

    app.main()
