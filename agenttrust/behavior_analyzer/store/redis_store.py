"""
RedisBaselineStore — production-grade Redis-backed baseline store.

Serialization: pickle (fast, supports dataclasses with numpy arrays).
Keys:
  baseline:{agent_id}   → serialized AgentBaseline
  ba:agent_ids          → Redis Set of all known agent IDs
"""
from __future__ import annotations

import logging
import pickle
from typing import List, Optional

import structlog

from ..config import BehaviorAnalyzerConfig, get_config
from ..exceptions import StoreConnectionError, StoreKeyNotFoundError
from ..models.baseline import AgentBaseline
from .base import AbstractBaselineStore

logger = structlog.get_logger(__name__)

_BASELINE_PREFIX = "ba:baseline:"
_AGENT_SET_KEY = "ba:agent_ids"


class RedisBaselineStore(AbstractBaselineStore):
    """
    Redis-backed store using the `redis.asyncio` client.

    Connection is lazy — established on first use.
    """

    def __init__(
        self,
        config: Optional[BehaviorAnalyzerConfig] = None,
        redis_client=None,
    ) -> None:
        self.config = config or get_config()
        self._client = redis_client  # injected or created lazily
        self._ttl = self.config.cache_ttl_baseline

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(
                    self.config.redis_url,
                    encoding="utf-8",
                    decode_responses=False,  # binary — we use pickle
                )
            except Exception as exc:
                raise StoreConnectionError(
                    f"Cannot connect to Redis at {self.config.redis_url}: {exc}"
                ) from exc
        return self._client

    def _key(self, agent_id: str) -> str:
        return f"{_BASELINE_PREFIX}{agent_id}"

    async def get(self, agent_id: str) -> AgentBaseline:
        client = await self._get_client()
        raw = await client.get(self._key(agent_id))
        if raw is None:
            raise StoreKeyNotFoundError(agent_id)
        return pickle.loads(raw)

    async def set(self, baseline: AgentBaseline) -> None:
        client = await self._get_client()
        raw = pickle.dumps(baseline, protocol=pickle.HIGHEST_PROTOCOL)
        pipe = client.pipeline()
        pipe.set(self._key(baseline.agent_id), raw, ex=self._ttl)
        pipe.sadd(_AGENT_SET_KEY, baseline.agent_id)
        await pipe.execute()

    async def delete(self, agent_id: str) -> None:
        client = await self._get_client()
        pipe = client.pipeline()
        pipe.delete(self._key(agent_id))
        pipe.srem(_AGENT_SET_KEY, agent_id)
        await pipe.execute()

    async def exists(self, agent_id: str) -> bool:
        client = await self._get_client()
        return bool(await client.exists(self._key(agent_id)))

    async def list_agent_ids(self) -> List[str]:
        client = await self._get_client()
        members = await client.smembers(_AGENT_SET_KEY)
        return [m.decode() if isinstance(m, bytes) else m for m in members]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
