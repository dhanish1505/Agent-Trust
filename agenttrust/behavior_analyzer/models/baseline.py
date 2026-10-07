"""
Baseline profile models for per-agent behavioral statistics.

Uses Welford's online algorithm internally so baselines can be
updated incrementally without storing raw history.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class WelfordAccumulator:
    """
    Online mean/variance accumulator using Welford's method.
    O(1) space, numerically stable, supports incremental updates.

    Reference: Welford (1962) — Technometrics
    """
    n: int = 0
    mean: float = 0.0
    M2: float = 0.0   # sum of squared deviations from mean

    def update(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self.M2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 0.0
        return self.M2 / (self.n - 1)   # sample variance

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def zscore(self, value: float) -> float:
        """Signed Z-score of a new observation. Returns 0.0 if std ≈ 0."""
        if self.std < 1e-9:
            return 0.0
        return (value - self.mean) / self.std

    def to_dict(self) -> Dict[str, float]:
        return {"n": float(self.n), "mean": self.mean, "M2": self.M2}

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "WelfordAccumulator":
        obj = cls()
        obj.n = int(d.get("n", 0))
        obj.mean = d.get("mean", 0.0)
        obj.M2 = d.get("M2", 0.0)
        return obj


@dataclass
class ToolBaseline:
    """Per-tool statistical baseline for a single agent."""
    tool_name: str
    call_frequency: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    param_count: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    param_size: WelfordAccumulator = field(default_factory=WelfordAccumulator)
    exec_duration_ms: WelfordAccumulator = field(default_factory=WelfordAccumulator)

    # Hour-of-day histogram (24 bins)
    hour_histogram: List[int] = field(default_factory=lambda: [0] * 24)
    # Day-of-week histogram (7 bins, 0=Mon)
    dow_histogram: List[int] = field(default_factory=lambda: [0] * 7)

    def update_temporal(self, hour: int, dow: int) -> None:
        self.hour_histogram[hour % 24] += 1
        self.dow_histogram[dow % 7] += 1

    def total_calls(self) -> int:
        return sum(self.hour_histogram)


@dataclass
class AgentBaseline:
    """
    Complete behavioral baseline for a single agent.
    Aggregates per-tool statistics and global agent-level metrics.
    """
    agent_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Per-tool baselines
    tools: Dict[str, ToolBaseline] = field(default_factory=dict)

    # Agent-level accumulator: events per time window
    events_per_window: WelfordAccumulator = field(default_factory=WelfordAccumulator)

    # Delegation depth accumulator
    delegation_depth: WelfordAccumulator = field(default_factory=WelfordAccumulator)

    # Recent raw feature vectors for Isolation Forest retraining
    # Capped at config.baseline_window_size
    recent_feature_vectors: List[List[float]] = field(default_factory=list)

    # Count of events processed since last IF model retrain
    events_since_retrain: int = 0

    # Total lifetime event count
    total_events: int = 0

    def get_or_create_tool(self, tool_name: str) -> ToolBaseline:
        if tool_name not in self.tools:
            self.tools[tool_name] = ToolBaseline(tool_name=tool_name)
        return self.tools[tool_name]

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def add_feature_vector(self, vector: List[float], max_size: int = 500) -> None:
        self.recent_feature_vectors.append(vector)
        if len(self.recent_feature_vectors) > max_size:
            # Remove oldest entries (FIFO)
            self.recent_feature_vectors = self.recent_feature_vectors[-max_size:]

    @property
    def has_sufficient_data(self) -> bool:
        return self.total_events >= 10   # overridden by config


@dataclass
class BaselineSummary:
    """Lightweight summary returned to callers — no heavy accumulators."""
    agent_id: str
    total_events: int
    known_tools: List[str]
    updated_at: Optional[datetime]
    has_sufficient_data: bool
