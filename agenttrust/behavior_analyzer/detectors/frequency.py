"""
FrequencyDetector — sliding window rate-burst anomaly detector.

Detects rapid-fire tool calls that exceed the agent's normal call rate,
which is a strong signal for:
  - Rate-limit bypass attempts
  - Automated exploitation loops
  - Denial-of-service via tool flooding

Algorithm: Token Bucket / Sliding Window comparison
  baseline_rate = historical mean calls per rate_window_seconds
  current_rate  = events in the last rate_window_seconds (from store)
  burst_ratio   = current_rate / (baseline_rate + ε)
  score = min(1.0, (burst_ratio - 1.0) / (multiplier - 1.0))  if burst_ratio > 1.0
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import ClassVar, Dict, List

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector

# In-process sliding window: agent_id → list of recent timestamps
# In production this would be backed by Redis sorted sets
_rate_windows: Dict[str, List[datetime]] = {}


def _get_rate_window(agent_id: str, window_seconds: int) -> List[datetime]:
    """Return timestamps within the current window, purging stale entries."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window_seconds)
    timestamps = _rate_windows.get(agent_id, [])
    fresh = [t for t in timestamps if t >= cutoff]
    _rate_windows[agent_id] = fresh
    return fresh


def _record_event(agent_id: str, ts: datetime) -> None:
    if agent_id not in _rate_windows:
        _rate_windows[agent_id] = []
    _rate_windows[agent_id].append(ts)


class FrequencyDetector(BaseDetector):
    """
    Detects: burst access patterns and rate-limit bypass attempts.

    Uses an in-process sliding window (swappable for Redis ZSET in production).
    """

    name: ClassVar[str] = "frequency"
    default_weight: ClassVar[float] = 0.20

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        window_secs = config.rate_window_seconds
        burst_mult = config.rate_burst_multiplier

        # Record this event
        _record_event(event.agent_id, event.timestamp)

        # Current rate: events in window
        window = _get_rate_window(event.agent_id, window_secs)
        current_rate = len(window)  # calls in window

        # Baseline rate: from Welford accumulator
        acc = baseline.events_per_window
        if acc.n < config.min_samples_for_anomaly:
            # No baseline — use a soft cap of 20 calls/window
            baseline_rate = 20.0
            confidence = 0.2
        else:
            baseline_rate = max(1.0, acc.mean)
            confidence = min(1.0, acc.n / 50.0)

        burst_ratio = current_rate / (baseline_rate + 1e-6)

        # Score: 0.0 if within normal range, grows toward 1.0 as ratio increases
        if burst_ratio <= 1.0:
            score = 0.0
        else:
            score = min(1.0, (burst_ratio - 1.0) / max(1.0, burst_mult - 1.0))

        fired = burst_ratio >= burst_mult

        return DetectorResult(
            detector_name=self.name,
            score=score,
            fired=fired,
            confidence=confidence,
            evidence={
                "current_rate_in_window": current_rate,
                "baseline_mean_rate": round(baseline_rate, 2),
                "burst_ratio": round(burst_ratio, 4),
                "burst_multiplier_threshold": burst_mult,
                "window_seconds": window_secs,
                "baseline_samples": acc.n,
            },
        )
