"""
GitHub Activity — issues created, project column transitions, field updates.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_github_activity

_SEV_ICON = {"P1": "🔴", "P2": "🟡", "P3": "🔵", "Low": "⚪"}
_STAGE_ICON = {
    "new": "🆕", "triage": "🏷️", "investigating": "🔍",
    "fix_in_progress": "🔧", "awaiting_review": "⏳",
    "monitoring": "📡", "resolved": "✅",
}


def render():
    st.title("🐙 GitHub Activity")
    st.caption("All GitHub issues created and project board column transitions by the ITSM system.")

    activity = get_github_activity()
    if not activity:
        st.info("No GitHub activity yet. Set GITHUB_TOKEN and run the monitoring loop.")
        return

    st.markdown(f"**{len(activity)} GitHub issues**")

    # Column distribution bar
    column_counts: dict[str, int] = {}
    for item in activity:
        col = item.get("column") or "Unknown"
        column_counts[col] = column_counts.get(col, 0) + 1

    if column_counts:
        bar_cols = st.columns(len(column_counts))
        for bc, (col_name, count) in zip(bar_cols, column_counts.items()):
            bc.metric(col_name, count)

    st.divider()

    for item in activity:
        sev    = item.get("severity") or "?"
        icon   = _SEV_ICON.get(sev, "⚪")
        itype  = item.get("incident_type") or "Unknown"
        iid    = item.get("incident_id") or "N/A"
        ts     = (item.get("created_at") or "")[:16].replace("T", " ")
        col    = item.get("column") or "Unknown"
        url    = item.get("issue_url")
        number = item.get("issue_number")
        esc    = item.get("escalated", False)
        stage  = item.get("lifecycle_stage") or "?"
        stage_icon = _STAGE_ICON.get(stage, "⚙️")

        esc_tag = " 🔴 **ESCALATED**" if esc else ""
        link    = f"[#{number}]({url})" if url else f"#{number}"

        with st.container():
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(
                    f"{icon} **{sev}** — {itype} · {link}{esc_tag}  \n"
                    f"<small>`{iid}` · {ts} · GitHub: **{col}** · "
                    f"Lifecycle: {stage_icon} **{stage}**</small>",
                    unsafe_allow_html=True,
                )
            with c2:
                if url:
                    st.link_button("Open →", url)
        st.markdown("---")
