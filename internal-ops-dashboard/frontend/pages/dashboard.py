import streamlit as st

from frontend.components.alert_banner import render_alert_banner
from frontend.components.status_cards import render_service_cards
from frontend.services.api_client import (
    get_health,
    get_incidents,
    get_latest_deployment,
    get_metrics,
    get_services,
)
from frontend.utils.formatting import format_status, time_since


def render():
    st.title("🏠 Operations Dashboard")
    st.caption("Real-time overview of internal service health and operational status")

    health = get_health()
    services_data = get_services()
    incidents_data = get_incidents()
    metrics = get_metrics()
    latest_dep = get_latest_deployment()

    incidents = incidents_data.get("incidents", [])
    services = services_data.get("services", [])

    render_alert_banner(incidents)
    st.markdown("---")

    # Top summary row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("System Health",   health.get("overall", "unknown").upper())
    c2.metric("Open Incidents",  sum(1 for i in incidents if i["status"] != "resolved"))
    c3.metric("Latency (ms)",    metrics.get("request_latency_ms", "?"))
    c4.metric("Error Rate",      f"{metrics.get('error_rate_pct', '?')}%")

    st.markdown("---")
    st.subheader("🔍 Service Health")
    if services:
        render_service_cards(services)
    else:
        st.warning("Could not load service data.")

    st.markdown("---")
    left, right = st.columns(2)

    with left:
        st.subheader("🚨 Active Incidents")
        active = [i for i in incidents if i["status"] != "resolved"][:5]
        if not active:
            st.success("No open incidents.")
        else:
            for inc in active:
                icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(inc["severity"], "⚫")
                with st.expander(f"{icon} {inc['title']}"):
                    st.write(f"**Service:** `{inc['affected_service']}`")
                    st.write(f"**Status:** {format_status(inc['status'])}")
                    st.write(f"**Since:** {time_since(inc['timestamp'])}")
                    if inc.get("notes"):
                        st.caption(inc["notes"])

    with right:
        st.subheader("🚀 Latest Deployment")
        if "error" in latest_dep:
            st.error(latest_dep["error"])
        else:
            icon = {"success": "🟢", "failed": "🔴", "rolled_back": "🟠", "pending": "⚪"}.get(
                latest_dep.get("status", ""), "⚫"
            )
            st.write(f"**{icon} {latest_dep.get('version', '?')}**")
            st.write(f"Status: {format_status(latest_dep.get('status', ''))}")
            st.write(f"Commit: `{latest_dep.get('commit_ref', '?')}`")
            st.write(f"By: {latest_dep.get('deployed_by', '?')}")
            st.write(f"When: {time_since(latest_dep.get('timestamp', ''))}")
            if latest_dep.get("notes"):
                st.caption(latest_dep["notes"])

    st.markdown("---")
    st.subheader("📊 Quick Metrics")
    m1, m2, m3 = st.columns(3)
    m1.metric("Requests / min",  metrics.get("requests_per_min", "?"))
    m2.metric("Service Uptime",  f"{metrics.get('service_uptime_pct', '?')}%")
    m3.metric("Deploys / week",  metrics.get("deployment_frequency_per_week", "?"))