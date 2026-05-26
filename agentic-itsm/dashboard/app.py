"""
Agentic ITSM — AI Operational Command Center
Streamlit multi-page dashboard.

Run with:
  streamlit run dashboard/app.py --server.port 8502
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from dashboard.services.dashboard_api import get_live_ops_data, get_dashboard_summary, init_state_db

st.set_page_config(
    page_title="Agentic ITSM — Command Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🤖 Agentic ITSM")
st.sidebar.caption("AI Operational Command Center")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    [
        "📋 Live Incident Feed",
        "🔀 Workflow Timeline",
        "💥 Failure Injection",
        "🧠 AI Reasoning",
        "👤 Human Review Queue",
        "📄 Live Logs",
        "🐙 GitHub Activity",
        "🩺 System Health",
        "🔧 Remediation Status",
        "🔗 Incident Correlation",
        "🧠 Operational Memory",
        "🔭 Orchestration Health",
    ],
    label_visibility="collapsed",
)

# ── Live health mini-panel in sidebar ────────────────────────────────────────
st.sidebar.divider()
st.sidebar.markdown("**Monitored System**")
try:
    live    = get_live_ops_data()
    health  = live.get("health", {})
    overall = health.get("overall", "unknown")
    colour  = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(overall, "⚪")
    st.sidebar.markdown(f"{colour} **{overall.upper()}**")
    m = live.get("metrics", {})
    if m:
        st.sidebar.caption(
            f"Latency: {m.get('request_latency_ms', 0):.0f}ms  |  "
            f"Errors: {m.get('error_rate_pct', 0):.1f}%"
        )
except Exception:
    st.sidebar.caption("⚠️ Ops dashboard offline")

st.sidebar.divider()
summary = get_dashboard_summary()
c1, c2 = st.sidebar.columns(2)
c1.metric("Open", summary.get("open_incidents", 0))
c2.metric("Escalated", summary.get("escalated_incidents", 0))
c3, c4 = st.sidebar.columns(2)
c3.metric("Resolved", summary.get("resolved_incidents", 0))
c4.metric("⏳ Review", summary.get("awaiting_human_review", 0))

# ── Page routing ──────────────────────────────────────────────────────────────
if page == "📋 Live Incident Feed":
    from dashboard.pages import live_incidents; live_incidents.render()
elif page == "🔀 Workflow Timeline":
    from dashboard.pages import execution_trace; execution_trace.render()
elif page == "💥 Failure Injection":
    from dashboard.pages import failure_injection; failure_injection.render()
elif page == "🧠 AI Reasoning":
    from dashboard.pages import ai_reasoning; ai_reasoning.render()
elif page == "👤 Human Review Queue":
    from dashboard.pages import human_review_queue; human_review_queue.render()
elif page == "📄 Live Logs":
    from dashboard.pages import live_logs; live_logs.render()
elif page == "🐙 GitHub Activity":
    from dashboard.pages import github_activity; github_activity.render()
elif page == "🩺 System Health":
    from dashboard.pages import system_health; system_health.render()
elif page == "🔧 Remediation Status":
    from dashboard.pages import remediation_status; remediation_status.render()
elif page == "🔗 Incident Correlation":
    from dashboard.pages import correlation_view; correlation_view.render()
elif page == "🧠 Operational Memory":
    from dashboard.pages import operational_memory; operational_memory.render()
elif page == "🔭 Orchestration Health":
    from dashboard.pages import orchestration_health; orchestration_health.render()
