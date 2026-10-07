"""
Abstract store protocol for AgentBaseline persistence.
Swap backends (memory ↔ Redis) by injecting a different implementation.
"""
from __future__ import annotations

import abc
from typing import List, Optional

from ..models.baseline import AgentBaseline


class AbstractBaselineStore(abc.ABC):
    """
    Key-value store interface for AgentBaseline objects.
    All methods are async to allow Redis, DB, or HTTP backends.
    """

    @abc.abstractmethod
    async def get(self, agent_id: str) -> AgentBaseline:
        """
        Retrieve baseline for agent_id.
        Raises StoreKeyNotFoundError if not found.
        """
        ...

    @abc.abstractmethod
    async def set(self, baseline: AgentBaseline) -> None:
        """Persist (upsert) a baseline."""
        ...

    @abc.abstractmethod
    async def delete(self, agent_id: str) -> None:
        """Remove a baseline."""
        ...

    @abc.abstractmethod
    async def exists(self, agent_id: str) -> bool:
        """Check if a baseline exists without fetching it."""
        ...

    @abc.abstractmethod
    async def list_agent_ids(self) -> List[str]:
        """Return all stored agent IDs."""
        ...

    async def get_or_create(self, agent_id: str) -> AgentBaseline:
        """Convenience: fetch existing or create fresh baseline."""
        try:
            return await self.get(agent_id)
        except Exception:
            return AgentBaseline(agent_id=agent_id)
