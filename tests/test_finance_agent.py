"""
tests/test_finance_agent.py
----------------------------
Unit tests for Module 1: Finance Agent.

Three test suites, each independently runnable:
  TestMockData          — data integrity
  TestSearchInvoiceTool — tool function behaviour
  TestFinanceAgent      — end-to-end agent with MockDemoLLM

Run all tests:
    .venv\\Scripts\\python -m pytest tests/ -v

Run a specific suite:
    .venv\\Scripts\\python -m pytest tests/ -v -k TestSearchInvoiceTool
"""

import json
import unittest

from finance_agent.mock_data import INVOICES
from finance_agent.llm_provider import MockDemoLLM
from finance_agent.tools import search_invoice


# =========================================================================== #
#  Suite 1: Mock data integrity
# =========================================================================== #

class TestMockData(unittest.TestCase):
    """Verify that the mock invoice data is complete and consistent."""

    REQUIRED_FIELDS = {
        "invoice_id", "vendor", "amount", "currency",
        "status", "due_date", "paid_date", "description", "contact",
    }
    VALID_STATUSES = {"paid", "pending", "overdue"}

    def test_invoices_dict_is_not_empty(self):
        self.assertGreater(len(INVOICES), 0, "INVOICES must have at least one entry")

    def test_all_required_fields_present(self):
        for iid, inv in INVOICES.items():
            with self.subTest(invoice_id=iid):
                missing = self.REQUIRED_FIELDS - set(inv.keys())
                self.assertEqual(missing, set(), f"Missing fields in {iid}: {missing}")

    def test_invoice_id_matches_dict_key(self):
        for key, inv in INVOICES.items():
            with self.subTest(key=key):
                self.assertEqual(
                    key, inv["invoice_id"],
                    f"Key '{key}' does not match invoice_id '{inv['invoice_id']}'"
                )

    def test_all_statuses_are_valid(self):
        for iid, inv in INVOICES.items():
            with self.subTest(invoice_id=iid):
                self.assertIn(
                    inv["status"], self.VALID_STATUSES,
                    f"'{iid}' has invalid status '{inv['status']}'"
                )

    def test_paid_invoices_have_paid_date(self):
        for iid, inv in INVOICES.items():
            with self.subTest(invoice_id=iid):
                if inv["status"] == "paid":
                    self.assertIsNotNone(
                        inv["paid_date"],
                        f"Paid invoice '{iid}' must have a paid_date"
                    )

    def test_unpaid_invoices_have_no_paid_date(self):
        for iid, inv in INVOICES.items():
            with self.subTest(invoice_id=iid):
                if inv["status"] in {"pending", "overdue"}:
                    self.assertIsNone(
                        inv["paid_date"],
                        f"Unpaid invoice '{iid}' should not have a paid_date"
                    )

    def test_amount_is_positive(self):
        for iid, inv in INVOICES.items():
            with self.subTest(invoice_id=iid):
                self.assertGreater(inv["amount"], 0)

    def test_at_least_one_of_each_status(self):
        statuses = {inv["status"] for inv in INVOICES.values()}
        self.assertEqual(
            statuses, self.VALID_STATUSES,
            f"Expected all three statuses; found: {statuses}"
        )


# =========================================================================== #
#  Suite 2: search_invoice tool
# =========================================================================== #

class TestSearchInvoiceTool(unittest.TestCase):
    """Test search_invoice directly, bypassing the LLM entirely."""

    def _invoke(self, invoice_id: str) -> dict:
        """Call the tool via LangChain's .invoke() and parse the JSON response."""
        raw = search_invoice.invoke({"invoice_id": invoice_id})
        self.assertIsInstance(raw, str, "Tool must return a string")
        return json.loads(raw)

    # --- Happy path ---

    def test_known_invoice_returns_found_true(self):
        first_id = next(iter(INVOICES))
        result = self._invoke(first_id)
        self.assertTrue(result["found"])

    def test_known_invoice_has_correct_id(self):
        result = self._invoke("INV-001")
        self.assertEqual(result["invoice_id"], "INV-001")

    def test_known_invoice_has_all_fields(self):
        result = self._invoke("INV-001")
        for field in ("vendor", "amount", "currency", "status", "due_date", "description"):
            with self.subTest(field=field):
                self.assertIn(field, result)

    def test_every_known_invoice_is_found(self):
        """Every ID in INVOICES must be retrievable."""
        for iid in INVOICES:
            with self.subTest(invoice_id=iid):
                result = self._invoke(iid)
                self.assertTrue(result["found"], f"Expected {iid} to be found")

    # --- Case / whitespace normalisation ---

    def test_lowercase_id_is_normalised(self):
        result = self._invoke("inv-001")
        self.assertTrue(result["found"])

    def test_mixed_case_id_is_normalised(self):
        result = self._invoke("Inv-001")
        self.assertTrue(result["found"])

    def test_whitespace_is_stripped(self):
        result = self._invoke("  INV-001  ")
        self.assertTrue(result["found"])

    # --- Sad path ---

    def test_unknown_invoice_returns_found_false(self):
        result = self._invoke("INV-9999")
        self.assertFalse(result["found"])

    def test_unknown_invoice_has_error_key(self):
        result = self._invoke("INV-9999")
        self.assertIn("error", result)

    def test_unknown_invoice_error_mentions_id(self):
        result = self._invoke("INV-9999")
        self.assertIn("INV-9999", result["error"])

    def test_empty_string_returns_not_found(self):
        result = self._invoke("")
        self.assertFalse(result["found"])

    # --- Tool metadata ---

    def test_tool_has_a_name(self):
        self.assertEqual(search_invoice.name, "search_invoice")

    def test_tool_has_a_description(self):
        self.assertGreater(len(search_invoice.description), 20)


# =========================================================================== #
#  Suite 3: FinanceAgent end-to-end (MockDemoLLM)
# =========================================================================== #

class TestFinanceAgent(unittest.TestCase):
    """
    End-to-end tests that run the full LangGraph ReAct loop using MockDemoLLM.
    No API key required.
    """

    @classmethod
    def setUpClass(cls):
        """Create one agent instance shared across all tests in this suite."""
        from finance_agent.agent import FinanceAgent
        cls.agent = FinanceAgent(llm=MockDemoLLM())

    def test_run_returns_string(self):
        result = self.agent.run("Show me invoice INV-001.")
        self.assertIsInstance(result, str)

    def test_known_invoice_response_is_non_empty(self):
        result = self.agent.run("What is the status of invoice INV-001?")
        self.assertGreater(len(result.strip()), 10)

    def test_known_invoice_response_contains_id(self):
        result = self.agent.run("Tell me about invoice INV-002.")
        self.assertIn("INV-002", result)

    def test_known_invoice_response_contains_vendor(self):
        result = self.agent.run("What is invoice INV-001?")
        # INV-001 vendor is "Acme Corp"
        self.assertIn("Acme Corp", result)

    def test_unknown_invoice_graceful_response(self):
        result = self.agent.run("Look up invoice INV-9999.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 5)

    def test_off_topic_query_graceful_response(self):
        result = self.agent.run("What is the weather today?")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 5)

    def test_raises_on_empty_query(self):
        with self.assertRaises(ValueError):
            self.agent.run("")

    def test_raises_on_whitespace_query(self):
        with self.assertRaises(ValueError):
            self.agent.run("   ")

    def test_overdue_invoice_response_contains_status(self):
        result = self.agent.run("Is invoice INV-003 overdue?")
        self.assertIn("OVERDUE", result.upper())

    def test_paid_invoice_response_contains_paid_date(self):
        result = self.agent.run("When was invoice INV-001 paid?")
        # INV-001 paid_date is "2026-07-10"
        self.assertIn("2026-07-10", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
