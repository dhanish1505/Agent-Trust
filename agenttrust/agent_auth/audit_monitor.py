"""
audit_monitor.py — Monitoring & Audit Module
"Real-time Monitoring (Alerts, Anomalies) + Audit Logs + Dashboard"

Responsible for:
  - Real-time monitoring of authorization decisions
  - Anomaly alerting
  - Generating audit log entries
  - Producing dashboard-style reports
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import List

from .data_store import DataStore
from .models import (
    AuditLogEntry, AuthorizationResult, AuthDecision, RiskLevel,
)


class AuditAndMonitoringModule:
    """
    Central observability component. Records every authorization event and
    provides real-time alerting and reporting.
    """

    def __init__(self, store: DataStore):
        self._store = store
        self._alerts: List[dict] = []

    # ──────────────────────────────────────────────────────────────
    # CORE RECORDING
    # ──────────────────────────────────────────────────────────────

    def record(self, result: AuthorizationResult):
        """
        Record an authorization result to the audit log.
        Trigger alerts for anomalous/high-risk events.
        """
        entry = AuditLogEntry(
            request_id    = result.request_id,
            agent_id      = result.agent_id,
            action        = result.context_profile.intent_category,
            resource      = result.context_profile.target_description,
            decision      = result.decision.value,
            risk_level    = result.risk_score.level.value,
            trust_score   = result.trust_score,
            justification = result.justification,
            human_involved= result.human_decision is not None,
            timestamp     = result.timestamp,
        )
        self._store.audit_logs.append(entry)

        # Real-time alert checks
        self._check_alerts(result)

    def _check_alerts(self, result: AuthorizationResult):
        """Emit real-time alerts for concerning patterns."""

        # HIGH risk action
        if result.risk_score.level == RiskLevel.HIGH:
            self._emit_alert(
                "HIGH_RISK_ACTION",
                result.agent_id,
                result.request_id,
                f"HIGH risk decision '{result.decision.value}' for agent "
                f"'{result.agent_id}': {result.justification}",
            )

        # Trust score critically low
        if result.trust_score < 25.0:
            self._emit_alert(
                "CRITICAL_TRUST_DROP",
                result.agent_id,
                result.request_id,
                f"Agent '{result.agent_id}' trust score is critically low: "
                f"{result.trust_score:.1f}/100",
            )

        # Context anomaly flags
        for flag in result.context_profile.anomaly_flags:
            self._emit_alert(
                "CONTEXT_ANOMALY",
                result.agent_id,
                result.request_id,
                f"Context anomaly detected: {flag}",
            )

        # Repeated denials
        recent = self._store.audit_logs.get_by_agent(result.agent_id)[-10:]
        denials = sum(1 for l in recent if l.decision == AuthDecision.DENY.value)
        if denials >= 3:
            self._emit_alert(
                "REPEATED_DENIALS",
                result.agent_id,
                result.request_id,
                f"Agent '{result.agent_id}' has been denied {denials} times recently.",
            )

    def _emit_alert(self, alert_type: str, agent_id: str, request_id: str, message: str):
        alert = {
            "timestamp":  datetime.utcnow().isoformat(),
            "alert_type": alert_type,
            "agent_id":   agent_id,
            "request_id": request_id,
            "message":    message,
        }
        self._alerts.append(alert)
        print(f"  🚨 ALERT [{alert_type}]: {message}")

    # ──────────────────────────────────────────────────────────────
    # DASHBOARD / REPORTING
    # ──────────────────────────────────────────────────────────────

    def dashboard(self) -> dict:
        """Return a summary dashboard dict."""
        logs = self._store.audit_logs.get_all()
        decisions = Counter(l.decision for l in logs)
        risk_dist = Counter(l.risk_level for l in logs)
        per_agent = Counter(l.agent_id for l in logs)
        trust_scores = {
            agent_id: self._store.trust.get(agent_id).score
            for agent_id in per_agent
        }

        return {
            "total_requests":       len(logs),
            "decisions": {
                "ALLOW":              decisions.get("ALLOW", 0),
                "ALLOW_WITH_APPROVAL":decisions.get("ALLOW_WITH_APPROVAL", 0),
                "DENY":               decisions.get("DENY", 0),
            },
            "risk_distribution": {
                "LOW":    risk_dist.get("LOW", 0),
                "MEDIUM": risk_dist.get("MEDIUM", 0),
                "HIGH":   risk_dist.get("HIGH", 0),
            },
            "requests_per_agent":   dict(per_agent),
            "trust_scores":         trust_scores,
            "total_alerts":         len(self._alerts),
            "alert_types":          dict(Counter(a["alert_type"] for a in self._alerts)),
            "human_reviews":        sum(1 for l in logs if l.human_involved),
        }

    def print_dashboard(self):
        """Pretty-print the dashboard to stdout."""
        d = self.dashboard()
        print("\n" + "═" * 60)
        print("  📊  AUTHORIZATION SYSTEM DASHBOARD")
        print("═" * 60)
        print(f"  Total Requests  : {d['total_requests']}")
        print(f"  ✅ ALLOW        : {d['decisions']['ALLOW']}")
        print(f"  ⏳ W/ APPROVAL  : {d['decisions']['ALLOW_WITH_APPROVAL']}")
        print(f"  ❌ DENY         : {d['decisions']['DENY']}")
        print(f"\n  Risk Distribution:")
        print(f"    LOW     : {d['risk_distribution']['LOW']}")
        print(f"    MEDIUM  : {d['risk_distribution']['MEDIUM']}")
        print(f"    HIGH    : {d['risk_distribution']['HIGH']}")
        print(f"\n  Human Reviews   : {d['human_reviews']}")
        print(f"  Total Alerts    : {d['total_alerts']}")
        if d["alert_types"]:
            for atype, count in d["alert_types"].items():
                print(f"    {atype}: {count}")
        print(f"\n  Agent Trust Scores:")
        for agent_id, score in d["trust_scores"].items():
            bar_len = int(score / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {agent_id:20s} [{bar}] {score:.1f}/100")
        print("═" * 60)

    def get_alerts(self) -> List[dict]:
        return list(self._alerts)

    def export_audit_log(self, filepath: str):
        self._store.audit_logs.export_json(filepath)
