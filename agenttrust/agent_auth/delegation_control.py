"""
delegation_control.py — Delegation & Privilege Control
"Validate delegated authority & prevent privilege escalation"

Responsible for:
  - Validating delegation chains for incoming requests
  - Enforcing max delegation depth (prevent privilege escalation)
  - Checking that delegated permissions ⊆ delegator's permissions
  - Revoking expired or invalid delegations
"""

from datetime import datetime
from typing import List, Optional, Tuple

from .data_store import DataStore
from .models import (
    ActionCategory, ActionRequest, AgentIdentity,
    DelegationRecord, ResourceType,
)


_MAX_DELEGATION_DEPTH = 3      # Prevent deep re-delegation chains


class DelegationAndPrivilegeControl:
    """
    Validates delegation chains and prevents privilege escalation.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def create_delegation(
        self,
        delegator_id: str,
        delegatee_id: str,
        permissions: set,
        resources: set,
        expires_at: Optional[datetime] = None,
    ) -> Tuple[bool, str, Optional[DelegationRecord]]:
        """
        Create a new delegation from delegator → delegatee.
        Validates that:
          1. Delegator exists and is active.
          2. Delegated permissions ⊆ delegator's own permissions (no escalation).
          3. Chain depth ≤ MAX_DELEGATION_DEPTH.

        Returns (success, reason, DelegationRecord | None)
        """
        delegator = self._store.agents.get(delegator_id)
        if not delegator:
            return False, f"Delegator '{delegator_id}' not found.", None
        if not delegator.active:
            return False, f"Delegator '{delegator_id}' is deactivated.", None

        delegatee = self._store.agents.get(delegatee_id)
        if not delegatee:
            return False, f"Delegatee '{delegatee_id}' not found.", None

        # Check permission subset (prevent privilege escalation)
        excess_perms = permissions - delegator.permissions
        if excess_perms:
            return (
                False,
                f"Privilege escalation blocked! Delegator lacks: "
                f"{[p.value for p in excess_perms]}",
                None,
            )

        # Check resource subset
        excess_resources = resources - delegator.allowed_resources
        if excess_resources:
            return (
                False,
                f"Privilege escalation blocked! Delegator lacks access to resources: "
                f"{[r.value for r in excess_resources]}",
                None,
            )

        # Check current delegation depth for this delegatee
        existing_depth = self._get_current_depth(delegatee_id)
        new_depth = existing_depth + 1

        if new_depth > _MAX_DELEGATION_DEPTH:
            return (
                False,
                f"Delegation chain depth {new_depth} exceeds maximum "
                f"of {_MAX_DELEGATION_DEPTH}. Blocked to prevent escalation.",
                None,
            )

        record = DelegationRecord(
            delegator_id         = delegator_id,
            delegatee_id         = delegatee_id,
            delegated_permissions= set(permissions),
            delegated_resources  = set(resources),
            expires_at           = expires_at,
            depth                = new_depth,
        )
        self._store.delegations.add(record)
        self._store.behaviors.log_event(
            delegatee_id,
            "delegation_received",
            {
                "delegation_id":  record.delegation_id,
                "from":           delegator_id,
                "permissions":    [p.value for p in permissions],
                "resources":      [r.value for r in resources],
                "depth":          new_depth,
                "expires_at":     expires_at.isoformat() if expires_at else None,
            },
        )
        return True, "Delegation created successfully.", record

    def validate_delegation_for_request(
        self,
        request: ActionRequest,
    ) -> Tuple[bool, str, Optional[DelegationRecord]]:
        """
        If the request was delegated (request.delegated_by is set),
        validate that a valid, unexpired delegation record exists covering
        the requested action and resource.

        Returns (valid, reason, matching_record | None)
        """
        if request.delegated_by is None:
            return True, "No delegation in request (direct action).", None

        delegations = self._store.delegations.get_delegations_for(request.agent_id)
        valid_delegations = [d for d in delegations if d.is_valid()]

        for d in valid_delegations:
            if (
                d.delegator_id == request.delegated_by
                and request.action in d.delegated_permissions
                and request.resource_type in d.delegated_resources
            ):
                return True, f"Valid delegation found (id={d.delegation_id}, depth={d.depth}).", d

        return (
            False,
            f"No valid delegation from '{request.delegated_by}' to '{request.agent_id}' "
            f"covering action='{request.action.value}' on resource='{request.resource_type.value}'.",
            None,
        )

    def get_delegation_chain(self, agent_id: str) -> List[dict]:
        """Return the full delegation chain for an agent."""
        records = self._store.delegations.get_delegations_for(agent_id)
        return [
            {
                "delegation_id":  r.delegation_id,
                "from":           r.delegator_id,
                "to":             r.delegatee_id,
                "permissions":    [p.value for p in r.delegated_permissions],
                "resources":      [res.value for res in r.delegated_resources],
                "depth":          r.depth,
                "active":         r.active,
                "valid":          r.is_valid(),
                "expires_at":     r.expires_at.isoformat() if r.expires_at else None,
            }
            for r in records
        ]

    # ──────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────

    def _get_current_depth(self, agent_id: str) -> int:
        """Get the maximum delegation chain depth currently held by agent."""
        records = self._store.delegations.get_delegations_for(agent_id)
        valid = [r for r in records if r.is_valid()]
        return max((r.depth for r in valid), default=0)
