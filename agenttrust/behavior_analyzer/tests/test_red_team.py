"""
Option 4: Red-Teaming & Security Test Cases

Tests adversarial scenarios against the Behavior Analyzer.
"""
import pytest
from behavior_analyzer.models.result import AnomalySeverity

@pytest.mark.asyncio
async def test_scenario_payload_explosion(analyzer, event_factory):
    from .conftest import warm_baseline
    await warm_baseline(analyzer, "red-team", n=20)
    
    # Send a massive payload not seen in baseline
    e = event_factory(agent_id="red-team", param_size=100000)
    report = await analyzer.analyze(e)
    
    assert report.anomaly_score > 0.2
    fired_names = [r.detector_name for r in report.fired_detectors]
    assert "parameter" in fired_names

@pytest.mark.asyncio
async def test_scenario_off_hours_sensitive(analyzer, event_factory):
    from .conftest import warm_baseline
    await warm_baseline(analyzer, "red-team", n=20)
    
    # Sensitive action at 3 AM
    e = event_factory(agent_id="red-team", hour=3, sensitivity=0.95)
    report = await analyzer.analyze(e)
    
    assert report.anomaly_score > 0.2
    fired_names = [r.detector_name for r in report.fired_detectors]
    assert "temporal" in fired_names
