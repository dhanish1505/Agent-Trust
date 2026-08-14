"""
finance_agent/mock_data.py
--------------------------
In-memory mock invoice database.

This is the ONLY data source for Module 1.
No database, no network calls, no external files.

Each invoice record contains:
    invoice_id  : Unique identifier (str, format INV-NNN)
    vendor      : Vendor / supplier name (str)
    amount      : Invoice total (float)
    currency    : ISO currency code (str)
    status      : "paid" | "pending" | "overdue"
    due_date    : ISO 8601 date string (str)
    paid_date   : ISO 8601 date string or None
    description : Short description of goods/services (str)
    contact     : Vendor billing email (str)
"""

INVOICES: dict[str, dict] = {
    "INV-001": {
        "invoice_id": "INV-001",
        "vendor": "Acme Corp",
        "amount": 12500.00,
        "currency": "USD",
        "status": "paid",
        "due_date": "2026-07-15",
        "paid_date": "2026-07-10",
        "description": "Software licenses Q3 2026",
        "contact": "billing@acmecorp.com",
    },
    "INV-002": {
        "invoice_id": "INV-002",
        "vendor": "TechSupply Ltd",
        "amount": 4875.50,
        "currency": "USD",
        "status": "pending",
        "due_date": "2026-08-30",
        "paid_date": None,
        "description": "Hardware components batch #7",
        "contact": "accounts@techsupply.com",
    },
    "INV-003": {
        "invoice_id": "INV-003",
        "vendor": "CloudBase Inc",
        "amount": 2200.00,
        "currency": "USD",
        "status": "overdue",
        "due_date": "2026-07-01",
        "paid_date": None,
        "description": "Cloud hosting services June 2026",
        "contact": "billing@cloudbase.io",
    },
    "INV-004": {
        "invoice_id": "INV-004",
        "vendor": "DataStream Analytics",
        "amount": 8900.00,
        "currency": "EUR",
        "status": "paid",
        "due_date": "2026-06-20",
        "paid_date": "2026-06-18",
        "description": "Data pipeline consulting — May 2026",
        "contact": "invoices@datastream.eu",
    },
    "INV-005": {
        "invoice_id": "INV-005",
        "vendor": "Office Essentials Co",
        "amount": 635.75,
        "currency": "USD",
        "status": "pending",
        "due_date": "2026-09-05",
        "paid_date": None,
        "description": "Office supplies and ergonomic equipment",
        "contact": "ar@officeessentials.com",
    },
    "INV-006": {
        "invoice_id": "INV-006",
        "vendor": "SecureNet Solutions",
        "amount": 15000.00,
        "currency": "USD",
        "status": "overdue",
        "due_date": "2026-06-30",
        "paid_date": None,
        "description": "Annual cybersecurity audit and penetration testing",
        "contact": "finance@securenet.com",
    },
    "INV-007": {
        "invoice_id": "INV-007",
        "vendor": "Bright Marketing Agency",
        "amount": 3200.00,
        "currency": "GBP",
        "status": "paid",
        "due_date": "2026-07-31",
        "paid_date": "2026-07-28",
        "description": "Q2 2026 digital marketing campaign",
        "contact": "billing@brightmarketing.co.uk",
    },
    "INV-008": {
        "invoice_id": "INV-008",
        "vendor": "Precision Logistics",
        "amount": 1120.00,
        "currency": "USD",
        "status": "pending",
        "due_date": "2026-08-22",
        "paid_date": None,
        "description": "Freight and delivery services July 2026",
        "contact": "billing@precisionlogistics.com",
    },
    "INV-009": {
        "invoice_id": "INV-009",
        "vendor": "LegalEagle LLP",
        "amount": 7500.00,
        "currency": "USD",
        "status": "paid",
        "due_date": "2026-05-15",
        "paid_date": "2026-05-14",
        "description": "Legal counsel — contract review and IP filings",
        "contact": "accounts@legaleagle.com",
    },
    "INV-010": {
        "invoice_id": "INV-010",
        "vendor": "GreenEnergy Partners",
        "amount": 22400.00,
        "currency": "USD",
        "status": "overdue",
        "due_date": "2026-07-10",
        "paid_date": None,
        "description": "Solar panel installation Phase 1",
        "contact": "finance@greenenergy.partners",
    },
}
