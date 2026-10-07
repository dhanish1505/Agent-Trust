"""
BaselineManager — high-level CRUD operations on AgentBaseline objects.

Wraps the store + updater into a single service class used by the pipeline.
Also owns the Isolation Forest retraining trigger logic.
"""
from __future__ import annotations

from typing import Optional

import structlog

from ..config import BehaviorAnalyzerConfig, get_config
from ..models.baseline import AgentBaseline, BaselineSummary
from ..models.events import AgentEvent
from ..store.base import AbstractBaselineStore
from ..store.memory_store import InMemoryBaselineStore
from .updater import OnlineBaselineUpdater

logger = structlog.get_logger(__name__)


class BaselineManager:
    """
    Orchestrates baseline persistence and online updates.

    The Isolation Forest detector accesses baseline.recent_feature_vectors
    directly — this manager ensures they stay fresh.
    """

    def __init__(
        self,
        store: Optional[AbstractBaselineStore] = None,
        config: Optional[BehaviorAnalyzerConfig] = None,
    ) -> None:
        self.store = store or InMemoryBaselineStore()
        self.config = config or get_config()
        self._updater = OnlineBaselineUpdater()

    async def ingest_event(self, event: AgentEvent, baseline: AgentBaseline) -> AgentBaseline:
        """
        Update the baseline with a new event and persist it.
        Called as a background task after analysis completes.
        """
        self._updater.ingest(event, baseline, window_size=self.config.baseline_window_size)

        # Trigger IF model retrain if enough new events accumulated
        if baseline.events_since_retrain >= self.config.isolation_forest_retrain_every:
            await self._retrain_isolation_forest(baseline)
            baseline.events_since_retrain = 0

        await self.store.set(baseline)
        logger.debug(
            "baseline.updated",
            agent_id=event.agent_id,
            total_events=baseline.total_events,
        )
        return baseline

    async def get_summary(self, agent_id: str) -> Optional[BaselineSummary]:
        """Returns a lightweight summary without heavy accumulators."""
        try:
            baseline = await self.store.get(agent_id)
            return BaselineSummary(
                agent_id=agent_id,
                total_events=baseline.total_events,
                known_tools=list(baseline.tools.keys()),
                updated_at=baseline.updated_at,
                has_sufficient_data=baseline.total_events >= self.config.min_samples_for_anomaly,
            )
        except Exception:
            return None

    async def reset(self, agent_id: str) -> None:
        """Wipe the baseline for an agent (e.g. after role change)."""
        await self.store.delete(agent_id)
        logger.info("baseline.reset", agent_id=agent_id)

    async def _retrain_isolation_forest(self, baseline: AgentBaseline) -> None:
        """
        Retrain the cached Isolation Forest model on recent feature vectors.
        The trained model is stored on the baseline object so the detector
        can use it without re-fitting every call.
        """
        vectors = baseline.recent_feature_vectors
        if len(vectors) < self.config.min_samples_for_anomaly:
            return

        try:
            import numpy as np
            from sklearn.ensemble import IsolationForest

            X = np.array(vectors, dtype=float)
            model = IsolationForest(
                n_estimators=self.config.isolation_forest_n_estimators,
                contamination=self.config.isolation_forest_contamination,
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X)
            # Store model directly on baseline object (in-memory or pickle-serialized to Redis)
            baseline.__dict__["_if_model"] = model
            logger.info(
                "baseline.if_model_retrained",
                agent_id=baseline.agent_id,
                n_samples=len(vectors),
            )
        except Exception as exc:
            logger.warning("baseline.if_retrain_failed", error=str(exc))


class BaselineManagerFactory:
    """Factory that creates BaselineManager with the correct store backend."""

    @staticmethod
    def create(config: Optional[BehaviorAnalyzerConfig] = None) -> BaselineManager:
        cfg = config or get_config()
        if cfg.use_redis:
            from ..store.redis_store import RedisBaselineStore
            store = RedisBaselineStore(config=cfg)
        else:
            store = InMemoryBaselineStore()
        return BaselineManager(store=store, config=cfg)
