import asyncio
import json
import sys
import os
from datetime import datetime

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agenttrust.behavior_analyzer import (
    BehaviorAnalyzer, AgentEvent, ToolCall, DelegationInfo, AgentRole
)

async def train_and_evaluate():
    print("\n" + "="*60)
    print(" AgentTrust ML Behavior Analyzer - Training & Demo")
    print("="*60)
    
    # 1. Initialize Analyzer
    print("\n[1] Initializing Behavior Analyzer (In-Memory Store)...")
    analyzer = BehaviorAnalyzer()
    
    # 2. Load Dataset
    print("\n[2] Loading dataset from agent_behavior_dataset.json...")
    try:
        with open("agent_behavior_dataset.json", "r") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Dataset not found. Please run generate_dataset.py first.")
        return
        
    print(f"Loaded {len(dataset)} events.")
    
    # 3. Train Baseline (Simulated streaming)
    print("\n[3] Training Statistical Baselines and Isolation Forest Model...")
    print("Streaming events through the pipeline (this may take a few seconds)...")
    
    # Process in batches to simulate realistic throughput
    total = len(dataset)
    for i, row in enumerate(dataset):
        # Create dummy parameters to match count and size
        params = {}
        for j in range(row["param_count"]):
            params[f"param_{j}"] = "x"
        
        # Adjust the last parameter's size to hit the target total size
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
                agent_id=row["agent_id"],
                agent_role=AgentRole(row["agent_role"]) if row["agent_role"] in [r.value for r in AgentRole] else AgentRole.UNKNOWN,
                tool_call=event.tool_call,
                sensitivity_score=row["sensitivity_score"],
                timestamp=event.timestamp,
                delegation=DelegationInfo(
                    delegated_by="parent", 
                    chain_depth=row["delegation_depth"], 
                    delegation_token="tok"
                )
            )
            
        # We don't await every single one sequentially in prod, but for training script it's fine
        report = await analyzer.analyze(event)
        
        if i % 2500 == 0 and i > 0:
            print(f"  Processed {i}/{total} events...")
            
    print("✅ Training Complete. Baselines established. Isolation Forest model fitted.")
    
    # 4. Run Live Demos (Testing the trained model)
    print("\n[4] Live Threat Detection Demonstration")
    print("-" * 60)
    
    # Test A: Normal Business Request
    print("\n🔹 Scenario A: Normal Database Query (data-agent)")
    e_normal = AgentEvent(
        agent_id="data-agent",
        tool_call=ToolCall("search_customer", {"customer_id": "CUST-002"}),
        sensitivity_score=0.2,
        timestamp=datetime.now().replace(hour=14) # 2 PM
    )
    rep_normal = await analyzer.analyze(e_normal)
    print(f"Score: {rep_normal.anomaly_score:.4f} | Severity: {rep_normal.severity.value}")
    
    # Test B: Off-hours Sensitive Access
    print("\n🔹 Scenario B: Off-hours Sensitive Access (finance-agent at 3 AM weekend)")
    # Create a weekend date (e.g. October 10, 2026 is a Saturday)
    weekend_date = datetime(2026, 10, 10, 3, 0)
    e_offhours = AgentEvent(
        agent_id="finance-agent",
        tool_call=ToolCall("search_invoice", {"invoice_id": "INV-ALL"}),
        sensitivity_score=0.9,
        timestamp=weekend_date
    )
    
    rep_offhours = await analyzer.analyze(e_offhours)
    print(f"Score: {rep_offhours.anomaly_score:.4f} | Severity: {rep_offhours.severity.value}")
    for res in rep_offhours.fired_detectors:
        print(f"  🚨 Triggered: {res.detector_name} (Score: {res.score:.2f})")
        
    # Test C: Data Exfiltration Attempt
    print("\n🔹 Scenario C: Data Exfiltration Attempt (Massive payload from data-agent)")
    tc_exfil = ToolCall("get_customer_details", {"data": "A" * 120000}) # 120KB payload
    
    e_exfil = AgentEvent(
        agent_id="data-agent",
        tool_call=tc_exfil,
        sensitivity_score=0.5
    )
    rep_exfil = await analyzer.analyze(e_exfil)
    print(f"Score: {rep_exfil.anomaly_score:.4f} | Severity: {rep_exfil.severity.value}")
    for res in rep_exfil.fired_detectors:
        print(f"  🚨 Triggered: {res.detector_name} (Score: {res.score:.2f})")
        if "param_size_zscore" in res.evidence:
             print(f"     -> Z-Score deviation: {res.evidence['param_size_zscore']}")
        
    # Test D: Privilege Escalation / Delegation Abuse
    print("\n🔹 Scenario D: Deep Delegation Chain Abuse")
    e_deleg = AgentEvent(
        agent_id="finance-agent",
        tool_call=ToolCall("search_invoice", {"invoice_id": "INV-001"}),
        sensitivity_score=0.7,
        delegation=DelegationInfo(delegated_by="supervisor-agent", chain_depth=4, delegation_token="tok")
    )
    rep_deleg = await analyzer.analyze(e_deleg)
    print(f"Score: {rep_deleg.anomaly_score:.4f} | Severity: {rep_deleg.severity.value}")
    for res in rep_deleg.fired_detectors:
        print(f"  🚨 Triggered: {res.detector_name} (Score: {res.score:.2f})")
        
    print("\n" + "="*60)
    print("Demo execution finished successfully.")

if __name__ == "__main__":
    asyncio.run(train_and_evaluate())
