import os
import re
import uuid
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from agenttrust.gateway import current_agent_id
from finance_agent import FinanceAgent
from data_agent import DataAgent

# Initialize child agents
finance_agent = FinanceAgent()
data_agent = DataAgent()

@tool
def delegate_to_finance(query: str) -> str:
    """Delegate a finance-related question (like invoices) to the Finance Agent."""
    return finance_agent.run(query)

@tool
def delegate_to_data(query: str) -> str:
    """Delegate a data-related question (like customer profiles) to the Data Agent."""
    return data_agent.run(query)

class MockSupervisorLLM(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mock_supervisor"
    
    def bind_tools(self, tools, **kwargs):
        return self
        
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        has_tool_result = any(isinstance(m, ToolMessage) for m in messages)
        if has_tool_result:
            tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"Combined Information:\n{tool_msgs[-1].content}"))])
            
        user_text = next(m.content for m in reversed(messages) if isinstance(m, HumanMessage))
        tool_calls = []
        if re.search(r"CUST-\d+", user_text, re.IGNORECASE):
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "delegate_to_data",
                "args": {"query": user_text},
                "type": "tool_call",
            })
        if re.search(r"INV-\d+", user_text, re.IGNORECASE):
            tool_calls.append({
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": "delegate_to_finance",
                "args": {"query": user_text},
                "type": "tool_call",
            })
            
        if not tool_calls:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="Please provide a customer or invoice ID."))])
            
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=tool_calls))])

_SYSTEM_PROMPT = """You are the Supervisor Orchestrator. 
Your job is to read user tasks and route them to the appropriate child agents:
- delegate_to_finance: for invoice and financial queries.
- delegate_to_data: for customer data and profiles.

You can combine information from both if the user asks a complex question.
Do not guess information. Always rely on the outputs of the child agents."""

def get_supervisor_llm():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except ImportError:
            pass
    return MockSupervisorLLM()

class SupervisorAgent:
    def __init__(self):
        llm = get_supervisor_llm()
        self._graph = create_agent(
            model=llm,
            tools=[delegate_to_finance, delegate_to_data],
            system_prompt=_SYSTEM_PROMPT,
        )

    def run(self, query: str) -> str:
        token = current_agent_id.set("supervisor-agent")
        try:
            result = self._graph.invoke(
                {"messages": [HumanMessage(content=query)]}
            )
            return result["messages"][-1].content
        finally:
            current_agent_id.reset(token)


_SYSTEM_PROMPT = """You are the Supervisor Orchestrator. 
Your job is to read user tasks and route them to the appropriate child agents:
- delegate_to_finance: for invoice and financial queries.
- delegate_to_data: for customer data and profiles.

You can combine information from both if the user asks a complex question.
Do not guess information. Always rely on the outputs of the child agents."""


