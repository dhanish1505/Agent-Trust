"""
run_data_agent.py
------------------
Demo runner for Module 2: Data Agent.

Runs preset queries that demonstrate both tools, then enters an
interactive REPL so you can type your own queries.

No API key required — uses MockDemoLLM by default.
To use a real LLM, set OPENAI_API_KEY and install langchain-openai:
    .venv\\Scripts\\pip install langchain-openai

Usage:
    .venv\\Scripts\\python run_data_agent.py
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
#  Preset demo queries                                                         #
# --------------------------------------------------------------------------- #

DEMO_QUERIES: list[tuple[str, str]] = [
    (
        "Summary search — active customer",
        "Find customer CUST-001.",
    ),
    (
        "Full profile — active customer",
        "Show me full details for CUST-007.",
    ),
    (
        "Status check — suspended account",
        "What is the status of CUST-006?",
    ),
    (
        "Full profile — inactive account",
        "Get all information for CUST-003.",
    ),
    (
        "Unknown customer ID",
        "Search for customer CUST-9999.",
    ),
]


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def sep(char: str = "-", width: int = 64) -> None:
    print(char * width)


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main() -> None:
    sep("=")
    print("  Data Agent — Module 2 Demo")
    sep("=")

    from data_agent import DataAgent

    print()
    agent = DataAgent()   # prints which LLM is selected

    # ------------------------------------------------------------------ #
    #  Preset demo queries                                                 #
    # ------------------------------------------------------------------ #
    print()
    sep("=")
    print("  DEMO QUERIES")
    sep("=")

    for label, query in DEMO_QUERIES:
        print(f"\n[{label}]")
        print(f"  User  : {query}")
        sep()
        response = agent.run(query)
        print(f"  Agent :\n{_indent(response)}")

    # ------------------------------------------------------------------ #
    #  Interactive mode                                                    #
    # ------------------------------------------------------------------ #
    print()
    sep("=")
    print("  INTERACTIVE MODE  (type 'quit' to exit)")
    print("  Hint: customers are CUST-001 through CUST-010")
    print("  Tip : use 'details' or 'full' to get the complete profile")
    sep("=")

    while True:
        print()
        try:
            user_input = input("You   : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if user_input.lower() in {"quit", "exit", "q", ""}:
            print("Goodbye!")
            break

        response = agent.run(user_input)
        print(f"Agent : {response}")


if __name__ == "__main__":
    main()
