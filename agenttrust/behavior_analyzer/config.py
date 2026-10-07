"""
BehaviorAnalyzerConfig — single source of truth for all tunable parameters.
Loaded from environment variables or .env file via pydantic-settings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectorWeights(dict):
    """Typed alias for detector weight mapping."""
    pass


class BehaviorAnalyzerConfig(BaseSettings):
    """
    All configuration for the Behavior Analyzer module.
    Prefix: BA_ (e.g. BA_REDIS_URL=redis://...)
    """
    model_config = SettingsConfigDict(
        env_prefix="BA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Storage backend ───────────────────────────────────────────────────────
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL. Leave empty to use in-memory store.",
    )
    use_redis: bool = Field(
        default=False,
        description="If True, use Redis store; otherwise use in-memory store.",
    )

    # ── Redis TTLs (seconds) ──────────────────────────────────────────────────
    cache_ttl_baseline: int = Field(default=600, ge=10)
    cache_ttl_rate_window: int = Field(default=3600, ge=60)

    # ── Baseline / online learning ────────────────────────────────────────────
    min_samples_for_anomaly: int = Field(
        default=10,
        ge=3,
        description="Min events before anomaly detectors activate.",
    )
    baseline_window_size: int = Field(
        default=500,
        ge=50,
        description="Max events retained per agent for Isolation Forest retraining.",
    )

    # ── Statistical detector ──────────────────────────────────────────────────
    zscore_threshold: float = Field(
        default=3.0,
        ge=1.0,
        description="Z-score magnitude considered anomalous.",
    )

    # ── Frequency / rate detector ─────────────────────────────────────────────
    rate_window_seconds: int = Field(default=60, ge=5)
    rate_burst_multiplier: float = Field(
        default=3.0,
        ge=1.5,
        description="Burst = actual_rate > multiplier * baseline_rate.",
    )

    # ── Temporal detector ─────────────────────────────────────────────────────
    temporal_hour_bins: int = Field(default=24, ge=4, le=24)
    temporal_anomaly_percentile: float = Field(default=0.05, gt=0.0, lt=1.0)

    # ── Delegation detector ───────────────────────────────────────────────────
    max_delegation_depth: int = Field(default=3, ge=1)
    delegation_velocity_window_seconds: int = Field(default=300, ge=10)
    max_delegations_in_window: int = Field(default=5, ge=1)

    # ── Isolation Forest ─────────────────────────────────────────────────────
    isolation_forest_contamination: float = Field(default=0.05, gt=0.0, lt=0.5)
    isolation_forest_n_estimators: int = Field(default=100, ge=10)
    isolation_forest_retrain_every: int = Field(
        default=50,
        ge=5,
        description="Retrain IF model every N new events.",
    )

    # ── Ensemble scoring weights (must sum ≤ 1.0 each, normalized internally) ─
    detector_weights: Dict[str, float] = Field(
        default={
            "zscore": 0.20,
            "isolation_forest": 0.25,
            "temporal": 0.15,
            "frequency": 0.20,
            "parameter": 0.10,
            "delegation": 0.10,
        }
    )

    @field_validator("detector_weights")
    @classmethod
    def weights_positive(cls, v: Dict[str, float]) -> Dict[str, float]:
        for name, w in v.items():
            if w < 0:
                raise ValueError(f"Weight for detector '{name}' must be ≥ 0, got {w}")
        return v

    def normalized_weights(self) -> Dict[str, float]:
        """Return weights normalized so they sum to 1.0."""
        total = sum(self.detector_weights.values())
        if total == 0:
            return {k: 1.0 / len(self.detector_weights) for k in self.detector_weights}
        return {k: v / total for k, v in self.detector_weights.items()}


@lru_cache(maxsize=1)
def get_config() -> BehaviorAnalyzerConfig:
    return BehaviorAnalyzerConfig()
