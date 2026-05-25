"""
Streamlit incident card component.
Renders a single workflow run as a styled card.
"""
from __future__ import annotations

import streamlit as st


_SEVERITY_COLOURS = {
    "P1":  "#d73a4a",
    "P2":  "#e4e669",
    "P3":  "#0075ca",
    "Low": "#cfd3d7",
}


def render_incident_card(run: dict):
    sev    = run.get("severity") or "Unknown"
    itype  = run.get("incident_type") or "Unknown"
    iid    = run.get("incident_id") or "N/A"
    ts     = run.get("created_at", "")[:19].replace("T", " ")
    esc    = bool(run.get("escalation_required"))
    conf   = run.get("ai_confidence", 0.0)
    url    = run.get("github_issue_url")
    issue  = run.get("github_issue_number")
    col    = run.get("github_column") or "Unknown"
    colour = _SEVERITY_COLOURS.get(sev, "#888")

    esc_badge  = "🔴 ESCALATED" if esc else "🟢 No Escalation"
    issue_link = f"[#{issue}]({url})" if url and issue else "_Not created_"

    with st.container():
        st.markdown(
            f"""
<div style="border-left:4px solid {colour};padding:10px 14px;
            background:#1e1e2e;border-radius:4px;margin-bottom:8px;">
  <span style="color:{colour};font-weight:bold;font-size:1.05em;">
    [{sev}] {itype}
  </span>
  &nbsp;&nbsp;
  <span style="color:#aaa;font-size:0.85em;">{ts}</span>
  &nbsp;&nbsp;
  <span style="font-size:0.85em;">{esc_badge}</span>
  <br/>
  <code style="font-size:0.8em;">{iid}</code>
  &nbsp;·&nbsp;
  <span style="font-size:0.85em;">Column: <b>{col}</b></span>
  &nbsp;·&nbsp;
  <span style="font-size:0.85em;">Confidence: <b>{conf:.0%}</b></span>
  &nbsp;·&nbsp;
  <span style="font-size:0.85em;">GitHub: {issue_link}</span>
</div>
""",
            unsafe_allow_html=True,
        )
