"""
data_agent/agent.py
--------------------
Defines DataAgent — the public interface for Module 2.

Architecture (identical pattern to Module 1's FinanceAgent)
-----------------------------------------------------------
The agent is built on langchain.agents.create_agent, which compiles a
LangGraph state machine implementing the ReAct (Reason + Act) loop:

    User message
        |
        v
    [LLM node] --- decides which tool to call? --------------------+
        |                                                           |
        |   search_customer(customer_id) <----- summary query ------+
        |   get_customer_details(customer_id) <- detail query ------+
        |                                                           |
        |<-------- ToolMessage (tool result) ----------------------+
        |
        v  (no more tool calls)
    [LLM node] --- produces final text answer
        |
        v
    Response returned to caller

Public API
----------
    agent = DataAgent()               # auto-selects LLM
    agent = DataAgent(llm=my_llm)     # inject any BaseChatModel

    response: str = agent.run("Find customer CUST-003.")
    response: str = agent.run("Show full details for CUST-007.")

Module Input / Output
---------------------
    Input  : str  — natural-language query mentioning a customer ID
    Output : str  — formatted customer info or a graceful error/fallback
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from .llm_provider import get_llm
from .tools import get_customer_details, search_customer
from agenttrust.gateway import current_agent_id


_SYSTEM_PROMPT = """You are a Data Agent responsible for looking up customer information.

You have access to two tools:
- search_customer(customer_id): Returns a quick summary (name, email, department, status).
  Use this for a fast lookup or to confirm a customer exists.
- get_customer_details(customer_id): Returns the full customer profile including
  phone, location, subscription tier, join date, last login, and notes.
  Use this when the user asks for detailed or complete information.

When the user asks about a customer:
1. Choose the appropriate tool based on whether they want a summary or full details.
2. Call the tool with the customer ID.
3. Report the results clearly and completely.

If the user's request does not involve a customer lookup, politely explain that
your capability is limited to customer data queries and ask for a customer ID."""


class DataAgent:
    """
    LangGraph-powered Data Agent with two customer lookup tools.

    Accepts a natural-language query, selects the appropriate tool
    (search_customer or get_customer_details), and returns a formatted string.
    """

    def __init__(self, llm: BaseChatModel | None = None) -> None:
        """
        Initialise the Data Agent.

        Args:
            llm: Any LangChain-compatible chat model (must support tool calling
                 via bind_tools). If omitted, get_llm() auto-selects the LLM.
        """
        resolved_llm = llm if llm is not None else get_llm()

        self._graph = create_agent(
            model=resolved_llm,
            tools=[search_customer, get_customer_details],
            system_prompt=_SYSTEM_PROMPT,
        )

    def run(self, query: str) -> str:
        """
        Run the Data Agent on a natural-language query.

        MODULE INPUT:
            query (str): A natural-language question mentioning a customer ID.
                         Examples:
                           "Find customer CUST-001."
                           "What is the status of CUST-006?"
                           "Show me the full profile for CUST-008."
                           "Get all details for customer CUST-003."

        MODULE OUTPUT:
            str: The agent's response.
                 * Customer ID found + summary query:
                     Name, email, department, account status.
                 * Customer ID found + detail query:
                     Full profile (summary + phone, location, tier, etc.)
                 * Customer ID not found:
                     Error message listing all known IDs.
                 * No customer ID mentioned:
                     Polite fallback asking the user to provide an ID.

        Raises:
            ValueError: If query is empty or not a string.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string.")

        token = current_agent_id.set("data-agent")
        try:
            result = self._graph.invoke(
                {"messages": [HumanMessage(content=query)]}
            )
            # The graph accumulates all messages; the last one is the final response.
            return result["messages"][-1].content
        finally:
            current_agent_id.reset(token)
