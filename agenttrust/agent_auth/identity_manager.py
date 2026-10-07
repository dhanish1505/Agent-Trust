"""
identity_manager.py — Identity & Permission Manager
"Who is the agent? What is allowed?"

Responsible for:
  - Agent identity verification (is the agent registered & active?)
  - Base permission lookup (what actions/resources are statically allowed?)
  - Credential/attribute validation
"""

from datetime import datetime
from typing import Optional, Tuple

from .data_store import DataStore
from .models import (
    ActionCategory, ActionRequest, AgentIdentity, ResourceType,
)


class IdentityAndPermissionManager:
    """
    Core identity verification and static permission resolver.
    This is the very first gate in the authorization pipeline.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def verify_identity(self, agent_id: str) -> Tuple[bool, Optional[AgentIdentity], str]:
        """
        Verify that an agent exists and is active.

        Returns:
            (success, agent | None, reason)
        """
        agent = self._store.agents.get(agent_id)

        if agent is None:
            return False, None, f"Agent '{agent_id}' is not registered."

        if not agent.active:
            return False, None, f"Agent '{agent_id}' is deactivated."

        # Update last-seen timestamp
        agent.last_seen = datetime.utcnow()
        self._store.behaviors.log_event(
            agent_id,
            "identity_check",
            {"result": "verified", "name": agent.name, "role": agent.role},
        )

        return True, agent, "Identity verified."

    def check_static_permissions(
        self,
        agent: AgentIdentity,
        action: ActionCategory,
        resource: ResourceType,
    ) -> Tuple[bool, str]:
        """
        Check if the agent's static profile allows the action on the resource.
        This is the base layer before RBAC/ABAC policy evaluation.

        Returns:
            (allowed, reason)
        """
        if not agent.has_permission(action):
            return False, (
                f"Agent '{agent.agent_id}' does not have the '{action}' "
                f"permission in its identity profile."
            )

        if not agent.can_access_resource(resource):
            return False, (
                f"Agent '{agent.agent_id}' is not permitted to access "
                f"resource type '{resource}' in its identity profile."
            )

        return True, "Static permissions satisfied."

    def get_agent_profile_summary(self, agent_id: str) -> dict:
        """Returns a human-readable summary of an agent's identity & permissions."""
        agent = self._store.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not found."}
        trust = self._store.trust.get(agent_id)
        behavior = self._store.behaviors.get_profile(agent_id)
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "owner": agent.owner,
            "active": agent.active,
            "permissions": sorted([p.value for p in agent.permissions]),
            "allowed_resources": sorted([r.value for r in agent.allowed_resources]),
            "attributes": agent.attributes,
            "trust_score": trust.score,
            "total_requests": behavior.total_requests,
            "recent_violations": behavior.recent_violations,
            "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        }

    def resolve_effective_permissions(
        self,
        agent_id: str,
        request: ActionRequest,
    ) -> Tuple[bool, str]:
        """
        Full identity check for an incoming action request.
        Step 1 in the authorization pipeline.

        Returns:
            (passed, reason)
        """
        # 1. Verify identity
        ok, agent, msg = self.verify_identity(agent_id)
        if not ok:
            return False, msg

        # 2. Check static permissions
        ok, msg = self.check_static_permissions(
            agent, request.action, request.resource_type
        )
        if not ok:
            return False, msg

        return True, f"Identity OK. Agent '{agent.name}' ({agent.role}) cleared for base permission check."

    # ──────────────────────────────────────────────────────────────
    # ADMIN HELPERS
    # ──────────────────────────────────────────────────────────────

    def grant_permission(self, agent_id: str, action: ActionCategory) -> bool:
        """Dynamically grant an additional permission to an agent."""
        agent = self._store.agents.get(agent_id)
        if not agent:
            return False
        agent.permissions.add(action)
        self._store.behaviors.log_event(
            agent_id, "permission_granted", {"action": action.value}
        )
        print(f"  [IdentityManager] Granted '{action}' to agent '{agent_id}'.")
        return True

    def revoke_permission(self, agent_id: str, action: ActionCategory) -> bool:
        """Revoke a permission from an agent."""
        agent = self._store.agents.get(agent_id)
        if not agent:
            return False
        agent.permissions.discard(action)
        self._store.behaviors.log_event(
            agent_id, "permission_revoked", {"action": action.value}
        )
        print(f"  [IdentityManager] Revoked '{action}' from agent '{agent_id}'.")
        return True
