# -*- coding: utf-8 -*-
"""
verify_langchain.py
-------------------
Quick smoke-test to confirm that LangChain and its core sub-packages
are installed and importable in this virtual environment.

Run:
    python verify_langchain.py
"""

import sys


def check_import(module: str) -> tuple[str, str]:
    """Try importing a module and return its version (or an error message)."""
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", "version unavailable")
        return ("[OK]    ", version)
    except ImportError as exc:
        return ("[FAIL]  ", str(exc))


def main() -> None:
    print("=" * 55)
    print("  LangChain Environment Verification")
    print("=" * 55)
    print(f"  Python  : {sys.version}")
    print(f"  Prefix  : {sys.prefix}")
    print("=" * 55)

    packages = [
        ("langchain",           "langchain"),
        ("langchain-core",      "langchain_core"),
        ("langchain-community", "langchain_community"),
    ]

    all_ok = True
    for display_name, import_name in packages:
        status, info = check_import(import_name)
        print(f"  {display_name:<25} {status}  {info}")
        if status.startswith("[FAIL]"):
            all_ok = False

    print("=" * 55)

    if all_ok:
        # Demonstrate a real LangChain object to prove everything works.
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate

        template = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant named {name}."),
                ("human", "{question}"),
            ]
        )

        messages = template.format_messages(
            name="AgentTrust",
            question="What is LangChain?",
        )

        print("\n  Demo: ChatPromptTemplate -> formatted messages")
        print("-" * 55)
        for msg in messages:
            label = type(msg).__name__
            print(f"  [{label}] {msg.content}")
        print("-" * 55)
        print("\n  [OK] All checks passed -- LangChain is ready!\n")
    else:
        print("\n  [FAIL] Some packages are missing. Re-run:\n")
        print("     .venv\\Scripts\\pip install langchain langchain-core langchain-community\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
