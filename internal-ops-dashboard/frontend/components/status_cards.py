import streamlit as st

STATUS_ICON = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}


def render_service_cards(services: list):
    cols = st.columns(min(len(services), 5))
    for i, svc in enumerate(services):
        icon = STATUS_ICON.get(svc["status"], "⚫")
        with cols[i % 5]:
            st.metric(
                label=f"{icon} {svc['service_name']}",
                value=svc["status"].upper(),
                help=svc.get("notes") or f"Uptime: {svc.get('uptime_pct', '?')}%",
            )