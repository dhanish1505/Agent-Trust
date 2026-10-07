import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agenttrust"))
load_dotenv()

from supervisor_agent import SupervisorAgent
from agenttrust.gateway import auth_engine

def print_separator(title: str):
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")

def run_demo():
    print_separator("AgentTrust - Module 3 & Gateway Complete Orchestration Demo")
    
    print("[*] Initializing Supervisor Agent and Child Agents (Finance, Data)...")
    supervisor = SupervisorAgent()
    
    print("\n" + "="*70)
    print("  INTERACTIVE MODE  (type 'quit' to exit)")
    print("  Hint: You can ask the Supervisor to fetch customers and invoices.")
    print("  Demo Tip: Try asking it to 'hack', 'steal', 'bypass', or 'delete' to trigger the automatic security quarantine!")
    print("="*70)

    # Keywords that trigger Data Agent quarantine (PII, sensitive details, destructive actions)
    data_threat_keywords = [
        "hack", "steal", "bypass", "delete", "drop", "exfiltrate", "override",
        "password", "sensitive", "ssn", "credentials", "secret", "token", "personal details"
    ]
    
    # Keywords that trigger Finance Agent quarantine (Financial manipulation, unauthorized access)
    finance_threat_keywords = [
        "credit card", "fraud", "embezzle", "unauthorized payment", "wire transfer",
        "bank account"
    ]

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
            
        if user_input.lower() == "!restore":
            for agent_name in ["data-agent", "finance-agent"]:
                trust = auth_engine._store.trust.get(agent_name)
                trust.adjust(90.0, "Admin manual restore.")
                auth_engine._store.trust.save(trust)
            print("[*] All agents' trust scores have been restored! They can read the DB again.")
            continue

        lower_input = user_input.lower()
        
        # 1. Check for Data Agent Threats
        if any(word in lower_input for word in data_threat_keywords):
            print("\n🚨 [THREAT MONITOR] Malicious intent targeting PII/Data detected!")
            print("🚨 [THREAT MONITOR] Slashing Data Agent trust score to prevent potential breach...")
            trust = auth_engine._store.trust.get("data-agent")
            trust.adjust(-90.0, f"Detected malicious prompt injection attempts: {user_input}")
            auth_engine._store.trust.save(trust)
            print("🚨 [THREAT MONITOR] Quarantine active. Gateway will now block the Data Agent.")

        # 2. Check for Finance Agent Threats
        if any(word in lower_input for word in finance_threat_keywords):
            print("\n🚨 [THREAT MONITOR] Malicious intent targeting Financial systems detected!")
            print("🚨 [THREAT MONITOR] Slashing Finance Agent trust score to prevent financial fraud...")
            trust = auth_engine._store.trust.get("finance-agent")
            trust.adjust(-90.0, f"Detected financial manipulation attempts: {user_input}")
            auth_engine._store.trust.save(trust)
            print("🚨 [THREAT MONITOR] Quarantine active. Gateway will now block the Finance Agent.")

        response = supervisor.run(user_input)
        print("\n--- Final Agent Response ---")
        print(response)

if __name__ == "__main__":
    run_demo()
