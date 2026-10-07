"""
human_oversight.py — Human-in-the-Loop Handler
"Review High Risk Actions, Approve/Reject, Modify Policies/Trust Rules"

Responsible for:
  - Queuing ALLOW_WITH_APPROVAL decisions for human review
  - Simulating (or integrating with) a human approval interface
  - Recording human decisions and feeding them back into the engine
"""

import time
from datetime import datetime
from queue import Queue
from typing import Callable, Dict, Optional

from .models import AuthorizationResult, HumanDecision


class HumanOversightHandler:
    """
    Human-in-the-loop handler for HIGH-risk or policy-flagged requests.
    In production this would integrate with a Slack bot, email, or web dashboard.
    For demo purposes, provides both a simulation mode and a live-prompt mode.
    """

    def __init__(self, auto_approve_simulation: bool = False):
        """
        Args:
            auto_approve_simulation: If True, automatically simulate human approval
                                     (useful for testing without interactive prompts).
        """
        self._pending: Dict[str, AuthorizationResult] = {}
        self._auto_simulate = auto_approve_simulation
        self._callbacks: Dict[str, Callable] = {}

    # ──────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────

    def submit_for_review(
        self,
        result: AuthorizationResult,
        callback: Optional[Callable] = None,
    ) -> str:
        """
        Submit an authorization result for human review.
        Returns a review ticket ID (same as request_id).
        """
        self._pending[result.request_id] = result
        if callback:
            self._callbacks[result.request_id] = callback

        print("\n" + "═" * 60)
        print("  ⚠  HUMAN OVERSIGHT REQUIRED")
        print("═" * 60)
        print(f"  Request ID : {result.request_id}")
        print(f"  Agent      : {result.agent_id}")
        print(f"  Decision   : {result.decision.value}")
        print(f"  Risk Level : {result.risk_score.level.value}")
        print(f"  Trust Score: {result.trust_score:.1f}/100")
        print(f"  Reason     : {result.justification}")
        print("  Risk Factors:")
        for factor in result.risk_score.factors[:5]:
            print(f"    {factor}")
        print("═" * 60)

        return result.request_id

    def respond(
        self,
        request_id: str,
        decision: HumanDecision,
        notes: str = "",
    ) -> Optional[AuthorizationResult]:
        """
        Record a human decision for a pending review.

        Args:
            request_id: The request under review.
            decision:   APPROVE or REJECT.
            notes:      Optional human notes/comments.

        Returns:
            Updated AuthorizationResult or None if not found.
        """
        if request_id not in self._pending:
            print(f"  [HumanOversight] No pending review for request '{request_id}'.")
            return None

        result = self._pending.pop(request_id)
        result.human_decision = decision
        result.human_notes    = notes

        symbol = "✅" if decision == HumanDecision.APPROVE else "❌"
        print(f"\n  {symbol} Human decision: {decision.value}")
        if notes:
            print(f"  Notes: {notes}")

        # Fire callback if registered
        cb = self._callbacks.pop(request_id, None)
        if cb:
            cb(result)

        return result

    def simulate_review(
        self,
        result: AuthorizationResult,
        simulate_approve: bool = True,
        notes: str = "Simulated human approval",
    ) -> AuthorizationResult:
        """
        Simulate a human review decision (for testing/demo).
        """
        decision = HumanDecision.APPROVE if simulate_approve else HumanDecision.REJECT
        self.submit_for_review(result)
        time.sleep(0.3)   # Simulate review latency
        print(f"  [HumanOversight] Simulating human response: {decision.value}")
        return self.respond(result.request_id, decision, notes)

    def interactive_review(self, result: AuthorizationResult) -> AuthorizationResult:
        """
        Prompt the real user in the terminal for a decision.
        """
        self.submit_for_review(result)
        while True:
            user_input = input(
                "\n  Enter decision [A=Approve / R=Reject]: "
            ).strip().upper()
            if user_input in ("A", "APPROVE"):
                notes = input("  Notes (optional): ").strip()
                return self.respond(result.request_id, HumanDecision.APPROVE, notes or "Approved by human")
            elif user_input in ("R", "REJECT"):
                notes = input("  Rejection reason: ").strip()
                return self.respond(result.request_id, HumanDecision.REJECT, notes or "Rejected by human")
            else:
                print("  Invalid input. Please enter A or R.")

    def pending_count(self) -> int:
        return len(self._pending)

    def pending_reviews(self) -> list:
        return [
            {
                "request_id": rid,
                "agent_id":   r.agent_id,
                "decision":   r.decision.value,
                "risk_level": r.risk_score.level.value,
                "submitted":  r.timestamp.isoformat(),
            }
            for rid, r in self._pending.items()
        ]
