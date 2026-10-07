"""
WeightedEnsembleAggregator — combines per-detector scores into one final score.

Strategy:
  composite = Σ (weight_i * score_i * confidence_i)  /  Σ (weight_i * confidence_i)

Confidence-weighted sum means low-confidence results (e.g. from errored detectors)
contribute proportionally less to the final score.
"""
from __future__ import annotations

from typing import Dict, List

import structlog

from ..models.result import DetectorResult

logger = structlog.get_logger(__name__)


class WeightedEnsembleAggregator:
    """
    Produces a single composite anomaly score in [0.0, 1.0] from
    a list of DetectorResult objects and a weight map.

    Weight map keys must match DetectorResult.detector_name.
    Detectors with no entry in the weight map receive a default weight of 0.05.
    """

    DEFAULT_WEIGHT = 0.05

    def aggregate(
        self,
        results: List[DetectorResult],
        weights: Dict[str, float],
    ) -> float:
        """
        Compute confidence-adjusted weighted mean.

        Returns 0.0 if results list is empty.
        """
        if not results:
            return 0.0

        numerator = 0.0
        denominator = 0.0

        for result in results:
            if result.error is not None:
                # Errored detectors contribute 0 — their confidence is already 0
                continue

            w = weights.get(result.detector_name, self.DEFAULT_WEIGHT)
            effective_weight = w * result.confidence
            numerator += effective_weight * result.score
            denominator += effective_weight

        if denominator < 1e-9:
            # All detectors errored or had zero confidence
            logger.warning("aggregator.zero_denominator")
            return 0.0

        composite = numerator / denominator
        composite = max(0.0, min(1.0, composite))

        logger.debug(
            "aggregator.result",
            composite=round(composite, 4),
            active_detectors=len([r for r in results if not r.error]),
        )
        return composite


class MaxScoreAggregator:
    """
    Alternative aggregator: returns the maximum score across all detectors.
    Useful when any single detector firing should be treated as high risk.
    """

    def aggregate(
        self,
        results: List[DetectorResult],
        weights: Dict[str, float],
    ) -> float:
        valid = [r.score for r in results if r.error is None]
        return max(valid) if valid else 0.0
