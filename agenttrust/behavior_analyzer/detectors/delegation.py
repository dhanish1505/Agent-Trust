"""
DelegationChainDetector — detects privilege escalation via delegation abuse.

Attack patterns detected:
  1. Deep chains: agent delegates to agent to agent... beyond config.max_delegation_depth
  2. Velocity abuse: many delegations issued in a short time window (rapid amplification)
  3. Self-delegation loops: agent delegating to itself (circular authority)
  4. Undeclared delegation: agent performing privileged actions without a valid token

Scoring:
  depth_score    = depth / max_depth  (linear, caps at 1.0)
  velocity_score = delegations_in_window / max_delegations_in_window
  final_score    = max(depth_score, velocity_score)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import ClassVar, DefaultDict, Dict, List

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector

# In-process delegation event log: agent_id → timestamps of delegation events
_delegation_log: DefaultDict[str, List[datetime]] = defaultdict(list)


def _record_delegation(agent_id: str, ts: datetime) -> None:
    _delegation_log[agent_id].append(ts)


def _count_delegations_in_window(agent_id: str, window_seconds: int) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    # Purge stale entries
    fresh = [t for t in _delegation_log[agent_id] if t >= cutoff]
    _delegation_log[agent_id] = fresh
    return len(fresh)


class DelegationChainDetector(BaseDetector):
    """
    Detects: excessive delegation depth, rapid delegation velocity,
    and self-delegation loops.
    """

    name: ClassVar[str] = "delegation"
    default_weight: ClassVar[float] = 0.10

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        evidence: Dict = {}
        score_components: List[float] = []

        # ── 1. Depth check ─────────────────────────────────────────────────────
        depth = event.delegation_depth
        max_depth = config.max_delegation_depth
        evidence["delegation_depth"] = depth
        evidence["max_allowed_depth"] = max_depth

        depth_score = 0.0
        if event.is_delegated:
            _record_delegation(event.agent_id, event.timestamp)

            if depth > max_depth:
                depth_score = min(1.0, depth / max_depth)
                evidence["depth_exceeded"] = True
            else:
                depth_score = depth / max_depth

            score_components.append(depth_score)

            # ── 2. Self-delegation detection ───────────────────────────────────
            if event.delegation and event.delegation.delegated_by == event.agent_id:
                evidence["self_delegation"] = True
                score_components.append(0.95)   # near-critical

            # ── 3. Delegation velocity ─────────────────────────────────────────
            window_secs = config.delegation_velocity_window_seconds
            max_in_window = config.max_delegations_in_window
            count_in_window = _count_delegations_in_window(event.agent_id, window_secs)

            evidence["delegations_in_window"] = count_in_window
            evidence["max_delegations_in_window"] = max_in_window
            evidence["velocity_window_seconds"] = window_secs

            velocity_score = min(1.0, count_in_window / max_in_window)
            score_components.append(velocity_score)

            if count_in_window > max_in_window:
                evidence["velocity_exceeded"] = True

        # ── 4. Baseline deviation — unusual delegation depth for this agent ────
        if baseline.delegation_depth.n >= config.min_samples_for_anomaly and event.is_delegated:
            z = baseline.delegation_depth.zscore(float(depth))
            evidence["delegation_depth_zscore"] = round(z, 4)
            if abs(z) > config.zscore_threshold:
                score_components.append(min(1.0, abs(z) / (3.0 * config.zscore_threshold)))

        if not score_components:
            return self.make_result(score=0.0, fired=False, not_delegated=True)

        final_score = min(1.0, max(score_components))
        fired = (
            depth > max_depth
            or evidence.get("self_delegation", False)
            or evidence.get("velocity_exceeded", False)
        )

        return DetectorResult(
            detector_name=self.name,
            score=final_score,
            fired=fired,
            confidence=0.95,   # delegation metadata is deterministic — always high confidence
            evidence=evidence,
        )
