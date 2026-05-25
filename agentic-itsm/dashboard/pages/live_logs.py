"""
Live Logs page — streams workflow, incident, and notification logs with filtering.
"""
from __future__ import annotations

import streamlit as st

from services.log_service import read_log_file


_LEVEL_COLOUR = {
    "ERROR":    "🔴",
    "CRITICAL": "🔴",
    "WARNING":  "🟡",
    "INFO":     "🟢",
    "DEBUG":    "⚪",
}


def render():
    st.title("📄 Live Logs")
    st.caption("Real-time operational log viewer for the Agentic ITSM platform.")

    col1, col2, col3 = st.columns(3)
    log_type = col1.selectbox("Log Stream", ["workflow", "incidents", "notifications"])
    lines    = col2.slider("Lines", min_value=20, max_value=500, value=100, step=20)
    filter_level = col3.selectbox("Min Level", ["ALL", "INFO", "WARNING", "ERROR"])

    auto_refresh = st.checkbox("Auto-refresh every 10s", value=False)
    if auto_refresh:
        import time
        st.empty()
        time.sleep(10)
        st.rerun()

    entries = read_log_file(log_type=log_type, lines=lines)

    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    min_level   = level_order.get(filter_level, 0)

    filtered = [
        e for e in entries
        if level_order.get(e.get("level", "INFO").upper(), 1) >= min_level
    ] if filter_level != "ALL" else entries

    st.markdown(f"**{len(filtered)} log entries** (filtered from {len(entries)} total)")
    st.divider()

    # Show newest first
    for entry in reversed(filtered):
        level  = (entry.get("level") or "INFO").upper()
        icon   = _LEVEL_COLOUR.get(level, "⚪")
        ts     = (entry.get("timestamp") or "")[:19].replace("T", " ")
        msg    = entry.get("message") or ""
        event  = entry.get("event") or ""
        agent  = entry.get("agent") or ""

        # Build structured display
        title = event or msg
        extra_parts = []
        if agent:
            extra_parts.append(f"agent=`{agent}`")
        for k, v in entry.items():
            if k not in ("timestamp", "level", "logger", "message", "event", "agent"):
                extra_parts.append(f"{k}=`{v}`")

        extra = "  ·  ".join(extra_parts[:5])  # cap displayed fields

        st.markdown(
            f"{icon} `{ts}` **{level}** — {title}  \n"
            f"<small style='color:#888;'>{extra}</small>",
            unsafe_allow_html=True,
        )
