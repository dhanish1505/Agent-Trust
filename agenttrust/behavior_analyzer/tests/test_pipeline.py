"""
Tests for the full analysis pipeline.
"""
import pytest
from behavior_analyzer.models.result import AnomalySeverity

@pytest.mark.asyncio
async def test_pipeline_warmup(analyzer, event_factory):
    # Before warmup
    event1 = event_factory()
    report1 = await analyzer.analyze(event1)
    assert report1.insufficient_data is True
    assert report1.anomaly_score == 0.0

    # Warmup
    from .conftest import warm_baseline
    await warm_baseline(analyzer, "test-agent", n=10)

    # After warmup
    event2 = event_factory()
    report2 = await analyzer.analyze(event2)
    assert report2.insufficient_data is False
    assert report2.severity == AnomalySeverity.NONE

@pytest.mark.asyncio
async def test_pipeline_anomaly_detection(analyzer, event_factory):
    from .conftest import warm_baseline
    await warm_baseline(analyzer, "test-agent", n=15)

    # Inject anomaly (deep delegation + large payload)
    bad_event = event_factory(delegation_depth=5, param_size=50000, sensitivity=0.9)
    report = await analyzer.analyze(bad_event)
    
    assert report.insufficient_data is False
    assert report.anomaly_score > 0.5
    assert len(report.fired_detectors) > 0
