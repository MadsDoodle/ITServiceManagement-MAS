"""
System Health — live view of the monitored ops dashboard health and metrics.
"""
from __future__ import annotations

import streamlit as st

from dashboard.services.dashboard_api import get_live_ops_data


def render():
    st.title("🩺 System Health")
    st.caption("Live view of the monitored Internal Ops Dashboard system.")

    auto_refresh = st.checkbox("Auto-refresh every 15s", value=False)
    if auto_refresh:
        import time; time.sleep(15); st.rerun()

    if st.button("🔄 Refresh Now"):
        st.rerun()

    data = get_live_ops_data()
    if "error" in data:
        st.error(f"Cannot reach ops dashboard: {data['error']}")
        st.info("Make sure the Internal Ops Dashboard backend is running on port 8000.")
        return

    # ── Overall health ────────────────────────────────────────────────────────
    health  = data.get("health", {})
    overall = health.get("overall", "unknown")
    colour  = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(overall, "⚪")
    label   = {"healthy": "success", "degraded": "warning", "down": "error"}.get(overall, "info")

    banner_fn = getattr(st, label, st.info)
    banner_fn(
        f"{colour} **System Overall: {overall.upper()}**  —  "
        f"{health.get('healthy', 0)} healthy, "
        f"{health.get('degraded', 0)} degraded, "
        f"{health.get('down', 0)} down"
    )

    # ── Metrics strip ─────────────────────────────────────────────────────────
    m = data.get("metrics", {})
    if m:
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Latency",    f"{m.get('request_latency_ms', 0):.0f}ms")
        mc2.metric("Error Rate", f"{m.get('error_rate_pct', 0):.1f}%")
        mc3.metric("RPM",        f"{m.get('requests_per_min', 0):.0f}")
        mc4.metric("Uptime",     f"{m.get('service_uptime_pct', 0):.1f}%")
        mc5.metric("Open Incidents", m.get("active_incidents", 0))

    # ── Service status cards ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Service Status")
    services = data.get("services", [])
    if services:
        svc_cols = st.columns(len(services))
        for col, svc in zip(svc_cols, services):
            status  = svc.get("status", "unknown")
            icon    = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(status, "⚪")
            uptime  = svc.get("uptime_pct", 0.0)
            notes   = svc.get("notes") or ""
            col.markdown(
                f"""<div style="text-align:center;padding:10px;background:#1a1a2e;
                    border-radius:8px;border-top:3px solid
                    {'#2da44e' if status=='healthy' else '#e4e669' if status=='degraded' else '#d73a4a'};">
                  <div style="font-size:1.5em;">{icon}</div>
                  <b>{svc.get('service_name','?')}</b><br/>
                  <small>{status.upper()}</small><br/>
                  <small>Uptime: {uptime:.1f}%</small>
                </div>""",
                unsafe_allow_html=True,
            )
            if notes:
                col.caption(notes[:60])

    # ── Open incidents ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Open Incidents (Ops Dashboard)")
    incidents = data.get("incidents", [])
    if incidents:
        for inc in incidents:
            sev   = inc.get("severity", "?")
            title = inc.get("title", "?")
            svc   = inc.get("affected_service", "?")
            status = inc.get("status", "?")
            st.markdown(f"- **[{sev}]** {title} · `{svc}` · _{status}_")
    else:
        st.info("No open incidents on the ops dashboard.")

    # ── Recent deployments ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Recent Deployments")
    deps = data.get("deployments", [])
    if deps:
        for dep in deps:
            status = dep.get("status", "?")
            icon   = {"success": "✅", "failed": "❌", "rolled_back": "↩️",
                      "pending": "⏳"}.get(status, "⚙️")
            ver    = dep.get("version", "?")
            by     = dep.get("deployed_by", "?")
            ts     = (dep.get("timestamp") or "")[:16].replace("T", " ")
            notes  = (dep.get("notes") or "")[:80]
            st.markdown(
                f"{icon} **{dep.get('deployment_id')}** — v{ver} "
                f"by `{by}` · {ts}"
                + (f"\n  > _{notes}_" if notes else "")
            )
