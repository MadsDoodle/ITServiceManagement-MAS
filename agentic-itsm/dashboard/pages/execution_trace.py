"""
Execution Trace page — visualises the LangGraph agent pipeline for a selected run.
"""
from __future__ import annotations

import json

import streamlit as st

from dashboard.services.dashboard_api import get_all_workflow_runs, get_workflow_run
from dashboard.components.timeline import render_timeline
from dashboard.components.agent_status import render_agent_status
from dashboard.components.workflow_graph import render_workflow_diagram


def render():
    st.title("🔀 Execution Trace")
    st.caption("Inspect the agent execution pipeline for any workflow run.")

    runs = get_all_workflow_runs(limit=100)
    if not runs:
        st.info("No workflow runs found. Trigger a workflow run first.")
        return

    # Selector
    options = {
        f"{r.get('incident_id')} — {r.get('severity','?')} — {r.get('created_at','')[:16]}": r.get("incident_id")
        for r in runs
    }
    selected_label = st.selectbox("Select Incident", list(options.keys()))
    selected_id    = options[selected_label]

    run = get_workflow_run(selected_id)
    if not run:
        st.error("Could not load run details.")
        return

    state = run.get("state", {})
    trace = state.get("trace", [])

    # Workflow diagram
    st.markdown("#### Pipeline Overview")
    last_agent = trace[-1].get("agent", "").lower().replace("agent", "") if trace else ""
    # Map agent name to graph node key
    node_map = {
        "monitoring":     "monitor",
        "classification": "classify",
        "rca":            "rca",
        "escalation":     "escalate",
        "github":         "github_ops",
        "notification":   "notify",
        "workflow":       "complete",
    }
    active_node = next((v for k, v in node_map.items() if k in last_agent.lower()), "")
    render_workflow_diagram(active_node)

    st.divider()

    # Agent status row
    render_agent_status(trace)

    st.divider()

    # Full timeline
    render_timeline(trace)

    st.divider()

    # Raw state inspector
    with st.expander("🔎 Raw State JSON", expanded=False):
        # Exclude trace from raw display to avoid duplication
        display_state = {k: v for k, v in state.items() if k != "trace"}
        st.json(display_state)
