"""
finance_agent/tools.py
----------------------
Defines the ONE tool available to the Finance Agent: search_invoice.

The @tool decorator (from langchain_core.tools) converts the function into
a StructuredTool that LangGraph can:
  - Describe to the LLM (via its docstring and type annotations)
  - Call automatically when the LLM emits a tool_call AIMessage
  - Capture the return value as a ToolMessage for the LLM to read

Return format: a JSON string so the LLM receives structured data.
"""

import json
from langchain_core.tools import tool

from .mock_data import INVOICES


@tool
def search_invoice(invoice_id: str) -> str:
    """
    Search for a specific invoice by its unique invoice ID.

    Use this tool whenever the user asks about an invoice's status, amount,
    vendor, due date, or any other invoice detail.

    Args:
        invoice_id: The invoice identifier string, for example 'INV-001'.
                    Case-insensitive; leading/trailing whitespace is ignored.

    Returns:
        A JSON string. On success (found=true), contains the full invoice record.
        On failure (found=false), contains an error message and a list of
        available invoice IDs.
    """
    # Normalise the ID so 'inv-001', 'INV-001', ' INV-001 ' all work.
    normalised = invoice_id.strip().upper()

    invoice = INVOICES.get(normalised)

    if invoice is None:
        result = {
            "found": False,
            "invoice_id": normalised,
            "error": (
                f"No invoice found with ID '{normalised}'. "
                f"Known IDs: {', '.join(sorted(INVOICES.keys()))}"
            ),
        }
    else:
        result = {"found": True, **invoice}

    return json.dumps(result, default=str, indent=2)
