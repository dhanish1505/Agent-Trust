"""
Core event data models representing agent actions and tool calls.

These are immutable dataclasses that flow through the entire analysis pipeline.
Using __slots__ and frozen=True for maximum performance.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class RiskLevel(str, Enum):
    """Coarse risk classification for upstream consumption."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentRole(str, Enum):
    """Predefined agent roles that influence baseline expectations."""
    MANAGER = "manager"
    DATA = "data"
    NOTIFICATION = "notification"
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """
    Represents a single tool invocation within an agent event.
    Immutable — created once, never mutated.
    """
    tool_name: str
    parameters: Dict[str, Any]
    target_resource: Optional[str] = None  # e.g. "s3://bucket/key"
    execution_duration_ms: Optional[float] = None

    def parameter_count(self) -> int:
        return len(self.parameters)

    def parameter_size_bytes(self) -> int:
        """Rough estimate of payload size for anomaly checks."""
        return sum(len(str(v)) for v in self.parameters.values())


@dataclass(frozen=True, slots=True)
class DelegationInfo:
    """
    Captures delegation chain metadata when an agent acts on behalf of another.
    """
    delegated_by: str           # parent agent_id
    chain_depth: int            # 0 = direct, 1 = one hop, etc.
    delegation_token: str       # opaque token from Delegation Control
    delegated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AgentEvent:
    """
    The primary unit of analysis — one agent action request.

    Every tool execution attempt produces exactly one AgentEvent.
    Passed through the pipeline unchanged; detectors read from it.
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    agent_id: str
    agent_role: AgentRole = AgentRole.UNKNOWN

    # ── What the agent wants to do ────────────────────────────────────────────
    tool_call: ToolCall = field(default_factory=lambda: ToolCall("noop", {}))
    intent_label: Optional[str] = None     # from Intent & Context Analyzer
    sensitivity_score: float = 0.0        # 0.0 (public) → 1.0 (top secret)

    # ── When / where ─────────────────────────────────────────────────────────
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_ip: Optional[str] = None
    session_id: Optional[str] = None

    # ── Delegation context ────────────────────────────────────────────────────
    delegation: Optional[DelegationInfo] = None

    # ── System-assigned ID ────────────────────────────────────────────────────
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def hour_of_day(self) -> int:
        return self.timestamp.hour

    @property
    def day_of_week(self) -> int:
        """0=Monday … 6=Sunday."""
        return self.timestamp.weekday()

    @property
    def is_delegated(self) -> bool:
        return self.delegation is not None

    @property
    def delegation_depth(self) -> int:
        return self.delegation.chain_depth if self.delegation else 0

    def feature_vector(self) -> List[float]:
        """
        Compact numerical representation for ML detectors.
        Order matters — must be stable across calls.
        """
        return [
            float(self.hour_of_day),
            float(self.day_of_week),
            float(self.delegation_depth),
            float(self.tool_call.parameter_count()),
            float(self.tool_call.parameter_size_bytes()),
            float(self.sensitivity_score),
            float(self.is_delegated),
        ]
