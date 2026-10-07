"""
trust_manager.py — Trust Manager
"Maintain trust score for each agent"

Responsible for:
  - Maintaining a per-agent trust score (0–100)
  - Adjusting scores based on decisions and outcomes
  - Providing trust-level classification (HIGH / MEDIUM / LOW / UNTRUSTED)
"""

from datetime import datetime
from typing import Tuple

from .data_store import DataStore
from .models import AuthDecision, HumanDecision, RiskLevel, TrustScore


# Trust classification thresholds
_TRUST_HIGH      = 80.0
_TRUST_MEDIUM    = 50.0
_TRUST_LOW       = 25.0

# Score adjustments per event
_DELTA = {
    "allow":                  +1.5,    # Successful authorized action
    "allow_with_approval":    +0.5,    # Approved by human
    "human_approved":         +2.0,    # Human explicitly approved
    "human_rejected":         -8.0,    # Human rejected as unsafe
    "deny_identity":          -5.0,    # Identity/permission failure
    "deny_policy":            -3.0,    # Policy violation
    "deny_risk":              -6.0,    # High risk denial
    "anomaly_detected":       -4.0,    # Behavioral anomaly
    "time_decay_daily":       -0.2,    # Natural decay for inactivity
}


class TrustManager:
    """
    Manages trust scores per agent and adjusts them based on authorization outcomes.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def get_trust_score(self, agent_id: str) -> TrustScore:
        return self._store.trust.get(agent_id)

    def classify_trust_level(self, score: float) -> str:
        if score >= _TRUST_HIGH:
            return "HIGH"
        if score >= _TRUST_MEDIUM:
            return "MEDIUM"
        if score >= _TRUST_LOW:
            return "LOW"
        return "UNTRUSTED"

    def update_after_decision(
        self,
        agent_id: str,
        decision: AuthDecision,
        risk_level: RiskLevel,
        human_decision: HumanDecision = None,
    ) -> Tuple[float, str]:
        """
        Adjust trust score after an authorization decision.
        Returns (new_score, reason).
        """
        trust = self._store.trust.get(agent_id)
        reason = ""

        if decision == AuthDecision.ALLOW:
            delta = _DELTA["allow"]
            reason = "Action allowed — positive reinforcement"

        elif decision == AuthDecision.ALLOW_WITH_APPROVAL:
            if human_decision == HumanDecision.APPROVE:
                delta = _DELTA["human_approved"]
                reason = "Human approved — trust boosted"
            elif human_decision == HumanDecision.REJECT:
                delta = _DELTA["human_rejected"]
                reason = "Human rejected — trust penalised"
            else:
                delta = _DELTA["allow_with_approval"]
                reason = "Awaiting human approval"

        elif decision == AuthDecision.DENY:
            if risk_level == RiskLevel.HIGH:
                delta = _DELTA["deny_risk"]
                reason = "Denied due to HIGH risk"
            else:
                delta = _DELTA["deny_policy"]
                reason = "Denied by policy"

        else:
            delta = 0.0
            reason = "Unknown decision type"

        trust.adjust(delta, reason)
        self._store.trust.save(trust)

        self._store.behaviors.log_event(
            agent_id,
            "trust_updated",
            {
                "decision":   decision.value,
                "delta":      delta,
                "new_score":  trust.score,
                "level":      self.classify_trust_level(trust.score),
                "reason":     reason,
            },
        )

        return trust.score, reason

    def penalize_anomaly(self, agent_id: str, anomaly_description: str) -> float:
        """Apply trust penalty for a detected behavioral anomaly."""
        trust = self._store.trust.get(agent_id)
        delta = _DELTA["anomaly_detected"]
        trust.adjust(delta, f"Anomaly: {anomaly_description}")
        self._store.trust.save(trust)
        return trust.score

    def apply_daily_decay(self, agent_id: str) -> float:
        """
        Apply a small daily trust decay (prevents stale high-trust agents).
        Should be called by a scheduler daily.
        """
        trust = self._store.trust.get(agent_id)
        trust.adjust(_DELTA["time_decay_daily"], "Daily trust decay")
        self._store.trust.save(trust)
        return trust.score

    def get_trust_summary(self, agent_id: str) -> dict:
        """Returns a summary dict of an agent's trust state."""
        trust = self._store.trust.get(agent_id)
        return {
            "agent_id":    agent_id,
            "score":       trust.score,
            "level":       self.classify_trust_level(trust.score),
            "last_updated": trust.last_updated.isoformat(),
            "history":     trust.history[-5:],   # Last 5 adjustments
        }
