"""
ZScoreDetector — Statistical deviation anomaly detector.

Checks each observable feature of the incoming event against the agent's
historical baseline using Z-scores (Welford online statistics).

A high absolute Z-score on any key metric (parameter count, payload size,
call frequency) indicates the current event deviates significantly from
past behavior — a common signal for data exfiltration or misuse.
"""
from __future__ import annotations

import math
from typing import ClassVar, Dict, List, Tuple

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline, WelfordAccumulator
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector


class ZScoreDetector(BaseDetector):
    """
    Detects: unexpected tool call frequency, parameter count deviation,
    parameter payload size anomalies.

    Score formula:
        max_z = max(|z_score|) across all checked features
        score  = min(1.0, max_z / (3 * threshold))

    A perfectly average event scores 0.0; a 3σ outlier scores ≈ 0.33;
    a 9σ outlier scores 1.0.
    """

    name: ClassVar[str] = "zscore"
    default_weight: ClassVar[float] = 0.20

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        tc = event.tool_call
        tool_bl = baseline.tools.get(tc.tool_name)

        if tool_bl is None or tool_bl.call_frequency.n < config.min_samples_for_anomaly:
            return self.make_result(
                score=0.0,
                fired=False,
                confidence=0.0,
                reason="insufficient_tool_data",
            )

        threshold = config.zscore_threshold
        checks: List[Tuple[str, WelfordAccumulator, float]] = [
            ("param_count",   tool_bl.param_count, float(tc.parameter_count())),
            ("param_size",    tool_bl.param_size,  float(tc.parameter_size_bytes())),
        ]
        if tc.execution_duration_ms is not None:
            checks.append(("exec_duration_ms", tool_bl.exec_duration_ms, tc.execution_duration_ms))

        evidence: Dict[str, float] = {}
        max_abs_z = 0.0

        for feature_name, acc, value in checks:
            z = acc.zscore(value)
            evidence[f"z_{feature_name}"] = round(z, 4)
            evidence[f"mean_{feature_name}"] = round(acc.mean, 4)
            evidence[f"std_{feature_name}"] = round(acc.std, 4)
            evidence[f"value_{feature_name}"] = round(value, 4)
            if abs(z) > abs(max_abs_z):
                max_abs_z = z

        # Normalize to [0, 1] — score saturates at 3× threshold
        score = min(1.0, abs(max_abs_z) / (3.0 * threshold))
        fired = abs(max_abs_z) >= threshold

        evidence["max_abs_zscore"] = round(max_abs_z, 4)
        evidence["threshold"] = threshold

        return DetectorResult(
            detector_name=self.name,
            score=score,
            fired=fired,
            confidence=min(1.0, tool_bl.param_count.n / 50.0),  # grows with data
            evidence=evidence,
        )
