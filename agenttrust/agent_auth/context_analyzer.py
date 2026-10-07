"""
context_analyzer.py — Intent & Context Analyzer
"Understand task intent, environment, time, sensitivity, target"

Responsible for:
  - Parsing the action intent
  - Assessing environmental sensitivity
  - Detecting off-hours / unusual timing
  - Producing a ContextProfile score
"""

from datetime import datetime
from typing import List

from .data_store import DataStore
from .models import (
    ActionCategory, ActionRequest, ContextProfile,
    EnvironmentSensitivity, ResourceType,
)


# High-sensitivity intent keywords that increase scrutiny
_HIGH_SENSITIVITY_KEYWORDS = {
    "delete", "drop", "purge", "override", "admin", "root",
    "all", "bulk", "mass", "export_all", "bypass",
}

# Intent → readable category mapping
_INTENT_CATEGORIES = {
    ActionCategory.READ:        "data_retrieval",
    ActionCategory.WRITE:       "data_modification",
    ActionCategory.DELETE:      "data_deletion",
    ActionCategory.EXECUTE:     "code_execution",
    ActionCategory.DELEGATE:    "privilege_delegation",
    ActionCategory.NOTIFY:      "notification_dispatch",
    ActionCategory.QUERY_DB:    "database_query",
    ActionCategory.CALL_API:    "external_api_call",
    ActionCategory.SEND_EMAIL:  "email_dispatch",
    ActionCategory.SEND_SMS:    "sms_dispatch",
    ActionCategory.FILE_ACCESS: "file_system_access",
}


class IntentAndContextAnalyzer:
    """
    Analyses the intent, context, and environmental factors of an action request.
    Produces a ContextProfile that feeds the Risk Evaluator.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def analyze(self, request: ActionRequest) -> ContextProfile:
        """
        Main entry point. Returns a fully populated ContextProfile.
        """
        intent_category = _INTENT_CATEGORIES.get(request.action, "unknown")
        time_of_day     = self._classify_time(request.timestamp)
        anomaly_flags   = self._detect_anomalies(request, time_of_day)
        context_score   = self._compute_context_score(
            request, time_of_day, anomaly_flags
        )

        profile = ContextProfile(
            request_id        = request.request_id,
            intent_category   = intent_category,
            sensitivity_level = request.environment,
            time_of_day       = time_of_day,
            target_description= (
                f"{request.action.value} on "
                f"{request.resource_type.value}:{request.resource_id}"
            ),
            anomaly_flags     = anomaly_flags,
            context_score     = context_score,
        )

        self._store.behaviors.log_event(
            request.agent_id,
            "context_analyzed",
            {
                "request_id":    request.request_id,
                "intent":        intent_category,
                "time":          time_of_day,
                "context_score": context_score,
                "flags":         anomaly_flags,
            },
        )

        return profile

    # ──────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_time(ts: datetime) -> str:
        """Classify request time into business, after-hours, or weekend."""
        weekday  = ts.weekday()   # 0=Mon … 6=Sun
        hour     = ts.hour

        if weekday >= 5:
            return "weekend"
        if 8 <= hour < 18:
            return "business_hours"
        return "after_hours"

    @staticmethod
    def _detect_anomalies(request: ActionRequest, time_of_day: str) -> List[str]:
        """
        Detect surface-level anomaly signals from the request context.
        More sophisticated checks live in the BehaviorAnalyzer.
        """
        flags: List[str] = []

        # Off-hours high-sensitivity action
        if (
            time_of_day in ("after_hours", "weekend")
            and request.environment in (
                EnvironmentSensitivity.CONFIDENTIAL,
                EnvironmentSensitivity.RESTRICTED,
            )
        ):
            flags.append("OFF_HOURS_SENSITIVE_ACTION")

        # High-risk actions in restricted environments
        if (
            request.action in (ActionCategory.DELETE, ActionCategory.EXECUTE)
            and request.environment == EnvironmentSensitivity.RESTRICTED
        ):
            flags.append("DESTRUCTIVE_ACTION_IN_RESTRICTED_ENV")

        # Suspicious keywords in intent string
        import re
        intent_lower = request.intent.lower()
        for kw in _HIGH_SENSITIVITY_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", intent_lower):
                flags.append(f"SENSITIVE_KEYWORD_IN_INTENT: '{kw}'")
                break

        # Bulk/mass operation signal via parameters
        if request.parameters.get("bulk") or request.parameters.get("all_records"):
            flags.append("BULK_OPERATION_REQUESTED")

        # Delegation of delegation (re-delegation risk)
        if (
            request.action == ActionCategory.DELEGATE
            and request.delegated_by is not None
        ):
            flags.append("RE_DELEGATION_ATTEMPT")

        # External resource during internal call
        if (
            request.resource_type in (ResourceType.API, ResourceType.EMAIL, ResourceType.SMS)
            and request.environment == EnvironmentSensitivity.RESTRICTED
        ):
            flags.append("EXTERNAL_RESOURCE_FROM_RESTRICTED_CONTEXT")

        return flags

    @staticmethod
    def _compute_context_score(
        request: ActionRequest,
        time_of_day: str,
        anomaly_flags: List[str],
    ) -> float:
        """
        Returns a score in [0, 1].
        1.0 = perfectly normal context, 0.0 = extremely suspicious context.
        """
        score = 1.0

        # Time penalties
        if time_of_day == "after_hours":
            score -= 0.10
        elif time_of_day == "weekend":
            score -= 0.20

        # Sensitivity penalties
        sensitivity_penalty = {
            EnvironmentSensitivity.PUBLIC:       0.00,
            EnvironmentSensitivity.INTERNAL:     0.05,
            EnvironmentSensitivity.CONFIDENTIAL: 0.15,
            EnvironmentSensitivity.RESTRICTED:   0.25,
        }
        score -= sensitivity_penalty.get(request.environment, 0.0)

        # Action-type penalties
        action_penalty = {
            ActionCategory.DELETE:   0.20,
            ActionCategory.EXECUTE:  0.15,
            ActionCategory.DELEGATE: 0.10,
        }
        score -= action_penalty.get(request.action, 0.0)

        # Each anomaly flag reduces score
        score -= len(anomaly_flags) * 0.08

        return max(0.0, round(score, 3))
