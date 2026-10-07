"""
OnlineBaselineUpdater — incremental baseline update using Welford's algorithm.

Each call to ingest() updates per-tool and agent-level accumulators
in O(1) time and O(1) space — no raw event history needed.
"""
from __future__ import annotations

from ..models.baseline import AgentBaseline, ToolBaseline
from ..models.events import AgentEvent


class OnlineBaselineUpdater:
    """
    Stateless helper — call ingest() after every agent event to keep
    the baseline current. Mutates the passed AgentBaseline in place.
    """

    def ingest(self, event: AgentEvent, baseline: AgentBaseline, window_size: int = 500) -> None:
        """
        Update all baseline accumulators with data from event.
        O(1) time and space per call.
        """
        tc = event.tool_call
        tool_bl: ToolBaseline = baseline.get_or_create_tool(tc.tool_name)

        # ── Per-tool statistical updates ──────────────────────────────────────
        tool_bl.param_count.update(float(tc.parameter_count()))
        tool_bl.param_size.update(float(tc.parameter_size_bytes()))
        if tc.execution_duration_ms is not None:
            tool_bl.exec_duration_ms.update(tc.execution_duration_ms)

        # ── Temporal patterns ─────────────────────────────────────────────────
        tool_bl.update_temporal(event.hour_of_day, event.day_of_week)

        # ── Agent-level accumulators ──────────────────────────────────────────
        # Delegation depth (0 if not delegated)
        baseline.delegation_depth.update(float(event.delegation_depth))

        # ── Feature vector for Isolation Forest ───────────────────────────────
        baseline.add_feature_vector(event.feature_vector(), max_size=window_size)
        baseline.events_since_retrain += 1
        baseline.total_events += 1
        baseline.touch()
