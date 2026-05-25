import streamlit as st

from frontend.services.api_client import get_health


def render_navbar():
    st.sidebar.title("⚙️ Internal Ops")
    st.sidebar.markdown("---")

    health = get_health()
    if "error" in health:
        st.sidebar.error("❌ Backend Offline")
        st.sidebar.caption(health["error"])
    else:
        overall = health.get("overall", "unknown")
        icon = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(overall, "⚫")
        label = f"{icon} System {overall.title()}"
        if overall == "healthy":
            st.sidebar.success(label)
        elif overall == "degraded":
            st.sidebar.warning(label)
        else:
            st.sidebar.error(label)

        col1, col2 = st.sidebar.columns(2)
        col1.metric("Healthy", health.get("healthy", "?"))
        col2.metric("Degraded", health.get("degraded", "?"))

    st.sidebar.markdown("---")
    st.sidebar.caption("Internal Ops Dashboard · v1.3.0")
    st.sidebar.caption("ITSM Integration Target")