"""
data_agent/__init__.py
-----------------------
Public API for the data_agent package.

Usage:
    from data_agent import DataAgent

    agent = DataAgent()

    # Quick summary lookup
    print(agent.run("Find customer CUST-001."))

    # Full profile lookup
    print(agent.run("Show me full details for CUST-007."))
"""

from .agent import DataAgent

__all__ = ["DataAgent"]
