import json
import random
from datetime import datetime, timedelta, timezone

def generate_agent_dataset(num_events=10000, anomaly_ratio=0.03):
    events = []
    
    agents = [
        {"id": "supervisor-agent", "role": "manager", "tools": ["delegate"]},
        {"id": "data-agent", "role": "data", "tools": ["search_customer", "get_customer_details"]},
        {"id": "finance-agent", "role": "executor", "tools": ["search_invoice"]}
    ]
    
    start_time = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    
    # ── 1. Generate Normal Baseline ───────────────────────────────────────────
    print(f"Generating {int(num_events * (1 - anomaly_ratio))} normal events...")
    for _ in range(int(num_events * (1 - anomaly_ratio))):
        agent = random.choice(agents)
        tool = random.choice(agent["tools"])
        
        # Normal business hours (8 AM - 6 PM) with some jitter
        hour = int(random.gauss(13, 3)) % 24
        minute = random.randint(0, 59)
        
        # Mostly weekdays (0-4)
        dow = random.choices(range(7), weights=[15, 15, 15, 15, 15, 5, 5])[0]
        
        event_time = start_time + timedelta(days=random.randint(0, 30), hours=hour, minutes=minute)
        
        # Normal parameters
        param_count = random.choices([1, 2, 3], weights=[50, 40, 10])[0]
        param_size = int(random.gauss(250, 50))  # 250 bytes average
        
        # Normal sensitivity (0.1 - 0.5)
        sensitivity = round(random.uniform(0.1, 0.5), 2)
        
        is_delegated = random.random() < 0.1
        delegation_depth = 1 if is_delegated else 0
        
        events.append({
            "agent_id": agent["id"],
            "agent_role": agent["role"],
            "tool_name": tool,
            "timestamp": event_time.isoformat(),
            "param_count": param_count,
            "param_size_bytes": max(50, param_size),
            "sensitivity_score": sensitivity,
            "is_delegated": is_delegated,
            "delegation_depth": delegation_depth,
            "is_anomaly": False
        })
        
    # ── 2. Inject Anomalies ───────────────────────────────────────────────────
    print(f"Injecting {int(num_events * anomaly_ratio)} anomalies...")
    for _ in range(int(num_events * anomaly_ratio)):
        agent = random.choice(agents)
        anomaly_type = random.choice(["off_hours", "data_exfil", "delegation_abuse", "prompt_injection"])
        
        event = {
            "agent_id": agent["id"],
            "agent_role": agent["role"],
            "tool_name": random.choice(agent["tools"]),
            "is_delegated": False,
            "delegation_depth": 0,
            "is_anomaly": True,
            "anomaly_type": anomaly_type
        }
        
        if anomaly_type == "off_hours":
            # 2 AM - 4 AM on a weekend
            hour = random.randint(2, 4)
            dow = random.choice([5, 6])
            event_time = start_time + timedelta(days=random.randint(0, 30), hours=hour)
            event.update({
                "timestamp": event_time.isoformat(),
                "param_count": 2,
                "param_size_bytes": 200,
                "sensitivity_score": 0.8  # High sensitivity during off-hours
            })
            
        elif anomaly_type == "data_exfil":
            # Massive payload size (e.g., trying to export DB)
            event_time = start_time + timedelta(days=random.randint(0, 30), hours=14)
            event.update({
                "timestamp": event_time.isoformat(),
                "param_count": 1,
                "param_size_bytes": random.randint(50000, 150000), # 50KB - 150KB
                "sensitivity_score": 0.6
            })
            
        elif anomaly_type == "delegation_abuse":
            # Deep delegation chain
            event_time = start_time + timedelta(days=random.randint(0, 30), hours=11)
            event.update({
                "timestamp": event_time.isoformat(),
                "param_count": 2,
                "param_size_bytes": 150,
                "sensitivity_score": 0.9,
                "is_delegated": True,
                "delegation_depth": random.randint(3, 5) # Exceeds normal max depth
            })
            
        elif anomaly_type == "prompt_injection":
            # Many parameters, specific keywords in payload simulation
            event_time = start_time + timedelta(days=random.randint(0, 30), hours=15)
            event.update({
                "timestamp": event_time.isoformat(),
                "param_count": random.randint(5, 10),
                "param_size_bytes": 1200,
                "sensitivity_score": 0.7
            })
            
        events.append(event)
        
    # Sort chronologically
    events.sort(key=lambda x: x["timestamp"])
    
    with open("agent_behavior_dataset.json", "w") as f:
        json.dump(events, f, indent=2)
        
    print(f"Dataset generated successfully with {len(events)} records.")
    print(f"Saved to: agent_behavior_dataset.json")

if __name__ == "__main__":
    generate_agent_dataset(15000, 0.05)
