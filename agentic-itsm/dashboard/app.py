"""
Agentic ITSM — AI Operations Dashboard
Streamlit multi-page app for monitoring the AI workflow.

Run with:
  streamlit run dashboard/app.py --server.port 8502
"""
from __future__ import annotations

import sys
import os

# Ensure the project root is on the path when run from subdirectory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from dashboard.pages import (
    incidents,
    execution_trace,
    github_activity,
    notifications,
    live_logs,
)
from dashboard.services.dashboard_api import get_live_ops_data, get_dashboard_summary, init_state_db

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic ITSM — Ops Console",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure DB is initialised
init_state_db()

# ── Sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.title("🤖 Agentic ITSM")
st.sidebar.caption("AI Operations Console")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    [
        "📋 Incident Feed",
        "🔀 Execution Trace",
        "🐙 GitHub Activity",
        "📧 Notifications",
        "📄 Live Logs",
    ],
    label_visibility="collapsed",
)

# ── Ops health mini-panel in sidebar ─────────────────────────────────────────
st.sidebar.divider()
st.sidebar.markdown("**Monitored System Health**")
try:
    live = get_live_ops_data()
    health = live.get("health", {})
    overall = health.get("overall", "unknown")
    colour  = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(overall, "⚪")
    st.sidebar.markdown(f"{colour} System: **{overall.upper()}**")
    metrics = live.get("metrics", {})
    if metrics:
        st.sidebar.caption(
            f"Latency: {metrics.get('request_latency_ms', 0):.0f}ms | "
            f"Error rate: {metrics.get('error_rate_pct', 0):.1f}%"
        )
except Exception:
    st.sidebar.caption("⚠️ Ops dashboard offline")

st.sidebar.divider()
summary = get_dashboard_summary()
st.sidebar.metric("Workflow Runs", summary["total_workflow_runs"])
st.sidebar.metric("Escalated",     summary["escalated_incidents"])

# ── Route to page ─────────────────────────────────────────────────────────────
if page == "📋 Incident Feed":
    incidents.render()
elif page == "🔀 Execution Trace":
    execution_trace.render()
elif page == "🐙 GitHub Activity":
    github_activity.render()
elif page == "📧 Notifications":
    notifications.render()
elif page == "📄 Live Logs":
    live_logs.render()
