"""
risk_evaluator.py — Risk Evaluator
"Calculate risk score (Low / Medium / High)"

Responsible for:
  - Combining context score, behavior deviation, and trust score
  - Mapping the combined signal to a RiskLevel
  - Providing a human-readable explanation of the risk factors
"""

from .data_store import DataStore
from .models import (
    ActionCategory, ActionRequest, BehaviorProfile,
    ContextProfile, RiskLevel, RiskScore,
)


# Thresholds for risk classification
_HIGH_RISK_THRESHOLD   = 0.65
_MEDIUM_RISK_THRESHOLD = 0.35

# Action-level base risk modifiers
_ACTION_RISK = {
    ActionCategory.READ:        0.05,
    ActionCategory.NOTIFY:      0.05,
    ActionCategory.QUERY_DB:    0.10,
    ActionCategory.CALL_API:    0.15,
    ActionCategory.FILE_ACCESS: 0.15,
    ActionCategory.WRITE:       0.20,
    ActionCategory.SEND_EMAIL:  0.20,
    ActionCategory.SEND_SMS:    0.20,
    ActionCategory.EXECUTE:     0.30,
    ActionCategory.DELETE:      0.35,
    ActionCategory.DELEGATE:    0.30,
}


class RiskEvaluator:
    """
    Computes a composite risk score from context, behavior, and trust signals.
    """

    def __init__(self, store: DataStore):
        self._store = store

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def evaluate(
        self,
        request: ActionRequest,
        context: ContextProfile,
        behavior: BehaviorProfile,
    ) -> RiskScore:
        """
        Compute and return a RiskScore for the given request.

        Risk formula (all values normalised to [0, 1]):
          raw = action_base
              + (1 - context_score) * 0.30      ← context anomaly contribution
              + deviation_score     * 0.30       ← behavior anomaly contribution
              + trust_penalty       * 0.20       ← low trust contribution
              + flag_count          * 0.05       ← per context anomaly flag
        """
        factors: list[str] = []

        # 1. Action base risk
        action_base = _ACTION_RISK.get(request.action, 0.10)
        factors.append(f"Action '{request.action.value}' base risk: {action_base:.2f}")

        # 2. Context contribution (inverse of context score)
        context_contribution = (1.0 - context.context_score) * 0.30
        if context_contribution > 0.05:
            factors.append(
                f"Context anomaly (score={context.context_score:.2f}): +{context_contribution:.2f}"
            )

        # 3. Behavior deviation contribution
        behavior_contribution = behavior.deviation_score * 0.30
        if behavior_contribution > 0.05:
            factors.append(
                f"Behavior deviation (score={behavior.deviation_score:.2f}): +{behavior_contribution:.2f}"
            )

        # 4. Trust penalty (lower trust → higher risk)
        trust = self._store.trust.get(request.agent_id)
        trust_penalty = max(0.0, (100.0 - trust.score) / 100.0) * 0.20
        if trust_penalty > 0.02:
            factors.append(
                f"Low trust (score={trust.score:.1f}): +{trust_penalty:.2f}"
            )

        # 5. Context anomaly flag contribution
        flag_count = len(context.anomaly_flags)
        flag_contribution = flag_count * 0.05
        if flag_count:
            factors.append(
                f"Context flags ({flag_count} flags): +{flag_contribution:.2f}"
            )
            factors += [f"  • {flag}" for flag in context.anomaly_flags]

        # 6. Behavior pattern contribution
        if behavior.flagged_patterns:
            factors.append(
                f"Behavior patterns ({len(behavior.flagged_patterns)} patterns):"
            )
            factors += [f"  • {p}" for p in behavior.flagged_patterns[-3:]]

        # Final score
        raw_score = (
            action_base
            + context_contribution
            + behavior_contribution
            + trust_penalty
            + flag_contribution
        )
        raw_score = round(min(1.0, raw_score), 4)

        # Classify
        if raw_score >= _HIGH_RISK_THRESHOLD:
            level = RiskLevel.HIGH
        elif raw_score >= _MEDIUM_RISK_THRESHOLD:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        explanation = (
            f"Combined risk score: {raw_score:.4f} → {level.value}. "
            f"Trust score: {trust.score:.1f}/100."
        )

        self._store.behaviors.log_event(
            request.agent_id,
            "risk_evaluated",
            {
                "request_id":  request.request_id,
                "risk_score":  raw_score,
                "risk_level":  level.value,
                "factors":     factors,
            },
        )

        return RiskScore(
            request_id  = request.request_id,
            level       = level,
            score       = raw_score,
            factors     = factors,
            explanation = explanation,
        )
