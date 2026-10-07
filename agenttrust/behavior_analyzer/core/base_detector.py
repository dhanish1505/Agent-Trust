"""
Abstract base for all Behavior Analyzer detectors.

Uses both ABC (for enforcement) and Protocol (for structural typing)
so detectors can be used duck-typed in generic code without inheritance.
"""
from __future__ import annotations

import abc
import logging
from typing import ClassVar, Optional, Protocol, runtime_checkable

import structlog

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult

logger = structlog.get_logger(__name__)


@runtime_checkable
class DetectorProtocol(Protocol):
    """
    Structural protocol — any object with these methods is a valid detector.
    Enables duck-typed usage without explicit inheritance.
    """
    name: ClassVar[str]
    weight: ClassVar[float]

    async def analyze(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult: ...


class BaseDetector(abc.ABC):
    """
    Abstract base class for all concrete detectors.

    Subclasses MUST override:
        - name (ClassVar[str])        — unique detector identifier
        - default_weight (float)      — default ensemble weight
        - _run(event, baseline, config) → DetectorResult

    The public `analyze()` method wraps `_run()` with:
        - Structured logging (entry / exit / error)
        - Exception isolation — detector failures become DetectorResult.error
          rather than crashing the pipeline (soft failure)
        - Timing measurement
    """

    #: Unique identifier used as dict key in DetectorRegistry
    name: ClassVar[str]

    #: Default weight in the ensemble (can be overridden by config)
    default_weight: ClassVar[float] = 0.10

    def __init__(self, config: Optional[BehaviorAnalyzerConfig] = None) -> None:
        self.config = config or BehaviorAnalyzerConfig()
        self._log = structlog.get_logger(self.__class__.__name__)

    async def analyze(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        """
        Public entry point. Wraps _run() with error handling + logging.
        Never raises — returns a DetectorResult with error set on failure.
        """
        import time

        bound = self._log.bind(
            agent_id=event.agent_id,
            event_id=event.event_id,
            detector=self.name,
        )
        bound.debug("detector.start")
        t0 = time.perf_counter()

        try:
            result = await self._run(event, baseline, config)
            elapsed = (time.perf_counter() - t0) * 1000
            bound.debug(
                "detector.complete",
                score=round(result.score, 4),
                fired=result.fired,
                duration_ms=round(elapsed, 2),
            )
            return result

        except Exception as exc:  # noqa: BLE001
            elapsed = (time.perf_counter() - t0) * 1000
            bound.warning(
                "detector.error",
                error=str(exc),
                duration_ms=round(elapsed, 2),
            )
            # Soft failure — return neutral score, flag the error
            return DetectorResult(
                detector_name=self.name,
                score=0.0,
                fired=False,
                confidence=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )

    @abc.abstractmethod
    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        """
        Core detection logic. Implement this in every subclass.
        May raise exceptions — they are caught by analyze().
        """
        ...

    @classmethod
    def make_result(
        cls,
        score: float,
        fired: bool,
        confidence: float = 1.0,
        **evidence,
    ) -> DetectorResult:
        """Convenience factory so subclasses don't repeat boilerplate."""
        return DetectorResult(
            detector_name=cls.name,
            score=score,
            fired=fired,
            confidence=confidence,
            evidence=evidence,
        )
