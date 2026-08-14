"""
data_agent/mock_data.py
-----------------------
In-memory mock customer database.

This is the ONLY data source for Module 2.
No database, no network calls, no external files.

Each customer record contains two tiers of data:

  BASE FIELDS (returned by search_customer):
    customer_id    : Unique identifier (str, format CUST-NNN)
    name           : Full name (str)
    email          : Primary email address (str)
    department     : Organisational department (str)
    account_status : "active" | "inactive" | "suspended"

  EXTENDED FIELDS (returned by get_customer_details, in addition to base):
    phone          : Contact phone number (str)
    location       : City, Country (str)
    joined_date    : ISO 8601 date (str)
    subscription_tier : "Free" | "Pro" | "Enterprise" (str)
    last_login     : ISO 8601 date (str)
    notes          : Free-text notes on the account (str)
"""

CUSTOMERS: dict[str, dict] = {
    "CUST-001": {
        # --- Base fields ---
        "customer_id": "CUST-001",
        "name": "Alice Chen",
        "email": "alice.chen@techcorp.com",
        "department": "Engineering",
        "account_status": "active",
        # --- Extended fields ---
        "phone": "+1-415-555-0101",
        "location": "San Francisco, CA, USA",
        "joined_date": "2023-03-15",
        "subscription_tier": "Enterprise",
        "last_login": "2026-08-13",
        "notes": "Lead engineer for API integration project. Escalation contact.",
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Benjamin Okafor",
        "email": "b.okafor@dataflow.io",
        "department": "Data Science",
        "account_status": "active",
        "phone": "+44-20-7946-0202",
        "location": "London, UK",
        "joined_date": "2022-11-01",
        "subscription_tier": "Pro",
        "last_login": "2026-08-12",
        "notes": "Uses platform primarily for ETL pipeline management.",
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Clara Müller",
        "email": "c.muller@autoindustry.de",
        "department": "Operations",
        "account_status": "inactive",
        "phone": "+49-89-555-0303",
        "location": "Munich, Germany",
        "joined_date": "2021-06-20",
        "subscription_tier": "Pro",
        "last_login": "2026-05-30",
        "notes": "Account inactive since Q2 renewal was not completed.",
    },
    "CUST-004": {
        "customer_id": "CUST-004",
        "name": "David Nakamura",
        "email": "d.nakamura@finserv.jp",
        "department": "Finance",
        "account_status": "active",
        "phone": "+81-3-5555-0404",
        "location": "Tokyo, Japan",
        "joined_date": "2024-01-10",
        "subscription_tier": "Enterprise",
        "last_login": "2026-08-14",
        "notes": "New enterprise client. Onboarding in progress.",
    },
    "CUST-005": {
        "customer_id": "CUST-005",
        "name": "Evelyn Santos",
        "email": "evelyn.s@healthplus.br",
        "department": "Research & Development",
        "account_status": "active",
        "phone": "+55-11-9555-0505",
        "location": "São Paulo, Brazil",
        "joined_date": "2023-07-22",
        "subscription_tier": "Pro",
        "last_login": "2026-08-10",
        "notes": "R&D team uses the platform for clinical trial data analysis.",
    },
    "CUST-006": {
        "customer_id": "CUST-006",
        "name": "Farhan Malik",
        "email": "farhan.malik@cloudstartup.pk",
        "department": "Product",
        "account_status": "suspended",
        "phone": "+92-21-555-0606",
        "location": "Karachi, Pakistan",
        "joined_date": "2022-04-05",
        "subscription_tier": "Free",
        "last_login": "2026-06-01",
        "notes": "Account suspended due to payment failure on 2026-06-15.",
    },
    "CUST-007": {
        "customer_id": "CUST-007",
        "name": "Grace Kim",
        "email": "grace.kim@mediahub.kr",
        "department": "Marketing",
        "account_status": "active",
        "phone": "+82-2-555-0707",
        "location": "Seoul, South Korea",
        "joined_date": "2023-09-30",
        "subscription_tier": "Pro",
        "last_login": "2026-08-11",
        "notes": "Uses platform for campaign analytics dashboards.",
    },
    "CUST-008": {
        "customer_id": "CUST-008",
        "name": "Henry Dubois",
        "email": "h.dubois@logisticseu.fr",
        "department": "Supply Chain",
        "account_status": "active",
        "phone": "+33-1-5555-0808",
        "location": "Paris, France",
        "joined_date": "2024-03-18",
        "subscription_tier": "Enterprise",
        "last_login": "2026-08-09",
        "notes": "Integration with ERP system completed in Q1 2026.",
    },
    "CUST-009": {
        "customer_id": "CUST-009",
        "name": "Isabela Ferreira",
        "email": "i.ferreira@edtech.com",
        "department": "Customer Success",
        "account_status": "inactive",
        "phone": "+1-305-555-0909",
        "location": "Miami, FL, USA",
        "joined_date": "2022-08-14",
        "subscription_tier": "Free",
        "last_login": "2026-03-22",
        "notes": "Trial account expired. Follow-up email sent on 2026-04-01.",
    },
    "CUST-010": {
        "customer_id": "CUST-010",
        "name": "James Patel",
        "email": "james.patel@retailchain.in",
        "department": "IT",
        "account_status": "active",
        "phone": "+91-22-5555-1010",
        "location": "Mumbai, India",
        "joined_date": "2025-02-01",
        "subscription_tier": "Enterprise",
        "last_login": "2026-08-14",
        "notes": "High-volume account. Manages 50+ sub-users under the org license.",
    },
}

# Fields exposed by search_customer (summary view)
SEARCH_FIELDS = {"customer_id", "name", "email", "department", "account_status"}

# All fields exposed by get_customer_details (full view)
DETAIL_FIELDS = set(next(iter(CUSTOMERS.values())).keys())
