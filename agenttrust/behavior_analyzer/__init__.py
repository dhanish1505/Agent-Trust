"""
behavior_analyzer — Standalone Behavioral Anomaly Detection Module
=================================================================

A high-end, production-grade Python module for detecting anomalous
behavior in multi-agent AI systems.

Quick Start
-----------
    import asyncio
    from behavior_analyzer import BehaviorAnalyzer, AgentEvent, ToolCall

    analyzer = BehaviorAnalyzer()

    event = AgentEvent(
        agent_id="agent-001",
        tool_call=ToolCall("read_file", {"path": "/etc/passwd"}),
        sensitivity_score=0.9,
    )

    report = asyncio.run(analyzer.analyze(event))
    print(f"Anomaly score: {report.anomaly_score:.4f} [{report.severity.value}]")
    print(report.to_dict())

Architecture
------------
    BehaviorAnalyzer
        └── AnalysisPipeline
                ├── ZScoreDetector          (statistical deviation)
                ├── IsolationForestDetector (ML multi-dimensional)
                ├── TemporalPatternDetector (time-based patterns)
                ├── FrequencyDetector       (burst/rate analysis)
                ├── ParameterDeviationDetector (payload anomalies)
                └── DelegationChainDetector    (privilege escalation)
"""
from __future__ import annotations

from typing import Optional

from .config import BehaviorAnalyzerConfig, get_config
from .core.pipeline import AnalysisPipeline
from .core.registry import DetectorRegistry, default_registry
from .detectors import (
    DelegationChainDetector,
    FrequencyDetector,
    IsolationForestDetector,
    ParameterDeviationDetector,
    TemporalPatternDetector,
    ZScoreDetector,
)
from .models.events import AgentEvent, AgentRole, DelegationInfo, ToolCall
from .models.result import AnomalyReport, AnomalySeverity, DetectorResult
from .store.base import AbstractBaselineStore
from .store.memory_store import InMemoryBaselineStore


def _build_default_registry(config: BehaviorAnalyzerConfig) -> DetectorRegistry:
    """Register all built-in detectors into a fresh registry."""
    registry = DetectorRegistry()
    registry.register_many(
        ZScoreDetector,
        IsolationForestDetector,
        TemporalPatternDetector,
        FrequencyDetector,
        ParameterDeviationDetector,
        DelegationChainDetector,
    )
    # Disable detectors whose weight is 0 in config
    for name, weight in config.detector_weights.items():
        if weight == 0.0 and name in registry:
            registry.disable(name)
    return registry


class BehaviorAnalyzer:
    """
    High-level facade over the full analysis pipeline.

    This is the primary entry point for external consumers.

    Parameters
    ----------
    config : BehaviorAnalyzerConfig, optional
        Configuration object. Defaults to settings from environment.
    store : AbstractBaselineStore, optional
        Baseline persistence backend. Defaults to InMemoryBaselineStore.
    registry : DetectorRegistry, optional
        Custom registry. Defaults to all built-in detectors enabled.
    """

    def __init__(
        self,
        config: Optional[BehaviorAnalyzerConfig] = None,
        store: Optional[AbstractBaselineStore] = None,
        registry: Optional[DetectorRegistry] = None,
    ) -> None:
        self.config = config or get_config()
        self.store = store or InMemoryBaselineStore()
        self.registry = registry or _build_default_registry(self.config)
        self._pipeline = AnalysisPipeline(
            registry=self.registry,
            store=self.store,
            config=self.config,
        )

    async def analyze(self, event: AgentEvent) -> AnomalyReport:
        """
        Analyze a single agent event and return an AnomalyReport.

        This is the main API method. Never raises — returns a report
        with anomaly_score=0.0 and insufficient_data=True if baseline
        is not yet warm.
        """
        return await self._pipeline.analyze(event)

    def disable_detector(self, name: str) -> None:
        """Disable a detector by name without restarting."""
        self.registry.disable(name)

    def enable_detector(self, name: str) -> None:
        """Re-enable a previously disabled detector."""
        self.registry.enable(name)

    @property
    def active_detectors(self):
        return self.registry.enabled_names()

    def __repr__(self) -> str:
        return f"BehaviorAnalyzer(detectors={self.active_detectors})"


__all__ = [
    # Facade
    "BehaviorAnalyzer",
    # Models
    "AgentEvent", "AgentRole", "DelegationInfo", "ToolCall",
    "AnomalyReport", "AnomalySeverity", "DetectorResult",
    # Config
    "BehaviorAnalyzerConfig", "get_config",
    # Core
    "AnalysisPipeline", "DetectorRegistry",
    # Store
    "AbstractBaselineStore", "InMemoryBaselineStore",
    # Detectors (for custom registries)
    "ZScoreDetector", "IsolationForestDetector", "TemporalPatternDetector",
    "FrequencyDetector", "ParameterDeviationDetector", "DelegationChainDetector",
]

__version__ = "1.0.0"
