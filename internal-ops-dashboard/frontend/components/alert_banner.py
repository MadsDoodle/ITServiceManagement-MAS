import streamlit as st


def render_alert_banner(incidents: list):
    critical = [i for i in incidents if i["severity"] == "critical" and i["status"] != "resolved"]
    high = [i for i in incidents if i["severity"] == "high" and i["status"] != "resolved"]

    if critical:
        st.error(f"🔴 **CRITICAL:** {len(critical)} critical incident(s) require immediate attention")
        for inc in critical:
            st.error(f"  ↳ `{inc['affected_service']}` — {inc['title']}")

    if high:
        st.warning(f"🟠 **HIGH:** {len(high)} high-severity incident(s) under investigation")
        for inc in high:
            st.warning(f"  ↳ `{inc['affected_service']}` — {inc['title']}")