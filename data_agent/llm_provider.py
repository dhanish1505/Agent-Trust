"""
data_agent/llm_provider.py
---------------------------
LLM factory for the Data Agent.

Priority order (same policy as Module 1):
  1. OPENAI_API_KEY env var set + langchain-openai installed -> ChatOpenAI
  2. Otherwise -> MockDemoLLM (fully deterministic, no API key required)

MockDemoLLM
-----------
Drives the LangGraph ReAct loop without any real LLM.

Two-phase behaviour:

  Phase 1 — Tool decision (no ToolMessage in conversation yet):
    1. Scan the HumanMessage for a CUST-NNN customer ID pattern.
    2. If found, choose which tool to call:
         • Keywords such as "detail", "full", "all", "complete", "more"
           -> get_customer_details
         • Everything else (default)
           -> search_customer
    3. Emit an AIMessage with the corresponding tool_call.
    4. If no customer ID is found, return a polite fallback text.

  Phase 2 — Answer synthesis (ToolMessage present):
    Read the JSON from the most recent ToolMessage and format a
    human-readable summary.
    Detects whether the result is a summary or a full profile by checking
    for extended fields (phone, location, etc.) and adjusts the output.
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


# Keywords that signal the user wants full details rather than a quick search.
_DETAIL_KEYWORDS = frozenset(
    {"detail", "details", "full", "complete", "all", "everything",
     "more", "information", "profile", "info", "show", "tell"}
)


# --------------------------------------------------------------------------- #
#  MockDemoLLM
# --------------------------------------------------------------------------- #

class MockDemoLLM(BaseChatModel):
    """
    Deterministic mock LLM for demo and testing (no API key required).

    Supports the two-tool Data Agent ReAct loop:
      search_customer       — triggered by default
      get_customer_details  — triggered when detail keywords are present
    """

    @property
    def _llm_type(self) -> str:
        return "mock_demo_llm_data"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        """
        Required override for langchain-core >= 1.5.
        MockDemoLLM uses pattern matching, so we return self unchanged.
        """
        return self

    def _generate(
        self,
        messages: list,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        has_tool_result = any(isinstance(m, ToolMessage) for m in messages)

        if has_tool_result:
            ai_msg = self._synthesise_answer(messages)
        else:
            ai_msg = self._decide_tool_call(messages)

        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    # ------------------------------------------------------------------ #
    #  Phase 1: decide which tool to call (or respond with fallback)
    # ------------------------------------------------------------------ #

    def _decide_tool_call(self, messages: list) -> AIMessage:
        user_text = self._last_human_text(messages)

        match = re.search(r"\bCUST-\d+\b", user_text, re.IGNORECASE)
        if not match:
            return AIMessage(
                content=(
                    "I can help you look up customer information. "
                    "Please provide a customer ID such as CUST-001."
                )
            )

        customer_id = match.group().upper()
        tool_name = self._pick_tool(user_text)
        call_id = f"call_{uuid.uuid4().hex[:12]}"

        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": call_id,
                    "name": tool_name,
                    "args": {"customer_id": customer_id},
                    "type": "tool_call",
                }
            ],
        )

    @staticmethod
    def _pick_tool(user_text: str) -> str:
        """
        Choose between the two tools based on keyword signals in the query.

        Returns 'get_customer_details' if detail-oriented words are present,
        otherwise 'search_customer'.
        """
        words = set(user_text.lower().split())
        if words & _DETAIL_KEYWORDS:
            return "get_customer_details"
        return "search_customer"

    # ------------------------------------------------------------------ #
    #  Phase 2: synthesise a readable answer from the tool result
    # ------------------------------------------------------------------ #

    def _synthesise_answer(self, messages: list) -> AIMessage:
        tool_msg = next(
            m for m in reversed(messages) if isinstance(m, ToolMessage)
        )

        try:
            data = json.loads(tool_msg.content)
        except json.JSONDecodeError:
            return AIMessage(content=f"Customer result: {tool_msg.content}")

        if not data.get("found"):
            return AIMessage(
                content=f"Customer not found. {data.get('error', 'No details available.')}"
            )

        # Detect whether this is a summary or a full-profile result.
        is_full_profile = "phone" in data

        if is_full_profile:
            return self._format_full_profile(data)
        return self._format_summary(data)

    # ------------------------------------------------------------------ #
    #  Formatters
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_summary(data: dict) -> AIMessage:
        status_label = data["account_status"].upper()
        text = (
            f"Here is a summary for customer {data['customer_id']}:\n"
            f"  Name       : {data['name']}\n"
            f"  Email      : {data['email']}\n"
            f"  Department : {data['department']}\n"
            f"  Status     : {status_label}"
        )
        return AIMessage(content=text)

    @staticmethod
    def _format_full_profile(data: dict) -> AIMessage:
        status_label = data["account_status"].upper()
        text = (
            f"Full profile for customer {data['customer_id']}:\n"
            f"  Name              : {data['name']}\n"
            f"  Email             : {data['email']}\n"
            f"  Department        : {data['department']}\n"
            f"  Status            : {status_label}\n"
            f"  Phone             : {data.get('phone', 'N/A')}\n"
            f"  Location          : {data.get('location', 'N/A')}\n"
            f"  Joined            : {data.get('joined_date', 'N/A')}\n"
            f"  Subscription Tier : {data.get('subscription_tier', 'N/A')}\n"
            f"  Last Login        : {data.get('last_login', 'N/A')}\n"
            f"  Notes             : {data.get('notes', 'N/A')}"
        )
        return AIMessage(content=text)

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
    Return an LLM instance for the Data Agent.

    Tries OpenAI first (if OPENAI_API_KEY is set), falls back to MockDemoLLM.
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
                "      Install it: .venv\\Scripts\\pip install langchain-openai\n"
                "      Falling back to MockDemoLLM."
            )

    print("[LLM] No OPENAI_API_KEY -> using MockDemoLLM (demo mode, no API key required)")
    return MockDemoLLM()
