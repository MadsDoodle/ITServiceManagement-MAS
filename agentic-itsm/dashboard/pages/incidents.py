"""
Incident Feed page — shows all AI-managed workflow runs with severity, status, and escalation state.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_all_workflow_runs, get_dashboard_summary
from dashboard.components.incident_card import render_incident_card


def render():
    st.title("📋 Incident Feed")
    st.caption("All AI-managed incidents processed by the Agentic ITSM workflow.")

    # Summary metrics row
    summary = get_dashboard_summary()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Runs",         summary["total_workflow_runs"])
    c2.metric("Escalated",          summary["escalated_incidents"])
    c3.metric("GitHub Issues",      summary["github_issues_created"])
    c4.metric("Notifications Sent", summary["notifications_sent"])

    st.divider()

    # Severity filter
    col_filter, col_esc = st.columns(2)
    sev_filter = col_filter.selectbox(
        "Filter by Severity", ["All", "P1", "P2", "P3", "Low"], index=0
    )
    esc_filter = col_esc.selectbox(
        "Filter by Escalation", ["All", "Escalated", "Not Escalated"], index=0
    )

    runs = get_all_workflow_runs(limit=200)

    if sev_filter != "All":
        runs = [r for r in runs if r.get("severity") == sev_filter]
    if esc_filter == "Escalated":
        runs = [r for r in runs if r.get("escalation_required")]
    elif esc_filter == "Not Escalated":
        runs = [r for r in runs if not r.get("escalation_required")]

    if not runs:
        st.info("No incidents recorded yet. Run the workflow to generate incidents.")
        return

    st.markdown(f"**{len(runs)} incident(s) found**")
    for run in runs:
        render_incident_card(run)

        # Expandable detail
        with st.expander(f"Details — {run.get('incident_id', 'N/A')}", expanded=False):
            st.markdown(f"**Root Cause:** {run.get('root_cause_summary') or '_Not available_'}")
            anomaly_count = run.get("anomaly_count", 0)
            st.markdown(f"**Anomaly Count:** {anomaly_count}")
            col_l, col_r = st.columns(2)
            col_l.markdown(f"**Incident Type:** {run.get('incident_type') or 'N/A'}")
            col_r.markdown(f"**Confidence:** {run.get('ai_confidence', 0):.0%}")
            if run.get("github_issue_url"):
                st.markdown(f"[Open GitHub Issue →]({run['github_issue_url']})")
