"""
IsolationForestDetector — ML-based multi-dimensional anomaly detector.

Uses scikit-learn's IsolationForest on the agent's 7-dimensional feature vector:
  [hour_of_day, day_of_week, delegation_depth, param_count,
   param_size_bytes, sensitivity_score, is_delegated]

The model is pre-trained by BaselineManager on the agent's recent event history
and stored directly on the AgentBaseline object. If no model is available,
falls back to a coarse heuristic score.

Isolation Forest theory:
  - Anomalies are "isolated" earlier in random partition trees → shorter path length
  - score_samples() returns negative anomaly scores (more negative = more anomalous)
  - We remap [-0.5, 0.5] → [1.0, 0.0] for our convention
"""
from __future__ import annotations

from typing import ClassVar, List, Optional

import numpy as np

from ..config import BehaviorAnalyzerConfig
from ..models.baseline import AgentBaseline
from ..models.events import AgentEvent
from ..models.result import DetectorResult
from ..core.base_detector import BaseDetector


class IsolationForestDetector(BaseDetector):
    """
    Detects: multi-dimensional behavioral outliers that no single
    feature Z-score would catch (e.g. unusual combination of time + tool + depth).
    """

    name: ClassVar[str] = "isolation_forest"
    default_weight: ClassVar[float] = 0.25

    async def _run(
        self,
        event: AgentEvent,
        baseline: AgentBaseline,
        config: BehaviorAnalyzerConfig,
    ) -> DetectorResult:
        # Try to get pre-trained model from baseline object
        model = baseline.__dict__.get("_if_model")
        vectors = baseline.recent_feature_vectors

        if model is None:
            # Model not trained yet — try inline training if we have enough data
            if len(vectors) < config.min_samples_for_anomaly:
                return self.make_result(
                    score=0.0,
                    fired=False,
                    confidence=0.0,
                    reason="model_not_trained",
                )
            model = self._train_model(vectors, config)
            if model is None:
                return self.make_result(
                    score=0.0,
                    fired=False,
                    confidence=0.0,
                    reason="training_failed",
                )

        # Score the current event
        fv = np.array([event.feature_vector()], dtype=float)
        try:
            raw_score = float(model.score_samples(fv)[0])
        except Exception as exc:
            return self.make_result(
                score=0.0,
                fired=False,
                confidence=0.0,
                reason=f"scoring_failed: {exc}",
            )

        # IsolationForest score_samples returns values in roughly [-0.5, 0.5]
        # where more negative = more anomalous.
        # Remap to [0.0, 1.0]: anomaly_score = 1 - (raw + 0.5)
        #   raw=-0.5 (most anomalous) → score=1.0
        #   raw= 0.5 (most normal)    → score=0.0
        score = max(0.0, min(1.0, 1.0 - (raw_score + 0.5)))

        # Use IF's predict() as a hard threshold flag
        prediction = int(model.predict(fv)[0])   # -1 = anomaly, 1 = normal
        fired = prediction == -1

        confidence = min(1.0, len(vectors) / config.baseline_window_size)

        return DetectorResult(
            detector_name=self.name,
            score=score,
            fired=fired,
            confidence=confidence,
            evidence={
                "if_raw_score": round(raw_score, 6),
                "if_prediction": prediction,
                "feature_vector": [round(f, 4) for f in event.feature_vector()],
                "training_samples": len(vectors),
            },
        )

    @staticmethod
    def _train_model(vectors: List[List[float]], config: BehaviorAnalyzerConfig):
        try:
            from sklearn.ensemble import IsolationForest
            X = np.array(vectors, dtype=float)
            model = IsolationForest(
                n_estimators=config.isolation_forest_n_estimators,
                contamination=config.isolation_forest_contamination,
                random_state=42,
                n_jobs=-1,
            )
            model.fit(X)
            return model
        except Exception:
            return None
