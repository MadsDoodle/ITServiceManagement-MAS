import streamlit as st

_LEVEL_COLOR = {"ERROR": "error", "CRITICAL": "error", "WARNING": "warning", "WARN": "warning"}
_LEVEL_ICON = {"ERROR": "🔴", "CRITICAL": "🔴", "WARNING": "🟡", "WARN": "🟡", "INFO": "🟢", "DEBUG": "⚪"}


def render_log_viewer(entries: list):
    if not entries:
        st.info("No log entries to display.")
        return

    for entry in entries:
        if "raw" in entry:
            st.code(entry["raw"], language="text")
            continue

        level = entry.get("level", "INFO")
        icon = _LEVEL_ICON.get(level, "⚫")
        ts = entry.get("timestamp", "")
        name = entry.get("logger", "")
        msg = entry.get("message", "")
        line = f"{icon} `{ts}` **[{name}]** {msg}"

        color = _LEVEL_COLOR.get(level)
        if color == "error":
            st.error(line)
        elif color == "warning":
            st.warning(line)
        else:
            st.markdown(line)