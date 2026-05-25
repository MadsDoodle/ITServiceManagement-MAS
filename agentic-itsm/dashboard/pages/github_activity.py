"""
GitHub Activity page — all issues created, project column transitions, and field updates.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_github_activity

_SEV_COLOUR = {
    "P1":  "🔴",
    "P2":  "🟡",
    "P3":  "🔵",
    "Low": "⚪",
}


def render():
    st.title("🐙 GitHub Activity")
    st.caption("Issues created and project board updates by the GitHub Operations Agent.")

    activity = get_github_activity()

    if not activity:
        st.info("No GitHub activity yet. Configure GITHUB_TOKEN and run the workflow.")
        return

    st.markdown(f"**{len(activity)} GitHub issues created**")
    st.divider()

    for item in activity:
        sev    = item.get("severity") or "?"
        icon   = _SEV_COLOUR.get(sev, "⚪")
        itype  = item.get("incident_type") or "Unknown"
        iid    = item.get("incident_id") or "N/A"
        ts     = (item.get("created_at") or "")[:16].replace("T", " ")
        col    = item.get("column") or "Unknown"
        url    = item.get("issue_url")
        number = item.get("issue_number")
        esc    = item.get("escalated", False)

        esc_tag = " 🔴 **ESCALATED**" if esc else ""

        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                link = f"[#{number}]({url})" if url else f"#{number}"
                st.markdown(
                    f"{icon} **{sev}** — {itype} · {link}{esc_tag}  \n"
                    f"<small>`{iid}` · {ts} · Column: **{col}**</small>",
                    unsafe_allow_html=True,
                )
            with col2:
                if url:
                    st.link_button("Open Issue →", url)

        st.markdown("---")
