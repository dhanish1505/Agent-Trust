"""
DetectorRegistry — plugin system for detectors.

Implements the Strategy + Registry patterns:
  - Detectors are registered by name at import time (or manually).
  - The registry is the single source of truth for which detectors are active.
  - Detectors can be added, removed, enabled/disabled at runtime without
    restarting the application.
"""
from __future__ import annotations

import threading
from typing import Dict, Iterator, List, Optional, Type

import structlog

from ..exceptions import DetectorNotRegisteredError
from .base_detector import BaseDetector

logger = structlog.get_logger(__name__)


class DetectorRegistry:
    """
    Thread-safe registry of detector classes.

    Usage:
        registry = DetectorRegistry()
        registry.register(ZScoreDetector)
        registry.register(IsolationForestDetector)

        for detector in registry.enabled_detectors():
            ...
    """

    def __init__(self) -> None:
        self._detectors: Dict[str, Type[BaseDetector]] = {}
        self._disabled: set[str] = set()
        self._lock = threading.RLock()

    # ── Registration ──────────────────────────────────────────────────────────

    def register(
        self,
        detector_cls: Type[BaseDetector],
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a detector class. Raises if name already exists unless overwrite=True."""
        with self._lock:
            name = detector_cls.name
            if name in self._detectors and not overwrite:
                raise ValueError(
                    f"Detector '{name}' is already registered. "
                    "Use overwrite=True to replace it."
                )
            self._detectors[name] = detector_cls
            logger.debug("detector.registered", name=name)

    def register_many(self, *detector_classes: Type[BaseDetector]) -> None:
        for cls in detector_classes:
            self.register(cls)

    def unregister(self, name: str) -> None:
        with self._lock:
            removed = self._detectors.pop(name, None)
            self._disabled.discard(name)
            if removed:
                logger.debug("detector.unregistered", name=name)

    # ── Enable / Disable ──────────────────────────────────────────────────────

    def disable(self, name: str) -> None:
        """Disable a detector without removing it (reversible)."""
        with self._lock:
            if name not in self._detectors:
                raise DetectorNotRegisteredError(name)
            self._disabled.add(name)
            logger.info("detector.disabled", name=name)

    def enable(self, name: str) -> None:
        with self._lock:
            if name not in self._detectors:
                raise DetectorNotRegisteredError(name)
            self._disabled.discard(name)
            logger.info("detector.enabled", name=name)

    # ── Querying ──────────────────────────────────────────────────────────────

    def get(self, name: str) -> Type[BaseDetector]:
        with self._lock:
            if name not in self._detectors:
                raise DetectorNotRegisteredError(name)
            return self._detectors[name]

    def all_names(self) -> List[str]:
        with self._lock:
            return list(self._detectors.keys())

    def enabled_names(self) -> List[str]:
        with self._lock:
            return [n for n in self._detectors if n not in self._disabled]

    def disabled_names(self) -> List[str]:
        with self._lock:
            return list(self._disabled)

    def instantiate_enabled(
        self,
        config=None,
    ) -> List[BaseDetector]:
        """Return instantiated detector objects for all enabled detectors."""
        with self._lock:
            return [
                cls(config=config)
                for name, cls in self._detectors.items()
                if name not in self._disabled
            ]

    def __len__(self) -> int:
        return len(self._detectors)

    def __iter__(self) -> Iterator[str]:
        return iter(self._detectors)

    def __contains__(self, name: str) -> bool:
        return name in self._detectors

    def __repr__(self) -> str:
        names = ", ".join(self.enabled_names())
        return f"DetectorRegistry(enabled=[{names}])"


# ── Module-level singleton registry ───────────────────────────────────────────
# Import this to register detectors and share state across the module.
default_registry = DetectorRegistry()
