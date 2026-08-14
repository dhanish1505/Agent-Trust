"""
finance_agent/__init__.py
--------------------------
Public API for the finance_agent package.

Usage:
    from finance_agent import FinanceAgent

    agent = FinanceAgent()
    response = agent.run("What is the status of invoice INV-002?")
    print(response)
"""

from .agent import FinanceAgent

__all__ = ["FinanceAgent"]
