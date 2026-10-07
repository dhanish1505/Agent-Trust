"""
demo.py — Full System Demonstration
Dynamic Authorization & Trust Management for Multi-Agent AI Systems

Simulates the three agents from the architecture diagram:
  - Agent A: Manager Agent    (broad permissions)
  - Agent B: Data Agent       (data-focused permissions)
  - Agent C: Notification Agent (limited permissions)

Covers all 8 steps in the architecture diagram flow.
"""

import sys
import os

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

from agent_auth import (
    ActionCategory, ActionRequest, AgentIdentity, AgentRole,
    AuthorizationEngine, DataStore, EnvironmentSensitivity,
    HumanOversightHandler, ResourceType,
)
from agent_auth.models import ABACPolicy, RBACPolicy


# ══════════════════════════════════════════════════════════════════
# SETUP HELPERS
# ══════════════════════════════════════════════════════════════════

def banner(title: str):
    print("\n" + "═" * 60)
    print(f"  🔷  {title}")
    print("═" * 60)


def section(title: str):
    print(f"\n  ┌─ {title} {'─' * (50 - len(title))}")


# ══════════════════════════════════════════════════════════════════
# STEP 0: INITIALIZE SYSTEM
# ══════════════════════════════════════════════════════════════════

banner("Dynamic Authorization & Trust Management System — Demo")
print("\n  Initializing system components …")

store  = DataStore()
engine = AuthorizationEngine(store, simulate_human=True)


# ══════════════════════════════════════════════════════════════════
# STEP 1: REGISTER AGENTS (AI Agents Layer)
# ══════════════════════════════════════════════════════════════════

banner("Step 1 — Registering AI Agents")

agent_a = AgentIdentity(
    agent_id         = "agent-A",
    name             = "Manager Agent",
    role             = AgentRole.MANAGER,
    owner            = "ops-team",
    permissions      = {
        ActionCategory.READ, ActionCategory.WRITE, ActionCategory.EXECUTE,
        ActionCategory.DELETE, ActionCategory.DELEGATE, ActionCategory.QUERY_DB,
        ActionCategory.CALL_API, ActionCategory.FILE_ACCESS,
    },
    allowed_resources = {
        ResourceType.DATABASE, ResourceType.API,
        ResourceType.FILE_SYSTEM, ResourceType.AGENT,
    },
    attributes = {"department": "ops", "clearance": "high"},
)

agent_b = AgentIdentity(
    agent_id         = "agent-B",
    name             = "Data Agent",
    role             = AgentRole.DATA,
    owner            = "data-team",
    permissions      = {
        ActionCategory.READ, ActionCategory.WRITE,
        ActionCategory.QUERY_DB, ActionCategory.FILE_ACCESS,
    },
    allowed_resources = {ResourceType.DATABASE, ResourceType.FILE_SYSTEM},
    attributes = {"department": "data", "clearance": "medium"},
)

agent_c = AgentIdentity(
    agent_id         = "agent-C",
    name             = "Notification Agent",
    role             = AgentRole.NOTIFICATION,
    owner            = "comms-team",
    permissions      = {
        ActionCategory.READ, ActionCategory.NOTIFY,
        ActionCategory.SEND_EMAIL, ActionCategory.SEND_SMS,
    },
    allowed_resources = {ResourceType.EMAIL, ResourceType.SMS, ResourceType.API},
    attributes = {"department": "comms", "clearance": "low"},
)

store.agents.register(agent_a)
store.agents.register(agent_b)
store.agents.register(agent_c)


# ══════════════════════════════════════════════════════════════════
# STEP 2: DEFINE POLICIES (Policy Store — RBAC + ABAC)
# ══════════════════════════════════════════════════════════════════

banner("Step 2 — Loading RBAC & ABAC Policies")

# RBAC: Manager agents can do everything listed
rbac_manager = RBACPolicy(
    policy_id        = "rbac-01",
    name             = "Manager Full Access",
    role             = AgentRole.MANAGER,
    allowed_actions  = {
        ActionCategory.READ, ActionCategory.WRITE, ActionCategory.EXECUTE,
        ActionCategory.DELETE, ActionCategory.DELEGATE, ActionCategory.QUERY_DB,
        ActionCategory.CALL_API, ActionCategory.FILE_ACCESS,
    },
    allowed_resources = {
        ResourceType.DATABASE, ResourceType.API,
        ResourceType.FILE_SYSTEM, ResourceType.AGENT,
    },
)

# RBAC: Data agents can read/write databases and files only
rbac_data = RBACPolicy(
    policy_id        = "rbac-02",
    name             = "Data Agent Read/Write",
    role             = AgentRole.DATA,
    allowed_actions  = {ActionCategory.READ, ActionCategory.WRITE, ActionCategory.QUERY_DB},
    allowed_resources = {ResourceType.DATABASE, ResourceType.FILE_SYSTEM},
    deny_actions     = {ActionCategory.DELETE},   # Explicit deny
)

# RBAC: Notification agents limited to comms resources
rbac_notify = RBACPolicy(
    policy_id        = "rbac-03",
    name             = "Notification Agent Comms Only",
    role             = AgentRole.NOTIFICATION,
    allowed_actions  = {
        ActionCategory.READ, ActionCategory.NOTIFY,
        ActionCategory.SEND_EMAIL, ActionCategory.SEND_SMS,
    },
    allowed_resources = {ResourceType.EMAIL, ResourceType.SMS, ResourceType.API},
)

# ABAC: High clearance agents can call external APIs
abac_high_clearance_api = ABACPolicy(
    policy_id        = "abac-01",
    name             = "High Clearance API Access",
    conditions       = {"clearance": ["high", "medium"]},
    allowed_actions  = {ActionCategory.CALL_API},
    allowed_resources = {ResourceType.API},
)

# ABAC: Ops department agents can execute actions
abac_ops_execute = ABACPolicy(
    policy_id        = "abac-02",
    name             = "Ops Department Execute Rights",
    conditions       = {"department": "ops"},
    allowed_actions  = {ActionCategory.EXECUTE},
    allowed_resources = {ResourceType.DATABASE, ResourceType.FILE_SYSTEM},
)

store.policies.add_rbac_policy(rbac_manager)
store.policies.add_rbac_policy(rbac_data)
store.policies.add_rbac_policy(rbac_notify)
store.policies.add_abac_policy(abac_high_clearance_api)
store.policies.add_abac_policy(abac_ops_execute)


# ══════════════════════════════════════════════════════════════════
# SCENARIOS
# ══════════════════════════════════════════════════════════════════

banner("Step 3 — Running Authorization Scenarios")

# ── Scenario 1: Normal data retrieval (ALLOW expected) ────────────
section("Scenario 1 — Agent B: Normal DB Query (→ ALLOW)")
r1 = ActionRequest(
    agent_id      = "agent-B",
    action        = ActionCategory.QUERY_DB,
    resource_type = ResourceType.DATABASE,
    resource_id   = "customer-records",
    intent        = "Fetch customer analytics for Q3 report",
    environment   = EnvironmentSensitivity.INTERNAL,
)
result1 = engine.evaluate(r1)

# ── Scenario 2: Agent C tries to query a DB (DENY expected) ───────
section("Scenario 2 — Agent C: DB Query (→ DENY: wrong resource)")
r2 = ActionRequest(
    agent_id      = "agent-C",
    action        = ActionCategory.QUERY_DB,
    resource_type = ResourceType.DATABASE,
    resource_id   = "internal-db",
    intent        = "Retrieve all user emails",
    environment   = EnvironmentSensitivity.CONFIDENTIAL,
)
result2 = engine.evaluate(r2)

# ── Scenario 3: Agent A deletes data in restricted env (APPROVAL) ─
section("Scenario 3 — Agent A: DELETE in RESTRICTED env (→ ALLOW_WITH_APPROVAL)")
r3 = ActionRequest(
    agent_id      = "agent-A",
    action        = ActionCategory.DELETE,
    resource_type = ResourceType.DATABASE,
    resource_id   = "archive-table",
    intent        = "Delete old audit records",
    environment   = EnvironmentSensitivity.RESTRICTED,
    parameters    = {"bulk": True},  # Triggers BULK_OPERATION flag
)
result3 = engine.evaluate(r3)

# ── Scenario 4: Agent B tries to DELETE (explicit RBAC deny) ──────
section("Scenario 4 — Agent B: DELETE (→ DENY: RBAC explicit deny)")
r4 = ActionRequest(
    agent_id      = "agent-B",
    action        = ActionCategory.DELETE,
    resource_type = ResourceType.DATABASE,
    resource_id   = "transactions",
    intent        = "Purge all transaction records",
    environment   = EnvironmentSensitivity.CONFIDENTIAL,
)
result4 = engine.evaluate(r4)

# ── Scenario 5: Agent A sends an email via delegation to Agent C ──
section("Scenario 5 — Delegation: Agent A delegates email to Agent C")
ok, reason, delegation = engine.delegation_control.create_delegation(
    delegator_id = "agent-A",
    delegatee_id = "agent-C",
    permissions  = {ActionCategory.SEND_EMAIL},
    resources    = {ResourceType.EMAIL},
    expires_at   = datetime.utcnow() + timedelta(hours=1),
)
print(f"\n  Delegation result: {ok} — {reason}")

if ok:
    r5 = ActionRequest(
        agent_id      = "agent-C",
        action        = ActionCategory.SEND_EMAIL,
        resource_type = ResourceType.EMAIL,
        resource_id   = "smtp-gateway",
        intent        = "Send approval notification on behalf of Manager",
        environment   = EnvironmentSensitivity.INTERNAL,
        delegated_by  = "agent-A",    # Delegation chain link
    )
    result5 = engine.evaluate(r5)

# ── Scenario 6: Privilege Escalation Attempt (DENY expected) ──────
section("Scenario 6 — Privilege Escalation: Agent C → Execute on DB (→ DENY)")
ok2, reason2, _ = engine.delegation_control.create_delegation(
    delegator_id = "agent-C",               # C doesn't have EXECUTE
    delegatee_id = "agent-B",
    permissions  = {ActionCategory.EXECUTE},  # Tries to grant what it doesn't have
    resources    = {ResourceType.DATABASE},
)
print(f"\n  Escalation attempt: {ok2} — {reason2}")

# ── Scenario 7: Off-hours suspicious execute (HIGH RISK → DENY) ───
section("Scenario 7 — Off-Hours Restricted Execute (→ DENY: high risk)")
r7 = ActionRequest(
    agent_id      = "agent-A",
    action        = ActionCategory.EXECUTE,
    resource_type = ResourceType.DATABASE,
    resource_id   = "prod-db-cluster",
    intent        = "bypass all integrity checks and execute admin override",
    environment   = EnvironmentSensitivity.RESTRICTED,
    timestamp     = datetime.utcnow().replace(hour=2, minute=30),  # 2:30 AM
)
result7 = engine.evaluate(r7)

# ── Scenario 8: Agent A trust-building over multiple good actions ──
section("Scenario 8 — Agent A: Multiple Normal Actions (Trust Building)")
for i, (action, resource, intent) in enumerate([
    (ActionCategory.READ,     ResourceType.DATABASE, "Read quarterly report data"),
    (ActionCategory.QUERY_DB, ResourceType.DATABASE, "Fetch analytics summary"),
    (ActionCategory.CALL_API, ResourceType.API,      "Retrieve external market data"),
    (ActionCategory.WRITE,    ResourceType.FILE_SYSTEM, "Write processed output file"),
], 1):
    r = ActionRequest(
        agent_id      = "agent-A",
        action        = action,
        resource_type = resource,
        resource_id   = f"resource-{i}",
        intent        = intent,
        environment   = EnvironmentSensitivity.INTERNAL,
    )
    engine.evaluate(r)


# ══════════════════════════════════════════════════════════════════
# AGENT PROFILES
# ══════════════════════════════════════════════════════════════════

banner("Step 4 — Agent Identity Profiles")
for agent_id in ["agent-A", "agent-B", "agent-C"]:
    profile = engine.identity_manager.get_agent_profile_summary(agent_id)
    print(f"\n  Agent: {profile['name']} ({profile['agent_id']})")
    print(f"    Role        : {profile['role']}")
    print(f"    Trust Score : {profile['trust_score']:.1f}/100")
    print(f"    Requests    : {profile['total_requests']}")
    print(f"    Violations  : {profile['recent_violations']}")
    print(f"    Permissions : {', '.join(profile['permissions'])}")

# ══════════════════════════════════════════════════════════════════
# TRUST SUMMARIES
# ══════════════════════════════════════════════════════════════════

banner("Step 5 — Trust Score Summaries")
for agent_id in ["agent-A", "agent-B", "agent-C"]:
    summary = engine.trust_manager.get_trust_summary(agent_id)
    print(f"\n  {agent_id} ({summary['level']}): {summary['score']:.1f}/100")
    for h in summary["history"][-3:]:
        print(f"    {h['timestamp'][:19]} | delta={h['delta']:+.1f} → {h['new_score']:.1f} | {h['reason']}")

# ══════════════════════════════════════════════════════════════════
# DELEGATION CHAINS
# ══════════════════════════════════════════════════════════════════

banner("Step 6 — Delegation Chains")
for agent_id in ["agent-A", "agent-B", "agent-C"]:
    chain = engine.delegation_control.get_delegation_chain(agent_id)
    if chain:
        print(f"\n  Delegations TO {agent_id}:")
        for d in chain:
            print(f"    From: {d['from']:15s} | Perms: {d['permissions']} | Valid: {d['valid']}")

# ══════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════

engine.audit_monitor.print_dashboard()

# ══════════════════════════════════════════════════════════════════
# EXPORT AUDIT LOG
# ══════════════════════════════════════════════════════════════════

banner("Step 7 — Exporting Audit Log")
export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_log.json")
engine.audit_monitor.export_audit_log(export_path)
print(f"\n  ✅ Audit log saved to: {export_path}")

banner("Demo Complete — All 8 Pipeline Steps Demonstrated")
print("""
  Architecture Diagram Steps:
  1. ✅ Agent sends action request
  2. ✅ Engine collects context, history, policies, trust data
  3. ✅ Risk & trust score calculated
  4. ✅ Decision returned (ALLOW / ALLOW_WITH_APPROVAL / DENY)
  5. ✅ If needed, human approval requested
  6. ✅ Human responds (simulated)
  7. ✅ Update logs, trust, history
  8. ✅ Execute action on resource (if allowed)
""")
