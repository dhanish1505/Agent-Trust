"""
Custom exception hierarchy for the Behavior Analyzer module.

All exceptions inherit from BehaviorAnalyzerError so callers
can catch everything with a single except clause if needed.
"""
from __future__ import annotations


class BehaviorAnalyzerError(Exception):
    """Root exception for all Behavior Analyzer errors."""


# ── Configuration ─────────────────────────────────────────────────────────────

class ConfigurationError(BehaviorAnalyzerError):
    """Invalid or missing configuration."""


# ── Storage ───────────────────────────────────────────────────────────────────

class StoreError(BehaviorAnalyzerError):
    """Base class for storage backend errors."""


class StoreConnectionError(StoreError):
    """Cannot connect to storage backend."""


class StoreKeyNotFoundError(StoreError):
    """Requested key does not exist in the store."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Key not found in store: {key!r}")


# ── Baseline ──────────────────────────────────────────────────────────────────

class BaselineError(BehaviorAnalyzerError):
    """Base class for baseline-related errors."""


class InsufficientDataError(BaselineError):
    """Not enough data points to compute a reliable baseline or anomaly score."""

    def __init__(self, agent_id: str, current: int, required: int) -> None:
        self.agent_id = agent_id
        self.current = current
        self.required = required
        super().__init__(
            f"Agent '{agent_id}' has {current} samples; need ≥ {required} "
            "before anomaly detection activates."
        )


# ── Detector ──────────────────────────────────────────────────────────────────

class DetectorError(BehaviorAnalyzerError):
    """A detector failed during analysis."""

    def __init__(self, detector_name: str, reason: str) -> None:
        self.detector_name = detector_name
        super().__init__(f"Detector '{detector_name}' failed: {reason}")


class DetectorNotRegisteredError(DetectorError):
    """Detector name not found in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "not registered in DetectorRegistry")


# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineError(BehaviorAnalyzerError):
    """Analysis pipeline encountered an unrecoverable error."""
