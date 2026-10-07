"""
InMemoryBaselineStore — thread-safe in-memory store for testing and standalone use.
All data is lost on process restart.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Dict, List

from ..exceptions import StoreKeyNotFoundError
from ..models.baseline import AgentBaseline
from .base import AbstractBaselineStore


class InMemoryBaselineStore(AbstractBaselineStore):
    """
    Simple dict-backed store protected by asyncio.Lock.
    Zero dependencies — ideal for unit tests and local development.
    """

    def __init__(self) -> None:
        self._data: Dict[str, AgentBaseline] = {}
        self._lock = asyncio.Lock()

    async def get(self, agent_id: str) -> AgentBaseline:
        async with self._lock:
            if agent_id not in self._data:
                raise StoreKeyNotFoundError(agent_id)
            return deepcopy(self._data[agent_id])

    async def set(self, baseline: AgentBaseline) -> None:
        async with self._lock:
            self._data[baseline.agent_id] = deepcopy(baseline)

    async def delete(self, agent_id: str) -> None:
        async with self._lock:
            self._data.pop(agent_id, None)

    async def exists(self, agent_id: str) -> bool:
        async with self._lock:
            return agent_id in self._data

    async def list_agent_ids(self) -> List[str]:
        async with self._lock:
            return list(self._data.keys())

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"InMemoryBaselineStore(agents={len(self._data)})"
