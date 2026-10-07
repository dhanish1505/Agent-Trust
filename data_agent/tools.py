"""
data_agent/tools.py
--------------------
Defines the TWO tools available to the Data Agent.

Tool 1 — search_customer(customer_id)
    Returns a SUMMARY view: customer_id, name, email, department, account_status.
    Use this to quickly confirm a customer exists and see their key status.

Tool 2 — get_customer_details(customer_id)
    Returns the FULL profile including phone, location, subscription tier,
    join date, last login, and notes.
    Use this when the user needs complete information about a customer.

Both tools:
  • Normalise the customer_id (strip whitespace, uppercase).
  • Return a JSON string — structured data is unambiguous for the LLM.
  • Return found=False with an error message when the ID is not recognised.
"""

import json
from langchain_core.tools import tool
from agenttrust.gateway import secure_tool
from agenttrust.agent_auth.models import ActionCategory, ResourceType

from .mock_data import CUSTOMERS, SEARCH_FIELDS


# --------------------------------------------------------------------------- #
#  Tool 1: search_customer
# --------------------------------------------------------------------------- #

@tool
@secure_tool(ActionCategory.READ, ResourceType.DATABASE, "customer_id")
def search_customer(customer_id: str) -> str:
    """
    Search for a customer by their unique customer ID and return a summary.

    Returns: customer ID, name, email, department, and account status.
    Use this tool for a quick lookup or to verify a customer exists.

    Args:
        customer_id: The customer identifier string, e.g. 'CUST-001'.
                     Case-insensitive; leading/trailing whitespace is ignored.

    Returns:
        A JSON string with found=true and summary fields on success, or
        found=false with an error message if the customer is not recognised.
    """
    normalised = customer_id.strip().upper()
    customer = CUSTOMERS.get(normalised)

    if customer is None:
        result = {
            "found": False,
            "customer_id": normalised,
            "error": (
                f"No customer found with ID '{normalised}'. "
                f"Known IDs: {', '.join(sorted(CUSTOMERS.keys()))}"
            ),
        }
    else:
        result = {
            "found": True,
            **{k: v for k, v in customer.items() if k in SEARCH_FIELDS},
        }

    return json.dumps(result, indent=2)


# --------------------------------------------------------------------------- #
#  Tool 2: get_customer_details
# --------------------------------------------------------------------------- #

@tool
@secure_tool(ActionCategory.READ, ResourceType.DATABASE, "customer_id")
def get_customer_details(customer_id: str) -> str:
    """
    Retrieve the full profile for a customer by their unique customer ID.

    Returns all available information: ID, name, email, department,
    account status, phone, location, subscription tier, join date,
    last login, and account notes.

    Use this tool when the user wants complete or detailed information
    about a specific customer.

    Args:
        customer_id: The customer identifier string, e.g. 'CUST-001'.
                     Case-insensitive; leading/trailing whitespace is ignored.

    Returns:
        A JSON string with found=true and the full customer profile on success,
        or found=false with an error message if the customer is not recognised.
    """
    normalised = customer_id.strip().upper()
    customer = CUSTOMERS.get(normalised)

    if customer is None:
        result = {
            "found": False,
            "customer_id": normalised,
            "error": (
                f"No customer found with ID '{normalised}'. "
                f"Known IDs: {', '.join(sorted(CUSTOMERS.keys()))}"
            ),
        }
    else:
        result = {"found": True, **customer}

    return json.dumps(result, indent=2)
