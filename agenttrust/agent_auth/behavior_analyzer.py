"""
behavior_analyzer.py — Behavior Analyzer
"Check past behavior, patterns, anomalies, deviation"

Responsible for:
  - Tracking request rates and action patterns per agent
  - Detecting behavioral anomalies (sudden spikes, unusual action types)
  - Computing a deviation score fed into the Risk Evaluator
"""

from datetime import datetime, timedelta
from typing import List

from .data_store import DataStore
from .models import ActionCategory, ActionRequest, BehaviorProfile


# Thresholds (tunable)
_VIOLATION_WEIGHT       = 0.15   # Per recent violation
_ANOMALY_WEIGHT         = 0.10   # Per detected anomaly
_SPIKE_THRESHOLD        = 10     # Requests in last 5 min = spike
_MAX_DEVIATION_SCORE    = 1.0


class BehaviorAnalyzer:
    """
    Analyses an agent's historical behavior and detects deviations or patterns.
    Updates the BehaviorProfile in the BehaviorHistoryStore.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def analyze(self, request: ActionRequest) -> BehaviorProfile:
        """
        Analyze agent behavior for the given request.
        Returns an updated BehaviorProfile.
        """
        agent_id = request.agent_id
        profile  = self._store.behaviors.get_profile(agent_id)
        events   = self._store.behaviors.get_recent_events(agent_id, limit=200)

        # Update counters
        profile.total_requests += 1

        # Detect patterns
        flagged_patterns: List[str] = list(profile.flagged_patterns)
        anomaly_delta = 0

        # 1. Request spike detection (>N requests in last 5 minutes)
        recent_5min = self._count_recent(events, minutes=5)
        if recent_5min >= _SPIKE_THRESHOLD:
            pattern = f"REQUEST_SPIKE ({recent_5min} in 5min)"
            if pattern not in flagged_patterns:
                flagged_patterns.append(pattern)
            anomaly_delta += 1
            profile.anomaly_count += 1

        # 2. Repeated denied-action pattern
        recent_denials = self._count_event_type(events[-20:], "decision_denied")
        if recent_denials >= 3:
            pattern = f"REPEATED_DENIALS ({recent_denials} recent)"
            if pattern not in flagged_patterns:
                flagged_patterns.append(pattern)
            profile.recent_violations += 1
            anomaly_delta += 1

        # 3. Unusual action for role
        agent = self._store.agents.get(agent_id)
        if agent and request.action not in agent.permissions:
            pattern = f"UNAUTHORIZED_ACTION_ATTEMPT: {request.action.value}"
            if pattern not in flagged_patterns:
                flagged_patterns.append(pattern)
            profile.recent_violations += 1
            anomaly_delta += 1

        # 4. Rapid escalation (multiple delegate calls)
        recent_delegates = self._count_action_type(events[-30:], ActionCategory.DELEGATE)
        if recent_delegates >= 3:
            pattern = f"PRIVILEGE_ESCALATION_PATTERN ({recent_delegates} delegate calls)"
            if pattern not in flagged_patterns:
                flagged_patterns.append(pattern)
            anomaly_delta += 1
            profile.anomaly_count += 1

        # 5. Accessing many different resources in short time (lateral movement)
        recent_resource_types = self._unique_resource_types(events[-20:])
        if len(recent_resource_types) >= 4:
            pattern = f"LATERAL_MOVEMENT ({len(recent_resource_types)} resource types)"
            if pattern not in flagged_patterns:
                flagged_patterns.append(pattern)
            anomaly_delta += 1

        # Compute deviation score
        raw_score = (
            profile.recent_violations * _VIOLATION_WEIGHT
            + profile.anomaly_count   * _ANOMALY_WEIGHT
        )
        profile.deviation_score  = min(_MAX_DEVIATION_SCORE, raw_score)
        profile.flagged_patterns = flagged_patterns
        profile.last_updated     = datetime.utcnow()

        self._store.behaviors.update_profile(profile)
        self._store.behaviors.log_event(
            agent_id,
            "behavior_analyzed",
            {
                "request_id":       request.request_id,
                "deviation_score":  profile.deviation_score,
                "anomaly_delta":    anomaly_delta,
                "flagged_patterns": flagged_patterns,
            },
        )

        return profile

    def record_decision(self, agent_id: str, request_id: str, decision: str):
        """Log the final decision for historical tracking."""
        event_type = f"decision_{decision.lower().replace(' ', '_')}"
        self._store.behaviors.log_event(
            agent_id,
            event_type,
            {"request_id": request_id, "decision": decision},
        )

    # ──────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _count_recent(events: List[dict], minutes: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        return sum(1 for e in events if e.get("timestamp", "") >= cutoff)

    @staticmethod
    def _count_event_type(events: List[dict], event_type: str) -> int:
        return sum(1 for e in events if e.get("event_type") == event_type)

    @staticmethod
    def _count_action_type(events: List[dict], action: ActionCategory) -> int:
        return sum(
            1 for e in events
            if e.get("event_type") == "context_analyzed"
            and e.get("intent") == action.value
        )

    @staticmethod
    def _unique_resource_types(events: List[dict]) -> set:
        types = set()
        for e in events:
            if "resource_type" in e:
                types.add(e["resource_type"])
        return types
