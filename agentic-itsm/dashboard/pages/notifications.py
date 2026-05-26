"""
Notifications — stage-based email history.
"""
from __future__ import annotations

import json
import streamlit as st

from state.persistent_store import get_all_incidents
from services.log_service import read_log_file
from utils.constants import NOTIF_BANNER_COLOURS

_STAGE_LABELS = {
    "incident_detected":   "🔵 Incident Detected",
    "triage_started":      "🟡 Triage Started",
    "investigation_started": "🟠 Investigation Started",
    "remediation_started": "🟣 Fix In Progress",
    "escalation_required": "🔴 Escalated",
    "monitoring_started":  "🩵 Monitoring",
    "incident_resolved":   "🟢 Resolved",
}


def render():
    st.title("📧 Notifications")
    st.caption("Stage-based email notifications sent by the Notification Agent.")

    incidents = get_all_incidents(limit=200)
    notified  = [i for i in incidents if i.get("notification_sent")]
    stages_all: list[str] = []
    for i in incidents:
        state = i.get("state") or {}
        stages_all.extend(state.get("notifications_sent_stages") or [])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Incidents Notified", len(notified))
    c2.metric("Total Emails Sent",  len(stages_all))
    c3.metric("Escalation Alerts",  stages_all.count("escalation_required"))
    c4.metric("Resolution Emails",  stages_all.count("incident_resolved"))

    st.divider()

    # Stage distribution
    if stages_all:
        st.markdown("**Emails Sent by Stage**")
        stage_counts: dict[str, int] = {}
        for s in stages_all:
            stage_counts[s] = stage_counts.get(s, 0) + 1
        bar_cols = st.columns(len(stage_counts))
        from utils.constants import NOTIF_BANNER_COLOURS
        for col, (stage, count) in zip(bar_cols, stage_counts.items()):
            colour = NOTIF_BANNER_COLOURS.get(stage, "#888")
            label  = _STAGE_LABELS.get(stage, stage)
            col.markdown(
                f"<div style='text-align:center;padding:6px;border-top:3px solid {colour};"
                f"background:#1a1a2e;border-radius:4px;'>"
                f"<b style='color:{colour};'>{count}</b><br/>"
                f"<small>{label}</small></div>",
                unsafe_allow_html=True,
            )
        st.divider()

    # Per-incident notification history
    if notified:
        st.markdown("#### Notified Incidents")
        for inc in notified[:50]:
            iid   = inc.get("incident_id") or "N/A"
            sev   = inc.get("severity") or "?"
            itype = inc.get("incident_type") or "Unknown"
            ts    = (inc.get("created_at") or "")[:16].replace("T", " ")
            state = inc.get("state") or {}
            sent_stages = state.get("notifications_sent_stages") or []
            with st.expander(f"[{sev}] {itype} — {iid}  ·  {ts}"):
                st.markdown(f"**Stages notified:** {', '.join(_STAGE_LABELS.get(s, s) for s in sent_stages)}")
                summary = state.get("notification_summary", "_Not available_")
                st.text(summary[:400])

    # Notification log
    st.divider()
    st.markdown("#### Notification Log (Last 30 entries)")
    for entry in reversed(read_log_file("notifications", lines=30)[-30:]):
        level = (entry.get("level") or "INFO").upper()
        icon  = {"ERROR": "🔴", "WARNING": "🟡"}.get(level, "🟢")
        ts    = (entry.get("timestamp") or "")[:19].replace("T", " ")
        event = entry.get("event") or entry.get("message") or ""
        st.markdown(f"{icon} `{ts}` **{event}**")
