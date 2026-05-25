"""
Agent status panel — shows which agents were invoked and their outcomes.
"""
from __future__ import annotations

import streamlit as st

_AGENTS = [
    "MonitoringAgent",
    "ClassificationAgent",
    "RCAAgent",
    "EscalationAgent",
    "GitHubAgent",
    "NotificationAgent",
]


def render_agent_status(trace: list[dict]):
    """Render a row of agent status indicators derived from the trace."""
    invoked = {entry.get("agent") for entry in trace}
    errored = {entry.get("agent") for entry in trace if "fail" in entry.get("action", "").lower()}

    cols = st.columns(len(_AGENTS))
    for col, agent in zip(cols, _AGENTS):
        short_name = agent.replace("Agent", "")
        if agent in errored:
            col.metric(short_name, "❌ Error")
        elif agent in invoked:
            col.metric(short_name, "✅ Done")
        else:
            col.metric(short_name, "⏸ Skipped")
