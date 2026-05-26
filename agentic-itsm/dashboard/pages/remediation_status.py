"""
Remediation Status — shows all remediation attempts, their strategies, outcomes, and stability.
"""
from __future__ import annotations

import streamlit as st

from state.persistent_store import get_all_incidents


def render():
    st.title("🔧 Remediation Status")
    st.caption("All remediation attempts, their strategies, outcomes, and recovery validation status.")

    incidents = get_all_incidents(limit=200)
    attempted = [i for i in incidents if i.get("remediation_attempted")]
    succeeded = [i for i in attempted if i.get("remediation_succeeded")]
    failed    = [i for i in attempted if not i.get("remediation_succeeded")]
    monitoring = [i for i in incidents if i.get("lifecycle_stage") == "monitoring"]
    resolved   = [i for i in incidents if i.get("lifecycle_stage") == "resolved"
                  and i.get("recovery_validated")]

    # ── Summary ────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Attempted",  len(attempted))
    c2.metric("✅ Succeeded",     len(succeeded))
    c3.metric("❌ Failed",        len(failed))
    c4.metric("📡 Monitoring",    len(monitoring))
    c5.metric("🏁 Validated",     len(resolved))

    st.divider()

    # ── Active monitoring ──────────────────────────────────────────────────────
    if monitoring:
        st.subheader("📡 Currently Monitoring (Awaiting Stability)")
        for inc in monitoring:
            iid    = inc.get("incident_id", "N/A")
            checks = inc.get("stability_checks_passed", 0)
            started = (inc.get("monitoring_started_at") or "")[:16].replace("T", " ")
            strategy = inc.get("remediation_strategy") or "?"
            st.markdown(
                f"- `{iid}` — strategy: `{strategy}` · {checks} stability checks · "
                f"monitoring since {started}"
            )
        st.divider()

    # ── Remediation attempt table ─────────────────────────────────────────────
    st.subheader("All Remediation Attempts")
    if not attempted:
        st.info("No remediation attempts yet.")
        return

    tab_success, tab_failed = st.tabs(["✅ Succeeded", "❌ Failed / Partial"])

    with tab_success:
        if not succeeded:
            st.info("No successful remediations yet.")
        for inc in succeeded:
            _render_remediation_row(inc, success=True)

    with tab_failed:
        if not failed:
            st.info("No failed remediations.")
        for inc in failed:
            _render_remediation_row(inc, success=False)


def _render_remediation_row(inc: dict, success: bool):
    iid      = inc.get("incident_id", "N/A")
    sev      = inc.get("severity") or "?"
    itype    = inc.get("incident_type") or "Unknown"
    strategy = inc.get("remediation_strategy") or "?"
    detail   = inc.get("remediation_detail") or "_No detail_"
    retries  = inc.get("remediation_retries", 0)
    stage    = inc.get("lifecycle_stage") or "?"
    icon     = "✅" if success else "❌"

    st.markdown(
        f"{icon} `{iid}` — **[{sev}]** {itype}  \n"
        f"Strategy: `{strategy}` · Stage: `{stage}` · Retries: {retries}  \n"
        f"_{detail[:120]}_"
    )
