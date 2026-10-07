"""
data_store.py — In-memory Data & Memory Store
Covers: Policy Store, Behavior History Store, Trust Score Store, Delegation Chain Store
"""

import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    ABACPolicy, AgentIdentity, AuditLogEntry, BehaviorProfile,
    DelegationRecord, RBACPolicy, TrustScore,
)


class PolicyStore:
    """
    Stores RBAC and ABAC policies.
    In production this would be backed by OPA/Casbin + PostgreSQL.
    """

    def __init__(self):
        self._rbac_policies: Dict[str, RBACPolicy] = {}
        self._abac_policies: Dict[str, ABACPolicy] = {}

    # ── RBAC ──────────────────────────────────────────────

    def add_rbac_policy(self, policy: RBACPolicy):
        self._rbac_policies[policy.policy_id] = policy
        print(f"  [PolicyStore] RBAC policy added: '{policy.name}'")

    def get_rbac_policies(self) -> List[RBACPolicy]:
        return [p for p in self._rbac_policies.values() if p.active]

    # ── ABAC ──────────────────────────────────────────────

    def add_abac_policy(self, policy: ABACPolicy):
        self._abac_policies[policy.policy_id] = policy
        print(f"  [PolicyStore] ABAC policy added: '{policy.name}'")

    def get_abac_policies(self) -> List[ABACPolicy]:
        return [p for p in self._abac_policies.values() if p.active]

    def all_policies(self):
        return self.get_rbac_policies(), self.get_abac_policies()


# ─────────────────────────────────────────────

class BehaviorHistoryStore:
    """
    Stores per-agent behavior logs and events.
    In production: MongoDB / ELK Stack.
    """

    def __init__(self):
        # agent_id → list of event dicts
        self._events: Dict[str, List[dict]] = defaultdict(list)
        self._profiles: Dict[str, BehaviorProfile] = {}

    def log_event(self, agent_id: str, event_type: str, detail: dict):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **detail,
        }
        self._events[agent_id].append(entry)

    def get_recent_events(self, agent_id: str, limit: int = 50) -> List[dict]:
        return self._events[agent_id][-limit:]

    def get_profile(self, agent_id: str) -> BehaviorProfile:
        if agent_id not in self._profiles:
            self._profiles[agent_id] = BehaviorProfile(agent_id=agent_id)
        return self._profiles[agent_id]

    def update_profile(self, profile: BehaviorProfile):
        self._profiles[profile.agent_id] = profile


# ─────────────────────────────────────────────

class TrustScoreStore:
    """
    Persists trust score per agent.
    In production: Redis / PostgreSQL.
    """

    def __init__(self):
        self._scores: Dict[str, TrustScore] = {}

    def get(self, agent_id: str) -> TrustScore:
        if agent_id not in self._scores:
            self._scores[agent_id] = TrustScore(agent_id=agent_id)
        return self._scores[agent_id]

    def save(self, trust_score: TrustScore):
        self._scores[trust_score.agent_id] = trust_score

    def all_scores(self) -> Dict[str, TrustScore]:
        return dict(self._scores)


# ─────────────────────────────────────────────

class DelegationChainStore:
    """
    Authority propagation logs for delegation chains.
    In production: PostgreSQL with adjacency list / graph DB.
    """

    def __init__(self):
        self._records: Dict[str, DelegationRecord] = {}
        # delegatee_id → list of delegation_ids granted to them
        self._by_delegatee: Dict[str, List[str]] = defaultdict(list)

    def add(self, record: DelegationRecord):
        self._records[record.delegation_id] = record
        self._by_delegatee[record.delegatee_id].append(record.delegation_id)
        print(
            f"  [DelegationStore] '{record.delegator_id}' delegated to "
            f"'{record.delegatee_id}' (depth={record.depth})"
        )

    def get_delegations_for(self, agent_id: str) -> List[DelegationRecord]:
        ids = self._by_delegatee.get(agent_id, [])
        return [self._records[i] for i in ids if i in self._records]

    def revoke(self, delegation_id: str):
        if delegation_id in self._records:
            self._records[delegation_id].active = False
            print(f"  [DelegationStore] Delegation {delegation_id} revoked.")


# ─────────────────────────────────────────────

class AgentRegistry:
    """
    Stores registered agent identities.
    In production: Identity Provider (IdP) / Vault.
    """

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}

    def register(self, agent: AgentIdentity):
        self._agents[agent.agent_id] = agent
        print(f"  [AgentRegistry] Registered agent: '{agent.name}' (role={agent.role})")

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        return self._agents.get(agent_id)

    def deactivate(self, agent_id: str):
        if agent_id in self._agents:
            self._agents[agent_id].active = False

    def all_agents(self) -> List[AgentIdentity]:
        return list(self._agents.values())


# ─────────────────────────────────────────────

class AuditLogStore:
    """
    Append-only audit log store.
    In production: ELK / Prometheus + immutable write-once storage.
    """

    def __init__(self):
        self._logs: List[AuditLogEntry] = []

    def append(self, entry: AuditLogEntry):
        self._logs.append(entry)

    def get_all(self) -> List[AuditLogEntry]:
        return list(self._logs)

    def get_by_agent(self, agent_id: str) -> List[AuditLogEntry]:
        return [l for l in self._logs if l.agent_id == agent_id]

    def export_json(self, filepath: str):
        data = [
            {
                "log_id": e.log_id,
                "request_id": e.request_id,
                "agent_id": e.agent_id,
                "action": e.action,
                "resource": e.resource,
                "decision": e.decision,
                "risk_level": e.risk_level,
                "trust_score": e.trust_score,
                "justification": e.justification,
                "human_involved": e.human_involved,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self._logs
        ]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  [AuditLogStore] Exported {len(data)} logs to {filepath}")


# ─────────────────────────────────────────────
# UNIFIED DATA STORE (Façade)
# ─────────────────────────────────────────────

class DataStore:
    """
    Unified façade over all storage subsystems.
    Instantiated once and injected into all engine components.
    """

    def __init__(self):
        self.agents      = AgentRegistry()
        self.policies    = PolicyStore()
        self.behaviors   = BehaviorHistoryStore()
        self.trust       = TrustScoreStore()
        self.delegations = DelegationChainStore()
        self.audit_logs  = AuditLogStore()
        print("[DataStore] All storage subsystems initialized.")
