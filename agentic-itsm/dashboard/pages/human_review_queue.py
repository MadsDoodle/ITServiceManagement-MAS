"""
Human Review Queue — shows paused incidents awaiting operator approval.
Operators can approve, reject, or add notes.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_awaiting_review, approve_incident
from state.persistent_store import get_all_incidents


def render():
    st.title("👤 Human Review Queue")
    st.caption(
        "Incidents that have been escalated and are awaiting human approval before "
        "the ITSM platform proceeds with remediation."
    )

    pending = get_awaiting_review()

    if not pending:
        st.success("✅ No incidents awaiting human review.")
        _show_recent_decisions()
        return

    st.warning(
        f"⚠️  **{len(pending)} incident(s)** paused and awaiting your decision.",
        icon="⚠️",
    )
    st.divider()

    for inc in pending:
        _render_review_card(inc)

    st.divider()
    _show_recent_decisions()


def _render_review_card(inc: dict):
    iid      = inc.get("incident_id", "N/A")
    sev      = inc.get("severity") or "?"
    itype    = inc.get("incident_type") or "Unknown"
    ts       = (inc.get("created_at") or "")[:16].replace("T", " ")
    reasons  = inc.get("escalation_reasons_json") or []
    rca      = inc.get("root_cause_summary") or "_Pending_"
    strategy = inc.get("remediation_strategy") or "none"
    risk     = inc.get("risk_score", 0.0) or 0.0
    conf     = inc.get("ai_confidence", 0.0) or 0.0
    url      = inc.get("github_issue_url")

    sev_colour = {"P1": "#d73a4a", "P2": "#f0883e", "P3": "#0075ca", "Low": "#888"}.get(sev, "#888")

    st.markdown(
        f"""<div style="border:2px solid {sev_colour};padding:14px;
            background:#1a1a2e;border-radius:8px;margin-bottom:8px;">
          <h3 style="color:{sev_colour};margin:0;">[{sev}] {itype}</h3>
          <code style="font-size:0.8em;">{iid}</code>
          &nbsp;·&nbsp;<small>{ts}</small>
          &nbsp;·&nbsp;<small>Risk: <b>{risk:.2f}</b></small>
          &nbsp;·&nbsp;<small>Confidence: <b>{conf:.0%}</b></small>
        </div>""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Escalation Reasons**")
        for r in reasons:
            st.markdown(f"- {r}")
        st.markdown(f"**Proposed Remediation:** `{strategy}`")
    with c2:
        st.markdown("**Root Cause Summary**")
        st.info(rca[:400])
        if url:
            st.markdown(f"[View GitHub Issue →]({url})")

    # Decision form
    with st.form(key=f"review_{iid}"):
        notes = st.text_area(
            "Operator Notes (optional)",
            placeholder="Add context, reasoning, or instructions...",
        )
        col_approve, col_reject = st.columns(2)
        approve_btn = col_approve.form_submit_button(
            "✅ Approve Remediation", type="primary", use_container_width=True
        )
        reject_btn  = col_reject.form_submit_button(
            "❌ Reject — Manual Intervention", use_container_width=True
        )

        if approve_btn:
            ok = approve_incident(iid, approved=True, notes=notes)
            if ok:
                st.success(f"✅ Approved — the ITSM platform will proceed with remediation for {iid}")
                st.rerun()
            else:
                st.error("Failed to record approval")

        if reject_btn:
            ok = approve_incident(iid, approved=False, notes=notes)
            if ok:
                st.warning(f"❌ Rejected — incident {iid} will require manual intervention")
                st.rerun()
            else:
                st.error("Failed to record rejection")

    st.divider()


def _show_recent_decisions():
    st.markdown("### Recent Review Decisions")
    all_inc = get_all_incidents(limit=100)
    decided = [i for i in all_inc if i.get("human_approved") is not None]
    if not decided:
        st.caption("No decisions recorded yet.")
        return
    for inc in decided[:10]:
        approved = inc.get("human_approved")
        icon     = "✅" if approved else "❌"
        notes    = inc.get("human_notes") or ""
        ts       = (inc.get("updated_at") or "")[:16].replace("T", " ")
        st.markdown(
            f"{icon} `{inc.get('incident_id')}` — **{inc.get('severity')}** "
            f"{inc.get('incident_type')} · {ts}"
            + (f" · _{notes[:80]}_" if notes else "")
        )
