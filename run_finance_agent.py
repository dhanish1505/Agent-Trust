"""
run_finance_agent.py
---------------------
Demo runner for Module 1: Finance Agent.

Runs three preset queries that show the full tool-call cycle, then
enters an interactive loop so you can type your own queries.

No API key is required — the agent uses MockDemoLLM by default.
To use a real LLM set OPENAI_API_KEY in your environment and install
langchain-openai:
    .venv\\Scripts\\pip install langchain-openai

Usage:
    .venv\\Scripts\\python run_finance_agent.py
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
#  Demo queries                                                                #
# --------------------------------------------------------------------------- #

DEMO_QUERIES: list[tuple[str, str]] = [
    (
        "Known invoice (paid)",
        "What is the status of invoice INV-001?",
    ),
    (
        "Known invoice (overdue)",
        "Can you show me the details for invoice INV-003?",
    ),
    (
        "Unknown invoice",
        "Please look up invoice INV-9999.",
    ),
]


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def sep(char: str = "-", width: int = 62) -> None:
    print(char * width)


def header(title: str) -> None:
    sep("=")
    print(f"  {title}")
    sep("=")


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main() -> None:
    header("Finance Agent — Module 1 Demo")

    from finance_agent import FinanceAgent

    print()
    # FinanceAgent() calls get_llm() internally; it prints which LLM is used.
    agent = FinanceAgent()

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
    print("  Hint: ask about invoices INV-001 through INV-010")
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


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    main()
