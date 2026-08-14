"""
tests/test_data_agent.py
-------------------------
Unit tests for Module 2: Data Agent.

Three test suites:
  TestCustomerMockData     — data integrity checks
  TestCustomerTools        — direct tool invocation (both tools, all edge cases)
  TestDataAgent            — end-to-end agent with MockDemoLLM

Run all Data Agent tests:
    .venv\\Scripts\\python -m pytest tests/test_data_agent.py -v

Run a specific suite:
    .venv\\Scripts\\python -m pytest tests/test_data_agent.py -v -k TestCustomerTools
"""

import json
import unittest

from data_agent.mock_data import CUSTOMERS, SEARCH_FIELDS
from data_agent.llm_provider import MockDemoLLM
from data_agent.tools import search_customer, get_customer_details


# =========================================================================== #
#  Suite 1: Mock data integrity
# =========================================================================== #

class TestCustomerMockData(unittest.TestCase):
    """Verify the mock customer data is complete and internally consistent."""

    BASE_REQUIRED = {"customer_id", "name", "email", "department", "account_status"}
    EXTENDED_REQUIRED = {"phone", "location", "joined_date", "subscription_tier",
                         "last_login", "notes"}
    ALL_REQUIRED = BASE_REQUIRED | EXTENDED_REQUIRED
    VALID_STATUSES = {"active", "inactive", "suspended"}
    VALID_TIERS = {"Free", "Pro", "Enterprise"}

    def test_customers_dict_is_not_empty(self):
        self.assertGreaterEqual(len(CUSTOMERS), 10)

    def test_all_base_fields_present(self):
        for cid, customer in CUSTOMERS.items():
            with self.subTest(customer_id=cid):
                missing = self.BASE_REQUIRED - set(customer.keys())
                self.assertEqual(missing, set(), f"Missing base fields in {cid}: {missing}")

    def test_all_extended_fields_present(self):
        for cid, customer in CUSTOMERS.items():
            with self.subTest(customer_id=cid):
                missing = self.EXTENDED_REQUIRED - set(customer.keys())
                self.assertEqual(missing, set(), f"Missing extended fields in {cid}: {missing}")

    def test_customer_id_matches_dict_key(self):
        for key, customer in CUSTOMERS.items():
            with self.subTest(key=key):
                self.assertEqual(key, customer["customer_id"])

    def test_all_statuses_are_valid(self):
        for cid, customer in CUSTOMERS.items():
            with self.subTest(customer_id=cid):
                self.assertIn(customer["account_status"], self.VALID_STATUSES)

    def test_all_tiers_are_valid(self):
        for cid, customer in CUSTOMERS.items():
            with self.subTest(customer_id=cid):
                self.assertIn(customer["subscription_tier"], self.VALID_TIERS)

    def test_at_least_one_of_each_status(self):
        statuses = {c["account_status"] for c in CUSTOMERS.values()}
        self.assertEqual(statuses, self.VALID_STATUSES)

    def test_search_fields_are_subset_of_all_fields(self):
        all_fields = set(next(iter(CUSTOMERS.values())).keys())
        self.assertTrue(SEARCH_FIELDS.issubset(all_fields))

    def test_emails_contain_at_sign(self):
        for cid, customer in CUSTOMERS.items():
            with self.subTest(customer_id=cid):
                self.assertIn("@", customer["email"])

    def test_customer_ids_follow_pattern(self):
        import re
        pattern = re.compile(r"^CUST-\d{3}$")
        for cid in CUSTOMERS:
            with self.subTest(customer_id=cid):
                self.assertRegex(cid, pattern)


# =========================================================================== #
#  Suite 2: Tool invocations
# =========================================================================== #

class TestSearchCustomerTool(unittest.TestCase):
    """Test search_customer directly (no LLM involved)."""

    def _invoke(self, customer_id: str) -> dict:
        raw = search_customer.invoke({"customer_id": customer_id})
        self.assertIsInstance(raw, str, "Tool must return a string")
        return json.loads(raw)

    # --- Happy path ---

    def test_known_customer_found(self):
        result = self._invoke("CUST-001")
        self.assertTrue(result["found"])

    def test_known_customer_has_correct_id(self):
        result = self._invoke("CUST-001")
        self.assertEqual(result["customer_id"], "CUST-001")

    def test_summary_has_only_base_fields(self):
        result = self._invoke("CUST-001")
        # search_customer must NOT expose extended fields
        self.assertNotIn("phone", result)
        self.assertNotIn("location", result)
        self.assertNotIn("notes", result)

    def test_summary_has_all_required_base_fields(self):
        result = self._invoke("CUST-001")
        for field in ("name", "email", "department", "account_status"):
            with self.subTest(field=field):
                self.assertIn(field, result)

    def test_every_known_customer_is_found(self):
        for cid in CUSTOMERS:
            with self.subTest(customer_id=cid):
                result = self._invoke(cid)
                self.assertTrue(result["found"])

    # --- Normalisation ---

    def test_lowercase_id_normalised(self):
        result = self._invoke("cust-001")
        self.assertTrue(result["found"])

    def test_mixed_case_id_normalised(self):
        result = self._invoke("Cust-001")
        self.assertTrue(result["found"])

    def test_whitespace_stripped(self):
        result = self._invoke("  CUST-001  ")
        self.assertTrue(result["found"])

    # --- Sad path ---

    def test_unknown_customer_not_found(self):
        result = self._invoke("CUST-9999")
        self.assertFalse(result["found"])

    def test_unknown_customer_has_error_key(self):
        result = self._invoke("CUST-9999")
        self.assertIn("error", result)

    def test_unknown_customer_error_mentions_id(self):
        result = self._invoke("CUST-9999")
        self.assertIn("CUST-9999", result["error"])

    def test_empty_string_not_found(self):
        result = self._invoke("")
        self.assertFalse(result["found"])

    # --- Metadata ---

    def test_tool_name_is_search_customer(self):
        self.assertEqual(search_customer.name, "search_customer")

    def test_tool_has_description(self):
        self.assertGreater(len(search_customer.description), 20)


class TestGetCustomerDetailsTool(unittest.TestCase):
    """Test get_customer_details directly (no LLM involved)."""

    def _invoke(self, customer_id: str) -> dict:
        raw = get_customer_details.invoke({"customer_id": customer_id})
        self.assertIsInstance(raw, str)
        return json.loads(raw)

    # --- Happy path ---

    def test_known_customer_found(self):
        result = self._invoke("CUST-001")
        self.assertTrue(result["found"])

    def test_full_profile_has_extended_fields(self):
        result = self._invoke("CUST-001")
        for field in ("phone", "location", "joined_date", "subscription_tier",
                      "last_login", "notes"):
            with self.subTest(field=field):
                self.assertIn(field, result)

    def test_full_profile_also_has_base_fields(self):
        result = self._invoke("CUST-001")
        for field in ("name", "email", "department", "account_status"):
            with self.subTest(field=field):
                self.assertIn(field, result)

    def test_full_profile_has_more_fields_than_summary(self):
        summary = json.loads(search_customer.invoke({"customer_id": "CUST-001"}))
        full = self._invoke("CUST-001")
        self.assertGreater(len(full), len(summary))

    def test_every_known_customer_returns_full_profile(self):
        for cid in CUSTOMERS:
            with self.subTest(customer_id=cid):
                result = self._invoke(cid)
                self.assertTrue(result["found"])

    # --- Normalisation (same as search_customer) ---

    def test_lowercase_id_normalised(self):
        result = self._invoke("cust-002")
        self.assertTrue(result["found"])

    def test_whitespace_stripped(self):
        result = self._invoke("  CUST-002  ")
        self.assertTrue(result["found"])

    # --- Sad path ---

    def test_unknown_customer_not_found(self):
        result = self._invoke("CUST-9999")
        self.assertFalse(result["found"])

    def test_unknown_customer_has_error(self):
        result = self._invoke("CUST-9999")
        self.assertIn("error", result)

    # --- Metadata ---

    def test_tool_name_is_get_customer_details(self):
        self.assertEqual(get_customer_details.name, "get_customer_details")

    def test_tool_has_description(self):
        self.assertGreater(len(get_customer_details.description), 20)


# =========================================================================== #
#  Suite 3: End-to-end DataAgent tests (MockDemoLLM)
# =========================================================================== #

class TestDataAgent(unittest.TestCase):
    """
    Full end-to-end tests through the LangGraph ReAct loop.
    No API key required — uses MockDemoLLM.
    """

    @classmethod
    def setUpClass(cls):
        from data_agent.agent import DataAgent
        cls.agent = DataAgent(llm=MockDemoLLM())

    # --- Return type ---

    def test_run_returns_string(self):
        result = self.agent.run("Find customer CUST-001.")
        self.assertIsInstance(result, str)

    # --- Summary query (search_customer path) ---

    def test_summary_query_is_non_empty(self):
        result = self.agent.run("Find customer CUST-001.")
        self.assertGreater(len(result.strip()), 10)

    def test_summary_response_contains_customer_id(self):
        result = self.agent.run("Find customer CUST-002.")
        self.assertIn("CUST-002", result)

    def test_summary_response_contains_name(self):
        result = self.agent.run("Search for CUST-001.")
        self.assertIn("Alice Chen", result)

    def test_summary_response_contains_status(self):
        result = self.agent.run("What is the status of CUST-006?")
        self.assertIn("SUSPENDED", result.upper())

    # --- Full-detail query (get_customer_details path) ---

    def test_detail_query_contains_phone(self):
        result = self.agent.run("Show me full details for CUST-001.")
        self.assertIn("+1-415-555-0101", result)

    def test_detail_query_contains_location(self):
        result = self.agent.run("Get all information for CUST-001.")
        self.assertIn("San Francisco", result)

    def test_detail_query_contains_subscription_tier(self):
        result = self.agent.run("Show complete profile for CUST-001.")
        self.assertIn("Enterprise", result)

    # --- Unknown customer ---

    def test_unknown_customer_graceful_response(self):
        result = self.agent.run("Find customer CUST-9999.")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 5)

    # --- Off-topic query ---

    def test_off_topic_query_graceful_response(self):
        result = self.agent.run("What is the stock price today?")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 5)

    # --- Input validation ---

    def test_raises_on_empty_query(self):
        with self.assertRaises(ValueError):
            self.agent.run("")

    def test_raises_on_whitespace_query(self):
        with self.assertRaises(ValueError):
            self.agent.run("   ")

    def test_raises_on_non_string(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            self.agent.run(None)  # type: ignore[arg-type]

    # --- Inactive / suspended customers ---

    def test_inactive_customer_found(self):
        # CUST-003 is inactive
        result = self.agent.run("Find customer CUST-003.")
        self.assertIn("CUST-003", result)

    def test_suspended_customer_shows_status(self):
        result = self.agent.run("What is the status of CUST-006?")
        self.assertIn("SUSPENDED", result.upper())


if __name__ == "__main__":
    unittest.main(verbosity=2)
