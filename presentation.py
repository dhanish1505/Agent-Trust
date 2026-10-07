import os
import sys
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Ensure agenttrust modules can be found
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agenttrust"))
load_dotenv()

from agenttrust.behavior_analyzer import BehaviorAnalyzer, AgentEvent, ToolCall, DelegationInfo, AgentRole
from supervisor_agent import SupervisorAgent
from agenttrust.gateway import auth_engine

def print_separator(title: str):
    print(f"\n{'='*75}")
    print(f" {title}")
    print(f"{'='*75}\n")

async def train_ml_models():
    print_separator("PART 1: Machine Learning & Trust Engine Training")
    
    print("[*] Initializing Behavior Analyzer (In-Memory Store)...")
    analyzer = BehaviorAnalyzer()
    
    print("[*] Loading dataset from agent_behavior_dataset.json...")
    try:
        with open("agent_behavior_dataset.json", "r") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Dataset not found. Please run generate_dataset.py first.")
        return
        
    print(f"    Loaded {len(dataset)} enterprise agent events.")
    
    print("\n[*] Training Statistical Baselines and Isolation Forest Model...")
    print("    Streaming events through the pipeline (this takes a few seconds)...")
    
    total = len(dataset)
    for i, row in enumerate(dataset):
        params = {}
        for j in range(row["param_count"]):
            params[f"param_{j}"] = "x"
        current_size = sum(len(str(v)) for v in params.values())
        target_size = row["param_size_bytes"]
        if target_size > current_size:
            params["param_0"] = "x" * (target_size - current_size + 1)
            
        event = AgentEvent(
            agent_id=row["agent_id"],
            agent_role=AgentRole(row["agent_role"]) if row["agent_role"] in [r.value for r in AgentRole] else AgentRole.UNKNOWN,
            tool_call=ToolCall(
                tool_name=row["tool_name"],
                parameters=params,
            ),
            sensitivity_score=row["sensitivity_score"],
            timestamp=datetime.fromisoformat(row["timestamp"])
        )
        if row["is_delegated"]:
            event = AgentEvent(
                agent_id=event.agent_id,
                agent_role=event.agent_role,
                tool_call=event.tool_call,
                sensitivity_score=event.sensitivity_score,
                timestamp=event.timestamp,
                delegation=DelegationInfo(
                    delegated_by="parent", chain_depth=row["delegation_depth"], delegation_token="tok"
                )
            )
            
        await analyzer.analyze(event)
        
        if i % 2500 == 0 and i > 0:
            print(f"    Processed {i}/{total} events...")
            
    print("\n✅ Training Complete. Baselines established. Isolation Forest model fitted.")

def run_live_orchestration():
    print_separator("PART 2: Live Multi-Agent Orchestration & Security Enforcement")
    
    print("[*] Initializing Supervisor Agent and Child Agents (Finance, Data)...")
    supervisor = SupervisorAgent()
    
    print("\n" + "-"*75)
    print("Test A: Normal Authorized Delegation (Combined Request)")
    print("-" * 75)
    
    query = "Find customer CUST-002 and then get the details of invoice INV-003."
    print(f"\nUser Query: {query}\n")
    
    response = supervisor.run(query)
    print("\n--- Final Agent Response ---")
    print(response)

    print("\n" + "-"*75)
    print("Test B: ML Engine Detects Threat & Gateway Quarantines Agent")
    print("-" * 75)
    
    print("\n[!] The Data Agent is compromised and attempts to mass-exfiltrate data.")
    print("    The Machine Learning engine catches the anomaly and drops the Trust Score...")
    
    trust = auth_engine._store.trust.get("data-agent")
    trust.adjust(-90.0, "Caught EXFILTRATION pattern by ML Behavior Analyzer.")
    auth_engine._store.trust.save(trust)
    
    print("    -> Data Agent Trust Score is now: 10.0 (Quarantined)")
    
    print("\n[!] The Supervisor Agent unknowingly delegates another task to the compromised Data Agent.")
    
    query2 = "Who is customer CUST-001?"
    print(f"\nUser Query: {query2}\n")
    
    response2 = supervisor.run(query2)
    print("\n--- Final Agent Response ---")
    print(response2)
    
    print_separator("Demo Complete. Thank you!")

async def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
            
    await train_ml_models()
    run_live_orchestration()

if __name__ == "__main__":
    asyncio.run(main())
