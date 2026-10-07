import pytest
import dataclasses
from behavior_analyzer.detectors.parameter import ParameterDeviationDetector
from behavior_analyzer.detectors.delegation import DelegationChainDetector
from behavior_analyzer.config import BehaviorAnalyzerConfig
from behavior_analyzer.models.baseline import AgentBaseline
from behavior_analyzer.models.events import ToolCall

@pytest.mark.asyncio
async def test_parameter_injection_detection(event_factory, config):
    detector = ParameterDeviationDetector(config=config)
    baseline = AgentBaseline(agent_id="test-agent")

    # Normal event
    normal_event = event_factory(param_size=100)
    res1 = await detector.analyze(normal_event, baseline, config)
    assert not res1.fired

    # SQL Injection event
    sqli_event = event_factory(param_size=100)
    # properly replace tool_call parameters
    new_tc = dataclasses.replace(sqli_event.tool_call, parameters={"query": "DROP TABLE users;"})
    sqli_event = dataclasses.replace(sqli_event, tool_call=new_tc)
    
    res2 = await detector.analyze(sqli_event, baseline, config)
    assert res2.fired
    assert "injection_patterns" in res2.evidence

@pytest.mark.asyncio
async def test_delegation_depth_limit(event_factory, config):
    detector = DelegationChainDetector(config=config)
    baseline = AgentBaseline(agent_id="test-agent")

    # Depth 1 (OK)
    e1 = event_factory(delegation_depth=1)
    res1 = await detector.analyze(e1, baseline, config)
    assert not res1.fired

    # Depth 3 (Exceeds max of 2)
    e3 = event_factory(delegation_depth=3)
    res3 = await detector.analyze(e3, baseline, config)
    assert res3.fired

@pytest.mark.asyncio
async def test_self_delegation(event_factory, config):
    detector = DelegationChainDetector(config=config)
    baseline = AgentBaseline(agent_id="test-agent")

    event = event_factory(delegation_depth=1)
    # properly replace delegation
    new_del = dataclasses.replace(event.delegation, delegated_by="test-agent")
    event = dataclasses.replace(event, delegation=new_del)
    
    res = await detector.analyze(event, baseline, config)
    assert res.fired
    assert res.evidence.get("self_delegation") is True
