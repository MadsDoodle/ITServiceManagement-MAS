"""
Workflow Timeline — visualises the LangGraph agent pipeline for a selected incident.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_all_incidents, get_workflow_run
from dashboard.components.timeline import render_timeline
from dashboard.components.workflow_graph import render_workflow_diagram

_AGENTS = [
    "MonitoringAgent", "ClassificationAgent", "RCAAgent",
    "RiskScoringAgent", "EscalationAgent", "GitHubAgent",
    "HumanReviewAgent", "RemediationAgent", "RecoveryValidationAgent",
    "ResolutionAgent", "NotificationAgent",
]
_AGENT_ICONS = {
    "MonitoringAgent":         "🔭",
    "ClassificationAgent":     "🏷️",
    "RCAAgent":                "🔍",
    "RiskScoringAgent":        "📊",
    "EscalationAgent":         "⚠️",
    "GitHubAgent":             "🐙",
    "HumanReviewAgent":        "👤",
    "RemediationAgent":        "🔧",
    "RecoveryValidationAgent": "📡",
    "ResolutionAgent":         "🏁",
    "NotificationAgent":       "📧",
    "Workflow":                "✅",
}


def render():
    st.title("🔀 Workflow Timeline")
    st.caption("Full LangGraph agent pipeline execution trace for any incident.")

    incidents = get_all_incidents(limit=100)
    if not incidents:
        st.info("No incidents recorded yet.")
        return

    options = {
        f"{i.get('incident_id')} — {i.get('severity','?')} — {(i.get('created_at') or '')[:16]}": i.get("incident_id")
        for i in incidents
    }
    selected_id = options[st.selectbox("Select Incident", list(options.keys()))]

    inc   = get_workflow_run(selected_id)
    if not inc:
        st.error("Could not load incident.")
        return

    state = inc.get("state") or {}
    trace = state.get("trace") or []

    # Pipeline overview
    st.markdown("#### Pipeline")
    last_agent = trace[-1].get("agent", "") if trace else ""
    node_map = {
        "Monitoring": "monitor", "Classification": "classify", "RCA": "rca",
        "RiskScoring": "score_risk", "Escalation": "escalate", "GitHub": "github_ops",
        "HumanReview": "human_review", "Remediation": "remediate",
        "RecoveryValidation": "recovery_validate", "Resolution": "resolve",
        "Notification": "notify_triage", "Workflow": "complete",
    }
    active_node = next((v for k, v in node_map.items() if k.lower() in last_agent.lower()), "")
    render_workflow_diagram(active_node)

    st.divider()

    # Agent status row
    invoked = {e.get("agent") for e in trace}
    errored = {e.get("agent") for e in trace if "fail" in e.get("action", "").lower()}
    cols = st.columns(len(_AGENTS))
    for col, agent in zip(cols, _AGENTS):
        short = agent.replace("Agent", "")
        icon  = _AGENT_ICONS.get(agent, "⚙️")
        if agent in errored:
            col.metric(f"{icon} {short}", "❌")
        elif agent in invoked:
            col.metric(f"{icon} {short}", "✅")
        else:
            col.metric(f"{icon} {short}", "⏸")

    st.divider()
    render_timeline(trace)

    with st.expander("🔎 Raw State", expanded=False):
        st.json({k: v for k, v in state.items() if k not in ("trace", "raw_logs")})
