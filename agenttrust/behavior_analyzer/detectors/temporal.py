"""
TemporalPatternDetector — time-based behavioral anomaly detector.

Checks whether the current event's hour-of-day and day-of-week
are consistent with the agent's historical usage patterns.

Algorithm:
  1. Build a probability distribution over 24 hourly bins from history.
  2. Smooth with Laplace (add-1) to handle zero counts.
  3. Current hour probability below anomaly_percentile → anomalous.

Also detects access outside normal working hours for sensitive operations.
"""
from __future__ import annotations

import math
from typing import ClassVar, List

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline, ToolBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector

# Typical "business hours" window
_BUSINESS_HOURS_START = 7   # 07:00
_BUSINESS_HOURS_END = 20    # 20:00


def _laplace_smoothed_probs(histogram: List[int], alpha: float = 1.0) -> List[float]:
    """Laplace (add-alpha) smoothing over a histogram."""
    total = sum(histogram) + alpha * len(histogram)
    return [(count + alpha) / total for count in histogram]


def _entropy(probs: List[float]) -> float:
    """Shannon entropy — higher = more uniform distribution."""
    return -sum(p * math.log2(p + 1e-12) for p in probs)


class TemporalPatternDetector(BaseDetector):
    """
    Detects: actions at statistically unusual hours/days for this agent.
    High sensitivity for sensitive operations outside business hours.
    """

    name: ClassVar[str] = "temporal"
    default_weight: ClassVar[float] = 0.15

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        tool_bl: ToolBaseline | None = baseline.tools.get(event.tool_call.tool_name)

        if tool_bl is None or tool_bl.total_calls() < config.min_samples_for_anomaly:
            # No history yet — fall back to business-hours heuristic only
            return self._business_hours_heuristic(event, config)

        hour = event.hour_of_day
        dow = event.day_of_week

        # Hour-of-day probability
        hour_probs = _laplace_smoothed_probs(tool_bl.hour_histogram)
        hour_prob = hour_probs[hour]
        hour_entropy = _entropy(hour_probs)

        # Day-of-week probability
        dow_probs = _laplace_smoothed_probs(tool_bl.dow_histogram)
        dow_prob = dow_probs[dow]

        # Anomaly threshold: percentile-based
        threshold = config.temporal_anomaly_percentile

        # Combined probability — joint (assuming independence)
        joint_prob = hour_prob * dow_prob

        # Low-probability access → anomalous
        hour_anomalous = hour_prob < threshold
        dow_anomalous = dow_prob < threshold

        # Score: inversely proportional to joint probability, capped at 1.0
        # More skewed histograms (low entropy) → higher score for off-peak hits
        entropy_factor = max(0.5, 1.0 - hour_entropy / math.log2(24))
        score = min(1.0, entropy_factor * (threshold / (hour_prob + 1e-9)) * 0.3)

        # Amplify for highly sensitive operations during off-hours
        outside_business = not (_BUSINESS_HOURS_START <= hour < _BUSINESS_HOURS_END)
        if outside_business and event.sensitivity_score > 0.6:
            score = min(1.0, score * 1.5)

        fired = hour_anomalous or dow_anomalous or (outside_business and event.sensitivity_score > 0.7)

        return DetectorResult(
            detector_name=self.name,
            score=score,
            fired=fired,
            confidence=min(1.0, tool_bl.total_calls() / 100.0),
            evidence={
                "hour_of_day": hour,
                "day_of_week": dow,
                "hour_probability": round(hour_prob, 6),
                "dow_probability": round(dow_prob, 6),
                "hour_entropy": round(hour_entropy, 4),
                "joint_probability": round(joint_prob, 8),
                "outside_business_hours": outside_business,
                "sensitivity_score": round(event.sensitivity_score, 4),
                "anomaly_threshold": threshold,
            },
        )

    def _business_hours_heuristic(
        self, event: AgentEvent, config: BehaviorAnalyzerConfig
    ) -> DetectorResult:
        """Fallback: simple business-hours + sensitivity check."""
        hour = event.hour_of_day
        outside = not (_BUSINESS_HOURS_START <= hour < _BUSINESS_HOURS_END)
        sensitivity = event.sensitivity_score
        score = 0.0
        if outside and sensitivity > 0.5:
            score = 0.3 + sensitivity * 0.2
        fired = score > 0.4
        return DetectorResult(
            detector_name=self.name,
            score=score,
            fired=fired,
            confidence=0.3,   # low confidence — no baseline data
            evidence={
                "hour_of_day": hour,
                "outside_business_hours": outside,
                "sensitivity_score": round(sensitivity, 4),
                "fallback_heuristic": True,
            },
        )
