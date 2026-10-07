"""
auth_engine.py — Core Authorization Decision Engine
Orchestrates: Identity → Context → Policy → Behavior → Risk → Trust → Decision

This is the central pipeline that:
  1. Receives an ActionRequest from an agent
  2. Collects context, history, policies, and trust data
  3. Calculates risk & trust scores
  4. Returns a final AuthorizationResult (ALLOW / ALLOW_WITH_APPROVAL / DENY)
  5. If needed, routes to HumanOversightHandler
  6. Updates logs, trust scores, and history
"""

from typing import Optional

from .audit_monitor import AuditAndMonitoringModule
from .behavior_analyzer import BehaviorAnalyzer
from .context_analyzer import IntentAndContextAnalyzer
from .data_store import DataStore
from .delegation_control import DelegationAndPrivilegeControl
from .human_oversight import HumanOversightHandler
from .identity_manager import IdentityAndPermissionManager
from .models import (
    ActionRequest, AuthDecision, AuthorizationResult,
    HumanDecision, RiskLevel,
)
from .risk_evaluator import RiskEvaluator
from .trust_manager import TrustManager


# Risk thresholds for routing
_RISK_SCORE_APPROVAL_THRESHOLD = 0.55   # Above this → ALLOW_WITH_APPROVAL
_RISK_SCORE_DENY_THRESHOLD     = 0.80   # Above this → DENY (unconditionally)
_TRUST_MIN_TO_ALLOW            = 20.0   # Below this trust → deny regardless


class AuthorizationEngine:
    """
    Central authorization pipeline.
    Wires together all subsystems into a single evaluate() call.
    """

    def __init__(
        self,
        store: DataStore,
        human_oversight: Optional[HumanOversightHandler] = None,
        simulate_human: bool = True,
    ):
        self._store            = store
        self._identity         = IdentityAndPermissionManager(store)
        self._context          = IntentAndContextAnalyzer(store)
        self._behavior         = BehaviorAnalyzer(store)
        self._risk             = RiskEvaluator(store)
        self._trust            = TrustManager(store)
        self._delegation       = DelegationAndPrivilegeControl(store)
        self._audit            = AuditAndMonitoringModule(store)
        self._human            = human_oversight or HumanOversightHandler(
            auto_approve_simulation=simulate_human
        )
        self._simulate_human   = simulate_human

    # ──────────────────────────────────────────────────────────────
    # MAIN PIPELINE
    # ──────────────────────────────────────────────────────────────

    def evaluate(self, request: ActionRequest) -> AuthorizationResult:
        """
        Full authorization pipeline (matches architecture diagram flow).

        Flow:
          Step 1  — Identity & Permission check
          Step 2  — Collect context, history, policies, trust
          Step 3  — Compute risk & trust scores
          Step 4  — Make authorization decision
          Step 5  — Route to human oversight if needed
          Step 6  — Human responds (simulated or real)
          Step 7  — Update logs, trust score, history
          Step 8  — Return final AuthorizationResult
        """
        print(f"\n{'─'*60}")
        print(f"  📨 REQUEST [{request.request_id[:8]}]")
        print(f"     Agent : {request.agent_id}")
        print(f"     Action: {request.action.value}")
        print(f"     Target: {request.resource_type.value}:{request.resource_id}")
        print(f"     Intent: {request.intent}")
        print(f"{'─'*60}")

        # ── STEP 1: Identity & Permission ────────────────────────
        id_ok, id_reason = self._identity.resolve_effective_permissions(
            request.agent_id, request
        )
        agent = self._store.agents.get(request.agent_id)

        if not id_ok:
            return self._finalize(
                request     = request,
                decision    = AuthDecision.DENY,
                justification = f"[Identity] {id_reason}",
                policy_matched= "IDENTITY_CHECK_FAILED",
            )
        print(f"  ✔ [1] Identity: {id_reason}")

        # ── STEP 2a: Delegation validation (if delegated) ────────
        del_ok, del_reason, del_record = self._delegation.validate_delegation_for_request(request)
        delegation_id = del_record.delegation_id if del_record else None

        if not del_ok:
            return self._finalize(
                request        = request,
                decision       = AuthDecision.DENY,
                justification  = f"[Delegation] {del_reason}",
                policy_matched = "DELEGATION_INVALID",
            )
        if del_record:
            print(f"  ✔ [2a] Delegation: {del_reason}")

        # ── STEP 2b: Policy evaluation (RBAC + ABAC) ─────────────
        policy_result, policy_name = self._evaluate_policies(request)
        if policy_result is False:
            return self._finalize(
                request        = request,
                decision       = AuthDecision.DENY,
                justification  = f"[Policy:{policy_name}] Explicitly denied.",
                policy_matched = policy_name,
            )
        print(f"  ✔ [2b] Policy: {'matched=' + policy_name if policy_name else 'no explicit match (default-deny not triggered)'}")

        # ── STEP 2c: Context analysis ─────────────────────────────
        context_profile = self._context.analyze(request)
        print(
            f"  ✔ [2c] Context: intent={context_profile.intent_category}, "
            f"time={context_profile.time_of_day}, score={context_profile.context_score:.2f}, "
            f"flags={len(context_profile.anomaly_flags)}"
        )

        # ── STEP 2d: Behavior analysis ────────────────────────────
        behavior_profile = self._behavior.analyze(request)
        print(
            f"  ✔ [2d] Behavior: deviation={behavior_profile.deviation_score:.2f}, "
            f"violations={behavior_profile.recent_violations}, "
            f"patterns={len(behavior_profile.flagged_patterns)}"
        )

        # ── STEP 3: Risk & Trust Scores ───────────────────────────
        risk_score   = self._risk.evaluate(request, context_profile, behavior_profile)
        trust_score  = self._trust.get_trust_score(request.agent_id)
        trust_level  = self._trust.classify_trust_level(trust_score.score)

        print(
            f"  ✔ [3] Risk: {risk_score.level.value} ({risk_score.score:.4f}), "
            f"Trust: {trust_score.score:.1f}/100 ({trust_level})"
        )

        # ── STEP 4: Authorization Decision ────────────────────────
        decision, justification = self._make_decision(
            request, risk_score, trust_score.score, policy_result, policy_name
        )
        print(f"  ✔ [4] Decision: {decision.value} → {justification}")

        # ── Assemble preliminary result ───────────────────────────
        result = AuthorizationResult(
            request_id           = request.request_id,
            agent_id             = request.agent_id,
            decision             = decision,
            risk_score           = risk_score,
            trust_score          = trust_score.score,
            context_profile      = context_profile,
            behavior_profile     = behavior_profile,
            policy_matched       = policy_name,
            delegation_used      = delegation_id,
            justification        = justification,
            requires_human_approval = (decision == AuthDecision.ALLOW_WITH_APPROVAL),
        )

        # ── STEP 5/6: Human Oversight ─────────────────────────────
        if decision == AuthDecision.ALLOW_WITH_APPROVAL:
            if self._simulate_human:
                updated = self._human.simulate_review(
                    result,
                    simulate_approve=True,
                    notes="Auto-simulated approval for demo",
                )
            else:
                updated = self._human.interactive_review(result)

            if updated:
                result = updated
                # Override decision based on human response
                if result.human_decision == HumanDecision.REJECT:
                    result.decision = AuthDecision.DENY
                    result.justification += " [Human: REJECTED]"
                else:
                    result.justification += " [Human: APPROVED]"

        # ── STEP 7: Update Trust, Logs, History ───────────────────
        new_trust, trust_reason = self._trust.update_after_decision(
            request.agent_id, result.decision, risk_score.level,
            result.human_decision
        )
        result.trust_score = new_trust

        self._behavior.record_decision(
            request.agent_id, request.request_id, result.decision.value
        )
        self._audit.record(result)

        # ── STEP 8: Return ─────────────────────────────────────────
        icon = {"ALLOW": "✅", "DENY": "❌", "ALLOW_WITH_APPROVAL": "⏳"}.get(
            result.decision.value, "?"
        )
        print(f"\n  {icon} FINAL: {result.decision.value} | Trust→{new_trust:.1f} ({trust_reason})")

        return result

    # ──────────────────────────────────────────────────────────────
    # POLICY EVALUATION
    # ──────────────────────────────────────────────────────────────

    def _evaluate_policies(self, request: ActionRequest):
        """
        Evaluate RBAC then ABAC policies against the request.
        Returns (True=allow | False=deny | None=no-match, policy_name).
        """
        agent = self._store.agents.get(request.agent_id)
        if not agent:
            return False, "AGENT_NOT_FOUND"

        rbac_policies, abac_policies = self._store.policies.all_policies()

        # RBAC first
        for policy in rbac_policies:
            result = policy.evaluate(agent, request.action, request.resource_type)
            if result is True:
                return True, f"RBAC:{policy.name}"
            if result is False:
                return False, f"RBAC:{policy.name}"

        # ABAC next
        for policy in abac_policies:
            result = policy.evaluate(agent, request.action, request.resource_type)
            if result is True:
                return True, f"ABAC:{policy.name}"
            if result is False:
                return False, f"ABAC:{policy.name}"

        # No explicit policy match → proceed (base permissions already checked)
        return None, None

    # ──────────────────────────────────────────────────────────────
    # DECISION LOGIC
    # ──────────────────────────────────────────────────────────────

    def _make_decision(
        self,
        request: ActionRequest,
        risk_score,
        trust_score_val: float,
        policy_result,
        policy_name: str,
    ):
        """Map risk/trust/policy signals to an AuthDecision."""

        # Unconditional deny: critical trust failure
        if trust_score_val < _TRUST_MIN_TO_ALLOW:
            return (
                AuthDecision.DENY,
                f"Trust score ({trust_score_val:.1f}) is below minimum threshold "
                f"({_TRUST_MIN_TO_ALLOW}). Agent is untrusted.",
            )

        # High risk → deny unconditionally
        if risk_score.score >= _RISK_SCORE_DENY_THRESHOLD:
            return (
                AuthDecision.DENY,
                f"Risk score {risk_score.score:.4f} exceeds deny threshold "
                f"({_RISK_SCORE_DENY_THRESHOLD}). {risk_score.explanation}",
            )

        # Medium-high risk → human approval required
        if risk_score.score >= _RISK_SCORE_APPROVAL_THRESHOLD:
            return (
                AuthDecision.ALLOW_WITH_APPROVAL,
                f"Risk score {risk_score.score:.4f} requires human approval. "
                f"{risk_score.explanation}",
            )

        # Policy-matched allow + low risk → allow
        if policy_result is True:
            return (
                AuthDecision.ALLOW,
                f"Policy '{policy_name}' allows action. {risk_score.explanation}",
            )

        # No policy match but base permissions passed and low risk → allow
        if policy_result is None:
            return (
                AuthDecision.ALLOW,
                f"Base permissions satisfied. No explicit policy match. "
                f"Risk is {risk_score.level.value}. {risk_score.explanation}",
            )

        return AuthDecision.DENY, "Default deny: policy evaluation inconclusive."

    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────

    def _finalize(
        self,
        request: ActionRequest,
        decision: AuthDecision,
        justification: str,
        policy_matched: str = None,
    ) -> AuthorizationResult:
        """Create a deny/allow result quickly without full pipeline."""
        from .models import (
            BehaviorProfile, ContextProfile, EnvironmentSensitivity,
            RiskScore, RiskLevel,
        )
        context = ContextProfile(
            request_id        = request.request_id,
            intent_category   = request.action.value,
            sensitivity_level = request.environment,
            time_of_day       = "unknown",
            target_description= str(request.resource_id),
        )
        behavior = self._store.behaviors.get_profile(request.agent_id)
        risk = RiskScore(
            request_id  = request.request_id,
            level       = RiskLevel.HIGH,
            score       = 1.0,
            explanation = justification,
        )
        trust_val = self._store.trust.get(request.agent_id).score
        result = AuthorizationResult(
            request_id      = request.request_id,
            agent_id        = request.agent_id,
            decision        = decision,
            risk_score      = risk,
            trust_score     = trust_val,
            context_profile = context,
            behavior_profile= behavior,
            policy_matched  = policy_matched,
            justification   = justification,
        )
        self._trust.update_after_decision(
            request.agent_id, decision, RiskLevel.HIGH
        )
        self._behavior.record_decision(request.agent_id, request.request_id, decision.value)
        self._audit.record(result)
        print(f"  ❌ FINAL: {decision.value} | {justification}")
        return result

    # ──────────────────────────────────────────────────────────────
    # CONVENIENCE ACCESSORS
    # ──────────────────────────────────────────────────────────────

    @property
    def identity_manager(self) -> IdentityAndPermissionManager:
        return self._identity

    @property
    def delegation_control(self) -> DelegationAndPrivilegeControl:
        return self._delegation

    @property
    def trust_manager(self) -> TrustManager:
        return self._trust

    @property
    def audit_monitor(self) -> AuditAndMonitoringModule:
        return self._audit
