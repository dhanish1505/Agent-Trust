"""
AnalysisPipeline — orchestrates concurrent detector execution.

Design:
  1. Fetch (or create) agent baseline from store
  2. Fan-out: run all enabled detectors concurrently via asyncio.gather()
  3. Aggregate results via WeightedEnsembleAggregator
  4. Update baseline with the new event (online learning)
  5. Return AnomalyReport

Error philosophy: any single detector failure is isolated (soft failure).
The pipeline only hard-fails if the baseline store is unreachable.
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Optional

import structlog

from ..config import BehaviorAnalyzerConfig, get_config
from ..exceptions import InsufficientDataError
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import AnomalyReport, DetectorResult
from ..store.base import AbstractBaselineStore
from ..store.memory_store import InMemoryBaselineStore
from .base_detector import BaseDetector
from .registry import DetectorRegistry, default_registry

logger = structlog.get_logger(__name__)


class AnalysisPipeline:
    """
    Async pipeline that coordinates the full behavioral analysis flow.

    Instantiate once, reuse for all events (stateless per-call).
    The baseline store holds all mutable state.
    """

    def __init__(
        self,
        registry: Optional[DetectorRegistry] = None,
        store: Optional[AbstractBaselineStore] = None,
        config: Optional[BehaviorAnalyzerConfig] = None,
        aggregator=None,
    ) -> None:
        self.config = config or get_config()
        self.registry = registry or default_registry
        self.store: AbstractBaselineStore = store or InMemoryBaselineStore()
        self._aggregator = aggregator  # injected; resolved lazily to avoid circular import

    # ── Public API ────────────────────────────────────────────────────────────

    async def analyze(self, event: AgentEvent) -> AnomalyReport:
        """
        Full analysis of a single AgentEvent.
        Always returns an AnomalyReport — never raises.
        """
        bound = logger.bind(agent_id=event.agent_id, event_id=event.event_id)
        bound.info("pipeline.analyze.start", tool=event.tool_call.tool_name)

        t0 = time.perf_counter()

        # 1. Load or create baseline
        baseline = await self._load_baseline(event.agent_id)

        # 2. Check if we have enough data
        has_data = baseline.total_events >= self.config.min_samples_for_anomaly

        # 3. Fan-out across all enabled detectors
        detector_results: List[DetectorResult] = []
        if has_data:
            detector_results = await self._run_detectors(event, baseline)
        else:
            bound.info(
                "pipeline.insufficient_data",
                total_events=baseline.total_events,
                required=self.config.min_samples_for_anomaly,
            )

        # 4. Aggregate scores
        aggregator = self._get_aggregator()
        composite_score = aggregator.aggregate(
            detector_results,
            self.config.normalized_weights(),
        ) if has_data else 0.0

        # 5. Update baseline (fire-and-forget background task)
        asyncio.create_task(self._update_baseline(event, baseline))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        errored = sum(1 for r in detector_results if r.error)

        report = AnomalyReport(
            event_id=event.event_id,
            agent_id=event.agent_id,
            anomaly_score=composite_score,
            detector_results=detector_results,
            analysis_duration_ms=elapsed_ms,
            detectors_run=len(detector_results),
            detectors_errored=errored,
            insufficient_data=not has_data,
        )

        bound.info(
            "pipeline.analyze.complete",
            score=round(composite_score, 4),
            severity=report.severity.value,
            duration_ms=round(elapsed_ms, 2),
            detectors_run=report.detectors_run,
        )
        return report

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _load_baseline(self, agent_id: str) -> AgentBaseline:
        try:
            return await self.store.get(agent_id)
        except Exception:
            return AgentBaseline(agent_id=agent_id)

    async def _run_detectors(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
    ) -> List[DetectorResult]:
        """Fan-out: run all detectors concurrently."""
        detectors: List[BaseDetector] = self.registry.instantiate_enabled(self.config)
        if not detectors:
            logger.warning("pipeline.no_detectors")
            return []

        tasks = [
            detector.analyze(event, baseline, self.config)
            for detector in detectors
        ]
        results: List[DetectorResult] = await asyncio.gather(*tasks, return_exceptions=False)
        return results

    async def _update_baseline(self, event: AgentEvent, baseline: AgentBaseline) -> None:
        """Online baseline update — called as background asyncio task."""
        from ..baseline.manager import BaselineManager
        manager = BaselineManager(self.store, self.config)
        try:
            await manager.ingest_event(event, baseline)
        except Exception as exc:
            logger.error("pipeline.baseline_update_failed", error=str(exc))

    def _get_aggregator(self):
        if self._aggregator is None:
            from ..scoring.aggregator import WeightedEnsembleAggregator
            self._aggregator = WeightedEnsembleAggregator()
        return self._aggregator
