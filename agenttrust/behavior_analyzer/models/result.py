"""
Result models produced by detectors and the analysis pipeline.

AnomalyReport is the final output consumed by the Risk Evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AnomalySeverity(str, Enum):
    """Human-readable severity derived from anomaly score ranges."""
    NONE = "NONE"           # 0.00 – 0.20
    LOW = "LOW"             # 0.20 – 0.40
    MEDIUM = "MEDIUM"       # 0.40 – 0.60
    HIGH = "HIGH"           # 0.60 – 0.80
    CRITICAL = "CRITICAL"   # 0.80 – 1.00

    @classmethod
    def from_score(cls, score: float) -> "AnomalySeverity":
        if score < 0.20:
            return cls.NONE
        elif score < 0.40:
            return cls.LOW
        elif score < 0.60:
            return cls.MEDIUM
        elif score < 0.80:
            return cls.HIGH
        else:
            return cls.CRITICAL


@dataclass(frozen=True)
class DetectorResult:
    """
    Output from a single detector.

    score:    Normalized anomaly score in [0.0, 1.0].
    fired:    True if this detector considers the event anomalous.
    evidence: Human-readable dict with the data that triggered the score.
    """
    detector_name: str
    score: float                              # [0.0, 1.0]
    fired: bool
    confidence: float = 1.0                  # [0.0, 1.0] — how reliable this result is
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None              # set if detector errored (soft failure)

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", max(0.0, min(1.0, self.score)))
        object.__setattr__(self, "confidence", max(0.0, min(1.0, self.confidence)))


@dataclass
class AnomalyReport:
    """
    Final output of the Behavior Analyzer for a single AgentEvent.

    Consumed by the Risk Evaluator to calculate an overall risk score.
    Contains per-detector breakdown for full auditability.
    """
    # ── Identity ──────────────────────────────────────────────────────────────
    event_id: str
    agent_id: str

    # ── Composite score ───────────────────────────────────────────────────────
    anomaly_score: float = 0.0              # Weighted ensemble [0.0, 1.0]
    severity: AnomalySeverity = AnomalySeverity.NONE

    # ── Per-detector breakdown ────────────────────────────────────────────────
    detector_results: List[DetectorResult] = field(default_factory=list)

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    analysis_duration_ms: float = 0.0
    detectors_run: int = 0
    detectors_errored: int = 0
    insufficient_data: bool = False          # True if baseline not warm yet

    # ── Timestamp ─────────────────────────────────────────────────────────────
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.anomaly_score = max(0.0, min(1.0, self.anomaly_score))
        self.severity = AnomalySeverity.from_score(self.anomaly_score)

    @property
    def fired_detectors(self) -> List[DetectorResult]:
        return [r for r in self.detector_results if r.fired]

    @property
    def errored_detectors(self) -> List[DetectorResult]:
        return [r for r in self.detector_results if r.error is not None]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "anomaly_score": round(self.anomaly_score, 4),
            "severity": self.severity.value,
            "insufficient_data": self.insufficient_data,
            "detectors_run": self.detectors_run,
            "detectors_errored": self.detectors_errored,
            "analysis_duration_ms": round(self.analysis_duration_ms, 2),
            "analyzed_at": self.analyzed_at.isoformat(),
            "detector_breakdown": [
                {
                    "detector": r.detector_name,
                    "score": round(r.score, 4),
                    "fired": r.fired,
                    "confidence": round(r.confidence, 4),
                    "evidence": r.evidence,
                    **({"error": r.error} if r.error else {}),
                }
                for r in self.detector_results
            ],
        }
