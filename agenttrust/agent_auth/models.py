"""
models.py — Core Data Models for Dynamic Authorization & Trust Management
Covers: Agent Identity, Policies, Actions, Decisions, Delegation Chains, Audit Logs
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class AgentRole(str, Enum):
    MANAGER       = "manager"
    DATA          = "data"
    NOTIFICATION  = "notification"
    ANALYST       = "analyst"
    EXECUTOR      = "executor"
    AUDITOR       = "auditor"


class PolicyType(str, Enum):
    RBAC = "RBAC"   # Role-Based Access Control
    ABAC = "ABAC"   # Attribute-Based Access Control


class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class AuthDecision(str, Enum):
    ALLOW              = "ALLOW"
    ALLOW_WITH_APPROVAL = "ALLOW_WITH_APPROVAL"
    DENY               = "DENY"


class ActionCategory(str, Enum):
    READ        = "read"
    WRITE       = "write"
    DELETE      = "delete"
    EXECUTE     = "execute"
    DELEGATE    = "delegate"
    NOTIFY      = "notify"
    QUERY_DB    = "query_db"
    CALL_API    = "call_api"
    SEND_EMAIL  = "send_email"
    SEND_SMS    = "send_sms"
    FILE_ACCESS = "file_access"


class ResourceType(str, Enum):
    DATABASE    = "database"
    API         = "api"
    FILE_SYSTEM = "file_system"
    EMAIL       = "email"
    SMS         = "sms"
    AGENT       = "agent"


class EnvironmentSensitivity(str, Enum):
    PUBLIC       = "public"
    INTERNAL     = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED   = "restricted"


class HumanDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT  = "REJECT"


# ─────────────────────────────────────────────
# AGENT IDENTITY
# ─────────────────────────────────────────────

@dataclass
class AgentIdentity:
    """Represents an AI Agent's identity and static attributes."""
    agent_id: str
    name: str
    role: AgentRole
    owner: str                                # Human or system owner
    permissions: Set[ActionCategory]          # Allowed action categories
    allowed_resources: Set[ResourceType]      # Allowed resource types
    attributes: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None

    def __post_init__(self):
        # Ensure sets are mutable even if passed as frozenset/list
        self.permissions = set(self.permissions)
        self.allowed_resources = set(self.allowed_resources)

    def has_permission(self, action: ActionCategory) -> bool:
        return action in self.permissions

    def can_access_resource(self, resource: ResourceType) -> bool:
        return resource in self.allowed_resources


# ─────────────────────────────────────────────
# POLICIES
# ─────────────────────────────────────────────

@dataclass
class RBACPolicy:
    """Role-Based Access Control Policy."""
    policy_id: str
    name: str
    role: AgentRole
    allowed_actions: Set[ActionCategory]
    allowed_resources: Set[ResourceType]
    deny_actions: Set[ActionCategory] = field(default_factory=set)
    active: bool = True

    def evaluate(self, agent: AgentIdentity, action: ActionCategory,
                 resource: ResourceType) -> Optional[bool]:
        """Returns True=allow, False=deny, None=no-match."""
        if agent.role != self.role or not self.active:
            return None
        if action in self.deny_actions:
            return False
        if action in self.allowed_actions and resource in self.allowed_resources:
            return True
        return None


@dataclass
class ABACPolicy:
    """Attribute-Based Access Control Policy."""
    policy_id: str
    name: str
    conditions: Dict[str, Any]               # e.g. {"department": "ops"}
    allowed_actions: Set[ActionCategory]
    allowed_resources: Set[ResourceType]
    deny_actions: Set[ActionCategory] = field(default_factory=set)
    active: bool = True

    def _match_conditions(self, agent: AgentIdentity) -> bool:
        for key, value in self.conditions.items():
            agent_val = agent.attributes.get(key)
            if isinstance(value, list):
                if agent_val not in value:
                    return False
            elif agent_val != value:
                return False
        return True

    def evaluate(self, agent: AgentIdentity, action: ActionCategory,
                 resource: ResourceType) -> Optional[bool]:
        if not self.active or not self._match_conditions(agent):
            return None
        if action in self.deny_actions:
            return False
        if action in self.allowed_actions and resource in self.allowed_resources:
            return True
        return None


# ─────────────────────────────────────────────
# ACTION REQUEST
# ─────────────────────────────────────────────

@dataclass
class ActionRequest:
    """An action request submitted by an agent to the authorization engine."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    action: ActionCategory = ActionCategory.READ
    resource_type: ResourceType = ResourceType.DATABASE
    resource_id: str = ""
    intent: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: EnvironmentSensitivity = EnvironmentSensitivity.INTERNAL
    delegated_by: Optional[str] = None         # Delegating agent_id if any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────
# CONTEXT & SCORES
# ─────────────────────────────────────────────

@dataclass
class ContextProfile:
    """Intent & Context analysis result."""
    request_id: str
    intent_category: str          # e.g. "data_retrieval", "system_config"
    sensitivity_level: EnvironmentSensitivity
    time_of_day: str              # "business_hours" | "after_hours" | "weekend"
    target_description: str
    anomaly_flags: List[str] = field(default_factory=list)
    context_score: float = 1.0   # 0.0 = very unusual, 1.0 = completely normal


@dataclass
class BehaviorProfile:
    """Behavior analysis result for an agent."""
    agent_id: str
    total_requests: int = 0
    recent_violations: int = 0
    anomaly_count: int = 0
    deviation_score: float = 0.0    # 0.0 = normal, 1.0 = extreme deviation
    flagged_patterns: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskScore:
    """Risk evaluation result."""
    request_id: str
    level: RiskLevel
    score: float                     # 0.0–1.0 (higher = more risky)
    factors: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class TrustScore:
    """Per-agent trust score maintained by Trust Manager."""
    agent_id: str
    score: float = 100.0             # 0–100; starts at 100
    history: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def adjust(self, delta: float, reason: str):
        self.score = max(0.0, min(100.0, self.score + delta))
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "delta": delta,
            "new_score": self.score,
            "reason": reason,
        })
        self.last_updated = datetime.utcnow()


# ─────────────────────────────────────────────
# DELEGATION
# ─────────────────────────────────────────────

@dataclass
class DelegationRecord:
    """Records a privilege delegation from one agent to another."""
    delegation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    delegator_id: str = ""
    delegatee_id: str = ""
    delegated_permissions: Set[ActionCategory] = field(default_factory=set)
    delegated_resources: Set[ResourceType] = field(default_factory=set)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    active: bool = True
    depth: int = 1                   # Delegation chain depth (prevent escalation)

    def is_valid(self) -> bool:
        if not self.active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


# ─────────────────────────────────────────────
# AUTHORIZATION DECISION
# ─────────────────────────────────────────────

@dataclass
class AuthorizationResult:
    """Final authorization decision with full justification."""
    request_id: str
    agent_id: str
    decision: AuthDecision
    risk_score: RiskScore
    trust_score: float
    context_profile: ContextProfile
    behavior_profile: BehaviorProfile
    policy_matched: Optional[str] = None
    delegation_used: Optional[str] = None
    justification: str = ""
    requires_human_approval: bool = False
    human_decision: Optional[HumanDecision] = None
    human_notes: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# AUDIT LOG ENTRY
# ─────────────────────────────────────────────

@dataclass
class AuditLogEntry:
    """Immutable audit log record for every authorization event."""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    agent_id: str = ""
    action: str = ""
    resource: str = ""
    decision: str = ""
    risk_level: str = ""
    trust_score: float = 0.0
    justification: str = ""
    human_involved: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
