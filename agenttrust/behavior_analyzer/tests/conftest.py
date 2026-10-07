import asyncio
import random
from datetime import datetime, timezone
import pytest
import pytest_asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from behavior_analyzer import (
    AgentEvent, AgentRole, BehaviorAnalyzer,
    BehaviorAnalyzerConfig, DelegationInfo, ToolCall,
)
from behavior_analyzer.models.baseline import AgentBaseline
from behavior_analyzer.store.memory_store import InMemoryBaselineStore

@pytest.fixture
def config() -> BehaviorAnalyzerConfig:
    return BehaviorAnalyzerConfig(
        min_samples_for_anomaly=5,
        zscore_threshold=2.0,
        rate_burst_multiplier=2.0,
        max_delegation_depth=2,
        isolation_forest_n_estimators=10,
        use_redis=False,
    )

@pytest.fixture
def store() -> InMemoryBaselineStore:
    return InMemoryBaselineStore()

@pytest.fixture
def analyzer(config, store) -> BehaviorAnalyzer:
    return BehaviorAnalyzer(config=config, store=store)

def make_event(
    agent_id: str = "test-agent",
    tool_name: str = "read_file",
    hour: int = 10,
    param_size: int = 100,
    sensitivity: float = 0.2,
    delegation_depth: int = 0,
) -> AgentEvent:
    ts = datetime.now(timezone.utc).replace(hour=hour)
    delegation = None
    if delegation_depth > 0:
        delegation = DelegationInfo(
            delegated_by="parent-agent",
            chain_depth=delegation_depth,
            delegation_token="tok-test",
        )
    return AgentEvent(
        agent_id=agent_id,
        agent_role=AgentRole.DATA,
        tool_call=ToolCall(
            tool_name=tool_name,
            parameters={"path": "/data/file.csv", "payload": "A" * param_size},
        ),
        sensitivity_score=sensitivity,
        timestamp=ts,
        delegation=delegation,
    )

async def warm_baseline(analyzer: BehaviorAnalyzer, agent_id: str, n: int = 20) -> None:
    for _ in range(n):
        e = make_event(
            agent_id=agent_id,
            tool_name=random.choice(["read_file", "query_db"]),
            hour=random.randint(9, 17),
            param_size=random.randint(80, 150),
        )
        await analyzer.analyze(e)
        # Yield to event loop to allow background tasks (like baseline update) to run
        await asyncio.sleep(0.01)

@pytest.fixture
def event_factory():
    return make_event
