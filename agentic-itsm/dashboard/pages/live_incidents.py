"""
Live Incident Feed — real-time incident lifecycle view.
Shows all active incidents with severity, lifecycle stage, escalation state.
"""
from __future__ import annotations

import json
import streamlit as st

from dashboard.services.dashboard_api import (
    get_all_incidents,
    get_dashboard_summary,
)

_STAGE_COLOURS = {
    "new":             "#0075ca",
    "triage":          "#e4e669",
    "investigating":   "#f0883e",
    "fix_in_progress": "#8957e5",
    "awaiting_review": "#d73a4a",
    "monitoring":      "#0d7377",
    "resolved":        "#2da44e",
}
_STAGE_ICONS = {
    "new":             "🆕",
    "triage":          "🏷️",
    "investigating":   "🔍",
    "fix_in_progress": "🔧",
    "awaiting_review": "⏳",
    "monitoring":      "📡",
    "resolved":        "✅",
}
_SEV_COLOURS = {
    "P1": "#d73a4a", "P2": "#e4e669",
    "P3": "#0075ca", "Low": "#cfd3d7",
}


def render():
    st.title("📋 Live Incident Feed")
    st.caption("Real-time view of all AI-managed incidents and their lifecycle progression.")

    auto_refresh = st.checkbox("Auto-refresh every 10s", value=False)
    if auto_refresh:
        import time; time.sleep(10); st.rerun()

    summary = get_dashboard_summary()

    # ── Summary strip ─────────────────────────────────────────────────────────
    cols = st.columns(5)
    cols[0].metric("Total", summary["total_incidents"])
    cols[1].metric("🔴 Open", summary["open_incidents"])
    cols[2].metric("⏳ Awaiting Review", summary["awaiting_human_review"])
    cols[3].metric("✅ Resolved", summary["resolved_incidents"])
    cols[4].metric("⚠️ Escalated", summary["escalated_incidents"])

    st.divider()

    # ── Lifecycle stage bar ───────────────────────────────────────────────────
    stage_breakdown = summary.get("stage_breakdown", {})
    if stage_breakdown:
        st.markdown("**Incidents by Lifecycle Stage**")
        bar_cols = st.columns(len(stage_breakdown) or 1)
        for col, (stage, count) in zip(bar_cols, stage_breakdown.items()):
            icon   = _STAGE_ICONS.get(stage, "⚙️")
            colour = _STAGE_COLOURS.get(stage, "#888")
            col.markdown(
                f"<div style='text-align:center;padding:8px;"
                f"border-top:3px solid {colour};border-radius:4px;background:#1e1e2e;'>"
                f"<b style='color:{colour};'>{count}</b><br/>"
                f"<small>{icon} {stage.replace('_', ' ').title()}</small></div>",
                unsafe_allow_html=True,
            )
        st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    sev_filter   = c1.selectbox("Severity", ["All", "P1", "P2", "P3", "Low"])
    stage_filter = c2.selectbox("Stage", ["All", "new", "triage", "investigating",
                                           "fix_in_progress", "awaiting_review",
                                           "monitoring", "resolved"])
    esc_filter   = c3.selectbox("Escalation", ["All", "Escalated", "Not Escalated"])

    incidents = get_all_incidents(limit=200)
    if sev_filter   != "All":
        incidents = [i for i in incidents if i.get("severity") == sev_filter]
    if stage_filter != "All":
        incidents = [i for i in incidents if i.get("lifecycle_stage") == stage_filter]
    if esc_filter   == "Escalated":
        incidents = [i for i in incidents if i.get("escalation_required")]
    elif esc_filter == "Not Escalated":
        incidents = [i for i in incidents if not i.get("escalation_required")]

    if not incidents:
        st.info("No incidents match the selected filters.")
        return

    st.markdown(f"**{len(incidents)} incident(s)**")

    for inc in incidents:
        _render_incident_card(inc)


def _render_incident_card(inc: dict):
    iid      = inc.get("incident_id", "N/A")
    sev      = inc.get("severity") or "?"
    itype    = inc.get("incident_type") or "Unknown"
    stage    = inc.get("lifecycle_stage") or "unknown"
    ts       = (inc.get("created_at") or "")[:16].replace("T", " ")
    esc      = bool(inc.get("escalation_required"))
    url      = inc.get("github_issue_url")
    issue    = inc.get("github_issue_number")
    remediated = bool(inc.get("remediation_succeeded"))
    risk     = inc.get("risk_score", 0.0) or 0.0
    conf     = inc.get("ai_confidence", 0.0) or 0.0

    sev_colour   = _SEV_COLOURS.get(sev, "#888")
    stage_colour = _STAGE_COLOURS.get(stage, "#888")
    stage_icon   = _STAGE_ICONS.get(stage, "⚙️")
    issue_link   = f"[#{issue}]({url})" if url and issue else ""

    esc_tag = " · 🔴 **ESCALATED**" if esc else ""
    rem_tag = " · 🔧 Remediated" if remediated else ""

    with st.container():
        st.markdown(
            f"""<div style="border-left:4px solid {sev_colour};padding:10px 14px;
                background:#1a1a2e;border-radius:4px;margin-bottom:4px;">
              <span style="color:{sev_colour};font-weight:bold;">[{sev}]</span>
              &nbsp;
              <span style="font-weight:bold;">{itype}</span>
              &nbsp;&nbsp;
              <span style="background:{stage_colour};color:white;padding:2px 8px;
                           border-radius:10px;font-size:0.8em;">
                {stage_icon} {stage.replace("_"," ").title()}
              </span>
              {esc_tag}{rem_tag}
              <br/>
              <code style="font-size:0.78em;">{iid}</code>
              &nbsp;·&nbsp;<small>{ts}</small>
              &nbsp;·&nbsp;<small>Risk: <b>{risk:.2f}</b></small>
              &nbsp;·&nbsp;<small>Confidence: <b>{conf:.0%}</b></small>
              {"&nbsp;·&nbsp;<small>" + issue_link + "</small>" if issue_link else ""}
            </div>""",
            unsafe_allow_html=True,
        )

        with st.expander(f"↳  Details — {iid}", expanded=False):
            c1, c2 = st.columns(2)
            c1.markdown(f"**RCA:** {inc.get('root_cause_summary') or '_Pending_'}")
            c2.markdown(f"**Remediation:** {inc.get('remediation_detail') or '_Not attempted_'}")
            c3, c4 = st.columns(2)
            c3.markdown(f"**Stability checks:** {inc.get('stability_checks_passed', 0)}")
            c4.markdown(f"**Retries:** {inc.get('remediation_retries', 0)}")
            if url:
                st.markdown(f"[Open GitHub Issue →]({url})")
