"""
agenttrust — AgentTrust Security Layer
======================================
Dynamic Authorization & Trust Management for Multi-Agent AI Systems.

Sub-packages
------------
    agent_auth        — Core authorization engine (identity, policy, context,
                        behavior, risk, trust, delegation, audit)
    behavior_analyzer — Standalone ML-based behavioral anomaly detection
                        with 6 concurrent detectors + async pipeline
"""

__all__ = ["agent_auth", "behavior_analyzer"]
