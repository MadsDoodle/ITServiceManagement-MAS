"""
Execution timeline component — renders a LangGraph trace as a visual step list.
"""
from __future__ import annotations

import streamlit as st

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


def render_timeline(trace: list[dict]):
    if not trace:
        st.info("No execution trace available for this run.")
        return

    st.markdown("#### Agent Execution Timeline")
    for i, entry in enumerate(trace):
        agent     = entry.get("agent", "Unknown")
        action    = entry.get("action", "")
        detail    = entry.get("detail", "")
        timestamp = entry.get("timestamp", "")[:19].replace("T", " ")
        stage     = entry.get("stage", "")
        icon      = _AGENT_ICONS.get(agent, "⚙️")
        connector = "│" if i < len(trace) - 1 else " "

        stage_badge = (
            f'<span style="background:#333;color:#aaa;padding:1px 6px;'
            f'border-radius:8px;font-size:0.75em;margin-left:6px;">{stage}</span>'
            if stage else ""
        )

        st.markdown(
            f"""
<div style="display:flex;align-items:flex-start;margin-bottom:2px;">
  <div style="width:28px;text-align:center;font-size:1.1em;">{icon}</div>
  <div style="flex:1;padding-left:8px;">
    <strong>{agent}</strong>{stage_badge}
    <span style="color:#888;font-size:0.8em;margin-left:8px;">{timestamp}</span><br/>
    <span style="color:#aaa;font-size:0.85em;"><code>{action}</code></span>
    {f'<br/><span style="font-size:0.8em;color:#999;">{detail[:180]}</span>' if detail else ""}
  </div>
</div>
<div style="margin-left:14px;color:#333;font-size:0.9em;">{connector}</div>
""",
            unsafe_allow_html=True,
        )
