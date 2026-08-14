# AGENT TRUST — LangChain Agent Research Project

A modular Python + LangChain project.  
Each module is a self-contained agent with its own tools and mock data.

---

## Project Structure

```
AGENT TRUST/
├── .venv/                        ← shared virtual environment (not committed)
│
├── finance_agent/                ← MODULE 1: Finance Agent
│   ├── __init__.py
│   ├── agent.py                  ← FinanceAgent class (public API)
│   ├── tools.py                  ← search_invoice tool
│   ├── mock_data.py              ← 10 mock invoices
│   └── llm_provider.py           ← MockDemoLLM + get_llm() factory
│
├── data_agent/                   ← MODULE 2: Data Agent
│   ├── __init__.py
│   ├── agent.py                  ← DataAgent class (public API)
│   ├── tools.py                  ← search_customer + get_customer_details tools
│   ├── mock_data.py              ← 10 mock customers
│   └── llm_provider.py           ← MockDemoLLM + get_llm() factory
│
├── tests/
│   ├── __init__.py
│   ├── test_finance_agent.py     ← Module 1 tests  (31 tests)
│   └── test_data_agent.py        ← Module 2 tests  (50 tests)
│
├── run_finance_agent.py          ← Module 1 demo runner
├── run_data_agent.py             ← Module 2 demo runner
├── verify_langchain.py           ← Environment smoke-test
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Setup

```bash
# 1. Create and activate the virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install all dependencies
pip install -r requirements.txt
```

---

## Verify the environment

```bash
python verify_langchain.py
```

---

## Run a module

```bash
# Module 1 — Finance Agent
python run_finance_agent.py

# Module 2 — Data Agent
python run_data_agent.py
```

---

## Run tests

```bash
# All tests (both modules)
python -m pytest tests/ -v

# Module 1 only
python -m pytest tests/test_finance_agent.py -v

# Module 2 only
python -m pytest tests/test_data_agent.py -v
```

---

## Modules

### Module 1 — Finance Agent (`finance_agent/`)
| | |
|---|---|
| **Tool** | `search_invoice(invoice_id)` |
| **Data** | 10 mock invoices — paid / pending / overdue |
| **Input** | `"What is the status of invoice INV-003?"` |
| **Output** | Formatted invoice details (vendor, amount, status, due date) |

### Module 2 — Data Agent (`data_agent/`)
| | |
|---|---|
| **Tools** | `search_customer(customer_id)` · `get_customer_details(customer_id)` |
| **Data** | 10 mock customers — active / inactive / suspended |
| **Input** | `"Find customer CUST-007."` or `"Show full details for CUST-001."` |
| **Output** | Customer summary or full profile |

---

## LLM Configuration

No API key is required.  
Both modules use `MockDemoLLM` by default — a deterministic mock that drives the
full LangGraph ReAct loop without any external calls.

To use a real LLM:
```bash
pip install langchain-openai
# Set OPENAI_API_KEY in your environment
```

---

## Next Modules (planned)

- **Module 3** — …
- **Module 4** — …
