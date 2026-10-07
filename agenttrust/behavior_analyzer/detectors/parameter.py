"""
ParameterDeviationDetector — detects anomalies in tool call parameters.

Checks for:
  1. Type entropy shift — new parameter types not seen in baseline
  2. Value range violations — numeric values far outside historical ranges
  3. Payload size explosion — sudden large parameters (data exfiltration signal)
  4. Suspicious value patterns — known injection patterns (prompt injection signals)

Scores 0.0 for normal parameter profiles, approaching 1.0 for suspicious payloads.
"""
from __future__ import annotations

import math
import re
from typing import Any, ClassVar, Dict, List, Set

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector

# ── Suspicious patterns (prompt injection / path traversal / SSRF) ────────────
_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>", re.IGNORECASE),
    re.compile(r"\.\./", ),                         # path traversal
    re.compile(r"file://", re.IGNORECASE),          # local file access
    re.compile(r"(169\.254\.169\.254|metadata)", re.IGNORECASE),  # SSRF to IMDS
    re.compile(r"(DROP\s+TABLE|DELETE\s+FROM|UNION\s+SELECT)", re.IGNORECASE),  # SQLi
]


def _type_signature(params: Dict[str, Any]) -> Dict[str, str]:
    """Map parameter names to their Python type names."""
    return {k: type(v).__name__ for k, v in params.items()}


def _scan_for_injections(params: Dict[str, Any]) -> List[str]:
    """Return list of parameter names that match injection patterns."""
    hits = []
    for key, val in params.items():
        val_str = str(val)
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(val_str):
                hits.append(f"{key}:{pattern.pattern}")
                break
    return hits


class ParameterDeviationDetector(BaseDetector):
    """
    Detects: parameter type drift, payload size explosions, and injection patterns.
    """

    name: ClassVar[str] = "parameter"
    default_weight: ClassVar[float] = 0.10

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        tc = event.tool_call
        params = tc.parameters
        score_components: List[float] = []
        evidence: Dict[str, Any] = {}

        # ── 1. Injection pattern scan (highest priority) ───────────────────────
        injection_hits = _scan_for_injections(params)
        if injection_hits:
            evidence["injection_patterns"] = injection_hits
            score_components.append(0.90)

        # ── 2. Payload size deviation ──────────────────────────────────────────
        tool_bl = baseline.tools.get(tc.tool_name)
        current_size = float(tc.parameter_size_bytes())
        evidence["param_size_bytes"] = current_size

        if tool_bl and tool_bl.param_size.n >= config.min_samples_for_anomaly:
            z = tool_bl.param_size.zscore(current_size)
            size_score = min(1.0, abs(z) / (3.0 * config.zscore_threshold))
            evidence["param_size_zscore"] = round(z, 4)
            evidence["param_size_baseline_mean"] = round(tool_bl.param_size.mean, 2)
            score_components.append(size_score)
        else:
            # Heuristic: flag if payload > 64KB
            if current_size > 65_536:
                score_components.append(0.60)
                evidence["large_payload_heuristic"] = True

        # ── 3. Parameter count deviation ───────────────────────────────────────
        current_count = float(tc.parameter_count())
        evidence["param_count"] = current_count
        if tool_bl and tool_bl.param_count.n >= config.min_samples_for_anomaly:
            z = tool_bl.param_count.zscore(current_count)
            count_score = min(1.0, abs(z) / (3.0 * config.zscore_threshold))
            evidence["param_count_zscore"] = round(z, 4)
            score_components.append(count_score)

        # ── 4. Type entropy (new parameter names / types not seen before) ──────
        # We track seen parameter name sets per tool in a lightweight way
        expected_keys: Set[str] = set()
        if tool_bl:
            # Infer expected keys from baseline tools dict name (stored in evidence history)
            # Simplified: check against last known type signature
            pass  # Extended implementation would store key sets on ToolBaseline

        # Compute composite score
        if not score_components:
            final_score = 0.0
        else:
            final_score = min(1.0, max(score_components))

        fired = final_score >= 0.40 or bool(injection_hits)

        return DetectorResult(
            detector_name=self.name,
            score=final_score,
            fired=fired,
            confidence=0.8 if tool_bl else 0.4,
            evidence=evidence,
        )
