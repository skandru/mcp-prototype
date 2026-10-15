"""Streamlit demo: chat with an LLM that calls the waterboards MCP tools.

Run locally (uses the in-process server unless MCP_URL is set):

    streamlit run demo/app.py

Environment:
    LLM_MODEL   Unity AI Gateway model service (default models.ai.gpt-5-6-sol)
    MCP_URL     deployed MCP endpoint, e.g. https://<app-url>/mcp (optional)
    DATABRICKS_CONFIG_PROFILE / DATABRICKS_HOST   local auth (databricks auth login)
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pandas as pd
import streamlit as st
from databricks.sdk.core import Config
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from openai import OpenAI

LLM_MODEL = os.getenv("LLM_MODEL", "models.ai.gpt-5-6-sol")
MCP_URL = os.getenv("MCP_URL", "").strip()
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """You answer California drinking water questions using ONLY the \
waterboards_* tools. Call tools for every factual claim; never guess values.
- Users usually give a ZIP code; a ZIP can map to several water systems.
- Tap-water results are system-level samples, not per-address results, and are \
not a health determination. Source (well) chemistry is untreated water, not tap \
water. Say so when relevant.
- Compare results with the limits returned by the tools when present.
- Cite the `source` field of the tool results. Be concise and use short bullets.
- If a tool returns an error, explain it plainly and suggest what to try next."""

EXAMPLES = [
    "What is in the tap water in ZIP 93721?",
    "Which water systems serve ZIP 95814, and are any at risk?",
    "Any lead found at schools near ZIP 90012?",
    "What chemicals show up in well water near ZIP 93706?",
]


def _token() -> str:
    return Config().authenticate()["Authorization"].removeprefix("Bearer ")


def _llm() -> OpenAI:
    host = Config().host.rstrip("/")
    return OpenAI(api_key=_token(), base_url=f"{host}/ai-gateway/mlflow/v1")


def _mcp_client() -> Client:
    if MCP_URL:
        return Client(MCP_URL, auth=BearerAuth(_token()))
    from waterboards_mcp.app import mcp

    return Client(mcp)


def _tool_specs(tools) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": t.name,
            "description": t.description or "",
            "parameters": getattr(t, "input_schema", None) or t.inputSchema,
        }
        for t in tools
    ]


async def _run_turn(history: list[dict[str, Any]]) -> tuple[str, list[dict]]:
    """Run the model/tool loop for one user turn; return answer and tool trace."""
    llm = _llm()
    trace: list[dict] = []
    async with _mcp_client() as mcp_client:
        specs = _tool_specs(await mcp_client.list_tools())
        items: list[dict[str, Any]] = list(history)
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await asyncio.to_thread(
                llm.responses.create,
                model=LLM_MODEL,
                instructions=SYSTEM_PROMPT,
                input=items,
                tools=specs,
            )
            calls = [o for o in resp.output if o.type == "function_call"]
            if not calls:
                return resp.output_text or "", trace
            for call in calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                )
                args = json.loads(call.arguments or "{}")
                try:
                    result = await mcp_client.call_tool(call.name, args)
                    payload = result.structured_content or {
                        "text": result.content[0].text if result.content else ""
                    }
                except Exception as exc:  # shown to the model and the audience
                    payload = {"error": type(exc).__name__, "hint": str(exc)[:300]}
                trace.append({"tool": call.name, "args": args, "result": payload})
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(payload, default=str),
                    }
                )
    return "I hit the tool-call limit. Please narrow the question.", trace


def _render_trace(trace: list[dict]) -> None:
    for step in trace:
        icon = "⚠️" if "error" in step["result"] else "🔧"
        with st.expander(f"{icon} {step['tool']}({json.dumps(step['args'])})"):
            rows = step["result"].get("results")
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch")
                st.caption(
                    f"{step['result'].get('count')} rows · "
                    f"{step['result'].get('source', '')}"
                )
            st.json(step["result"], expanded=False)


st.set_page_config(page_title="CA Drinking Water MCP", page_icon="💧", layout="wide")
st.title("💧 California Drinking Water Assistant")
st.caption(
    "An LLM answering questions through the waterboards MCP server. "
    "Results are system-level samples from State Water Board open data, "
    "not a health determination."
)

with st.sidebar:
    st.subheader("Try a question")
    for example in EXAMPLES:
        if st.button(example, width="stretch"):
            st.session_state["pending"] = example
    st.divider()
    st.caption(f"Model: `{LLM_MODEL}`")
    st.caption(f"MCP: `{MCP_URL or 'in-process server'}`")
    if st.button("Clear chat"):
        st.session_state.clear()
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        _render_trace(m.get("trace", []))

prompt = st.chat_input("Ask about drinking water in a California ZIP code")
prompt = prompt or st.session_state.pop("pending", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Calling water tools..."):
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ]
            try:
                answer, trace = asyncio.run(_run_turn(history))
            except Exception as exc:
                answer, trace = (
                    f"Sorry, the request failed ({type(exc).__name__}): "
                    f"{str(exc)[:600]}",
                    [],
                )
        st.markdown(answer)
        _render_trace(trace)
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "trace": trace}
    )
