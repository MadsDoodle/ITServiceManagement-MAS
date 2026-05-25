"""
Notifications page — shows email notification history and summaries.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_all_workflow_runs
from services.log_service import read_log_file


def render():
    st.title("📧 Notifications")
    st.caption("Email notifications sent by the Notification Agent for escalated incidents.")

    runs = get_all_workflow_runs(limit=200)
    notified = [r for r in runs if r.get("notification_sent")]
    skipped  = [r for r in runs if not r.get("notification_sent") and r.get("escalation_required")]

    c1, c2, c3 = st.columns(3)
    c1.metric("Emails Sent",      len(notified))
    c2.metric("Escalated (total)", sum(1 for r in runs if r.get("escalation_required")))
    c3.metric("Skipped / Failed",  len(skipped))

    st.divider()

    if not notified:
        st.info("No notifications sent yet. Escalated incidents will trigger email alerts.")
    else:
        st.markdown("#### Sent Notifications")
        for run in notified:
            iid  = run.get("incident_id") or "N/A"
            sev  = run.get("severity") or "?"
            ts   = (run.get("created_at") or "")[:16].replace("T", " ")
            itype = run.get("incident_type") or "Unknown"
            with st.expander(f"[{sev}] {itype} — {iid}  ·  {ts}"):
                import json
                try:
                    state = json.loads(run.get("state_json") or "{}")
                    summary = state.get("notification_summary", "_Not available_")
                    st.text(summary)
                except Exception:
                    st.text("Could not load notification summary.")

    if skipped:
        st.divider()
        st.markdown("#### Escalated — Notification Failed/Skipped")
        st.caption("These incidents were escalated but email was not sent (likely missing Gmail config).")
        for run in skipped:
            st.markdown(
                f"- `{run.get('incident_id')}` — **{run.get('severity')}** / {run.get('incident_type')} "
                f"— {(run.get('created_at') or '')[:16]}"
            )

    # Notification log tail
    st.divider()
    st.markdown("#### Notification Log (Last 50 Entries)")
    log_entries = read_log_file("notifications", lines=50)
    if log_entries:
        for entry in reversed(log_entries[-20:]):
            level = entry.get("level", "INFO")
            msg   = entry.get("message", "")
            ts    = (entry.get("timestamp") or "")[:19].replace("T", " ")
            event = entry.get("event", "")
            colour = "🔴" if level == "ERROR" else ("🟡" if level == "WARNING" else "🟢")
            st.markdown(f"{colour} `{ts}` **{event or msg}**")
    else:
        st.caption("No notification logs yet.")
