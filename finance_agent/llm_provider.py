"""
finance_agent/llm_provider.py
------------------------------
LLM factory for the Finance Agent.

Priority order when get_llm() is called:
  1. OPENAI_API_KEY env var set + langchain-openai installed → ChatOpenAI
  2. Otherwise → MockDemoLLM (fully deterministic, no API key required)

MockDemoLLM
-----------
A BaseChatModel subclass that drives the LangGraph ReAct loop without any
real LLM. It works in two phases:

  Phase 1 — Tool decision (no ToolMessage in conversation yet):
    Scans the HumanMessage for an INV-NNN pattern.
      • Found  → returns an AIMessage with a tool_call for search_invoice.
      • Missing → returns a polite fallback text response.

  Phase 2 — Answer synthesis (ToolMessage present):
    Reads the JSON payload from the ToolMessage and formats a
    human-readable summary.

This lets the full LangGraph loop run correctly in demo/test mode.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable


# --------------------------------------------------------------------------- #
#  MockDemoLLM
# --------------------------------------------------------------------------- #

class MockDemoLLM(BaseChatModel):
    """
    Deterministic mock LLM for demo and testing (no API key required).

    Implements the two-phase ReAct pattern expected by LangGraph's
    create_react_agent loop.
    """

    @property
    def _llm_type(self) -> str:
        return "mock_demo_llm"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        """
        Override required by langchain-core >= 1.5.

        MockDemoLLM uses pattern matching instead of tool schema inspection,
        so we simply return self unchanged.  The full LangGraph loop still
        works because _generate honours the tool_call / ToolMessage protocol.
        """
        return self

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Determine phase from conversation history.
        has_tool_result = any(isinstance(m, ToolMessage) for m in messages)

        if has_tool_result:
            ai_msg = self._synthesise_answer(messages)
        else:
            ai_msg = self._decide_tool_call(messages)

        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    # ------------------------------------------------------------------ #
    #  Phase 1: decide whether to call search_invoice
    # ------------------------------------------------------------------ #

    def _decide_tool_call(self, messages: list) -> AIMessage:
        """
        Parse the latest HumanMessage for an invoice ID.
        Emit a tool_call AIMessage if found, else a polite text response.
        """
        user_text = self._last_human_text(messages)

        match = re.search(r"\bINV-\d+\b", user_text, re.IGNORECASE)
        if not match:
            return AIMessage(
                content=(
                    "I can help you look up invoice information. "
                    "Please provide an invoice ID such as INV-001."
                )
            )

        invoice_id = match.group().upper()
        call_id = f"call_{uuid.uuid4().hex[:12]}"

        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": call_id,
                    "name": "search_invoice",
                    "args": {"invoice_id": invoice_id},
                    "type": "tool_call",
                }
            ],
        )

    # ------------------------------------------------------------------ #
    #  Phase 2: format the tool result into a human-readable answer
    # ------------------------------------------------------------------ #

    def _synthesise_answer(self, messages: list) -> AIMessage:
        """
        Read the most recent ToolMessage and produce a readable summary.
        """
        tool_msg = next(
            m for m in reversed(messages) if isinstance(m, ToolMessage)
        )

        try:
            data = json.loads(tool_msg.content)
        except json.JSONDecodeError:
            return AIMessage(content=f"Invoice result: {tool_msg.content}")

        if not data.get("found"):
            return AIMessage(
                content=f"Invoice not found. {data.get('error', 'No details available.')}"
            )

        paid_info = (
            f"Paid on {data['paid_date']}"
            if data.get("paid_date")
            else "Not yet paid"
        )

        summary = (
            f"Here are the details for invoice {data['invoice_id']}:\n"
            f"  Vendor      : {data['vendor']}\n"
            f"  Amount      : {data['currency']} {data['amount']:,.2f}\n"
            f"  Status      : {data['status'].upper()}\n"
            f"  Due Date    : {data['due_date']}\n"
            f"  Payment     : {paid_info}\n"
            f"  Description : {data['description']}\n"
            f"  Contact     : {data['contact']}"
        )
        return AIMessage(content=summary)

    # ------------------------------------------------------------------ #
    #  Helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def _last_human_text(messages: list) -> str:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return str(msg.content)
        return ""


# --------------------------------------------------------------------------- #
#  Public factory
# --------------------------------------------------------------------------- #

def get_llm() -> BaseChatModel:
    """
    Return an LLM ready for use with the Finance Agent.

    Tries OpenAI first (if configured), falls back to MockDemoLLM.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if api_key:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore[import]
            print("[LLM] OPENAI_API_KEY found -> using ChatOpenAI (gpt-4o-mini)")
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except ImportError:
            print(
                "[LLM] OPENAI_API_KEY is set but langchain-openai is not installed.\n"
                "      Install it with: .venv\\Scripts\\pip install langchain-openai\n"
                "      Falling back to MockDemoLLM."
            )

    print("[LLM] No OPENAI_API_KEY -> using MockDemoLLM (demo mode, no API key required)")
    return MockDemoLLM()
