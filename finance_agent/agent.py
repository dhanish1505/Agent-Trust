"""
finance_agent/agent.py
-----------------------
Defines FinanceAgent — the public interface for Module 1.

Architecture
------------
The agent is built on LangGraph's create_agent, which implements the
standard ReAct (Reason + Act) loop:

    User message
        │
        ▼
    [LLM node]  ─── decides to call search_invoice? ──YES──► [Tool node]
        │                                                          │
        │◄─────────────── ToolMessage (tool result) ──────────────┘
        │
        ▼ (no more tool calls)
    [LLM node]  ─── produces final text answer
        │
        ▼
    Response returned to caller

Public API
----------
    agent = FinanceAgent()          # uses auto-selected LLM
    agent = FinanceAgent(llm=my_llm)  # inject any BaseChatModel

    response: str = agent.run("What is the status of invoice INV-003?")

Module Input / Output
---------------------
    Input  : str  — natural-language query (must mention an invoice ID for
                    the tool to be triggered)
    Output : str  — human-readable invoice details, or a graceful error /
                    fallback message
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from .llm_provider import get_llm
from .tools import search_invoice


# The system prompt scopes the agent to its single responsibility.
_SYSTEM_PROMPT = """You are a Finance Agent. Your only responsibility is to look \
up invoice information using the search_invoice tool.

When the user asks about an invoice:
1. Call search_invoice with the invoice ID they mentioned.
2. Report the results clearly and completely.

If the user's request does not involve an invoice lookup, politely explain \
that your capability is limited to invoice searches and ask for an invoice ID."""


class FinanceAgent:
    """
    LangGraph-powered Finance Agent.

    Accepts a natural-language query, decides whether to invoke
    search_invoice, and returns a formatted string response.
    """

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """
        Initialise the Finance Agent.

        Args:
            llm: Any LangChain-compatible chat model (must support tool calling).
                 If omitted, get_llm() is called which auto-selects OpenAI or
                 MockDemoLLM based on environment variables.
        """
        resolved_llm = llm if llm is not None else get_llm()

        # create_agent builds and compiles the full LangGraph state machine.
        # It handles the ReAct loop, tool dispatch, and message accumulation.
        self._graph = create_agent(
            model=resolved_llm,
            tools=[search_invoice],
            system_prompt=_SYSTEM_PROMPT,
        )

    def run(self, query: str) -> str:
        """
        Run the Finance Agent on a user query.

        MODULE INPUT:
            query (str): A natural-language question.
                         Examples:
                           "What is the status of invoice INV-001?"
                           "Show me the details for INV-007."
                           "Is invoice INV-003 overdue?"

        MODULE OUTPUT:
            str: The agent's response.
                 • If an invoice ID is present and found:
                     Formatted invoice details (vendor, amount, status, etc.)
                 • If the invoice ID is not found:
                     An error message listing known invoice IDs.
                 • If no invoice ID is mentioned:
                     A polite fallback asking the user to provide an ID.

        Raises:
            ValueError: If query is empty or not a string.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        result = self._graph.invoke(
            {"messages": [HumanMessage(content=query)]}
        )

        # The graph accumulates all messages; the last one is the final response.
        return result["messages"][-1].content
