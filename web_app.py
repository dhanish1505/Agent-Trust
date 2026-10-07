import os
import sys
import json
import asyncio
import io
from contextlib import redirect_stdout
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agenttrust"))
load_dotenv()

from agenttrust.behavior_analyzer import BehaviorAnalyzer, AgentEvent, ToolCall, DelegationInfo, AgentRole
from supervisor_agent import SupervisorAgent
from agenttrust.gateway import auth_engine

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/train")
async def train_model():
    analyzer = BehaviorAnalyzer() 
    
    try:
        with open("agent_behavior_dataset.json", "r") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        return {"status": "error", "message": "Dataset not found. Please generate it first."}
        
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
            tool_call=ToolCall(tool_name=row["tool_name"], parameters=params),
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
                delegation=DelegationInfo(delegated_by="parent", chain_depth=row["delegation_depth"], delegation_token="tok")
            )
            
        await analyzer.analyze(event)
        
    return {"status": "success", "message": f"Successfully trained on {len(dataset)} enterprise agent events!"}

@app.post("/api/test-a")
async def run_test_a():
    supervisor = SupervisorAgent()
    query = "Find customer CUST-002 and then get the details of invoice INV-003."
    
    f = io.StringIO()
    with redirect_stdout(f):
        response = supervisor.run(query)
    
    return {"query": query, "response": response, "logs": f.getvalue()}

@app.post("/api/test-b")
async def run_test_b():
    # Artificially drop trust
    trust = auth_engine._store.trust.get("data-agent")
    trust.adjust(-90.0, "Caught EXFILTRATION pattern by ML Behavior Analyzer.")
    auth_engine._store.trust.save(trust)
    
    supervisor = SupervisorAgent()
    query = "Who is customer CUST-001?"
    
    f = io.StringIO()
    with redirect_stdout(f):
        response = supervisor.run(query)
        
    # Restore trust for next run
    trust.score = 100.0
    auth_engine._store.trust.save(trust)
    
    return {"query": query, "response": response, "logs": f.getvalue()}

if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)
