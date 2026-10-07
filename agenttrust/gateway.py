import functools
import json
from contextvars import ContextVar
from typing import Any

from agenttrust.agent_auth.models import ActionRequest, ActionCategory, ResourceType, AuthDecision, EnvironmentSensitivity, AgentIdentity, AgentRole, RBACPolicy
from agenttrust.agent_auth.auth_engine import AuthorizationEngine
from agenttrust.agent_auth.data_store import DataStore

# ── Context Variables ────────────────────────────────────────────────────────
current_agent_id: ContextVar[str] = ContextVar("current_agent_id", default="UNKNOWN")

# ── Global Engine (For Demo) ─────────────────────────────────────────────────
store = DataStore()
auth_engine = AuthorizationEngine(store=store, simulate_human=True)

# Register Agents
store.agents.register(AgentIdentity(
    agent_id="finance-agent", name="Finance Agent", role=AgentRole.EXECUTOR,
    owner="system", permissions={ActionCategory.READ, ActionCategory.QUERY_DB},
    allowed_resources={ResourceType.DATABASE}
))

store.agents.register(AgentIdentity(
    agent_id="data-agent", name="Data Agent", role=AgentRole.DATA,
    owner="system", permissions={ActionCategory.READ, ActionCategory.QUERY_DB},
    allowed_resources={ResourceType.DATABASE}
))

store.agents.register(AgentIdentity(
    agent_id="supervisor-agent", name="Supervisor Orchestrator", role=AgentRole.MANAGER,
    owner="system", permissions={ActionCategory.DELEGATE},
    allowed_resources={ResourceType.AGENT}
))

# Register Policies
store.policies.add_rbac_policy(RBACPolicy(
    policy_id="pol-1", name="Finance DB Read", role=AgentRole.EXECUTOR,
    allowed_actions={ActionCategory.READ, ActionCategory.QUERY_DB},
    allowed_resources={ResourceType.DATABASE}
))

store.policies.add_rbac_policy(RBACPolicy(
    policy_id="pol-2", name="Data DB Read", role=AgentRole.DATA,
    allowed_actions={ActionCategory.READ, ActionCategory.QUERY_DB},
    allowed_resources={ResourceType.DATABASE}
))

store.policies.add_rbac_policy(RBACPolicy(
    policy_id="pol-3", name="Supervisor Delegation", role=AgentRole.MANAGER,
    allowed_actions={ActionCategory.DELEGATE},
    allowed_resources={ResourceType.AGENT}
))

# ── Gateway Decorator ────────────────────────────────────────────────────────

def secure_tool(action: ActionCategory, resource_type: ResourceType, resource_id_arg: str = None):
    """
    Wraps a LangChain @tool function to intercept the call and route it
    through the AgentTrust AuthorizationEngine.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            agent_id = current_agent_id.get()
            
            res_id = "unknown"
            if resource_id_arg and resource_id_arg in kwargs:
                res_id = str(kwargs[resource_id_arg])
            elif args:
                res_id = str(args[0])
                
            req = ActionRequest(
                agent_id=agent_id,
                action=action,
                resource_type=resource_type,
                resource_id=res_id,
                intent=f"Tool call: {func.__name__}",
                parameters=kwargs,
                environment=EnvironmentSensitivity.INTERNAL
            )
            
            result = auth_engine.evaluate(req)
            
            if result.decision in [AuthDecision.ALLOW, AuthDecision.ALLOW_WITH_APPROVAL]:
                return func(*args, **kwargs)
            else:
                return f"ERROR: Access Denied by AgentTrust Gateway. Justification: {result.justification}"
        return wrapper
    return decorator
