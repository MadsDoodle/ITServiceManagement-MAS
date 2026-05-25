import streamlit as st

from frontend.components.log_viewer import render_log_viewer
from frontend.services.api_client import get_logs


def render():
    st.title("📋 Log Viewer")

    c1, c2, c3 = st.columns([2, 2, 1])
    log_type = c1.selectbox("Log Source", ["app", "incidents", "deployment"])
    lines = c2.number_input("Lines", min_value=10, max_value=500, value=100)
    if c3.button("🔄 Refresh"):
        st.rerun()

    data = get_logs(log_type=log_type, lines=int(lines))
    if "error" in data:
        st.error(f"Failed to load logs: {data['error']}")
        return

    entries = data.get("entries", [])
    st.caption(f"Showing {data.get('count', 0)} entries from **{log_type}.log**")
    render_log_viewer(entries)