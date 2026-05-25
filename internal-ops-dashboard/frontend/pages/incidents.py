import streamlit as st

from services.api_client import create_incident, get_incidents, update_incident
from utils.formatting import format_severity, format_status, format_timestamp


def render():
    st.title("🚨 Incident Management")
    tab1, tab2 = st.tabs(["Incident List", "Create Incident"])

    with tab1:
        c1, c2 = st.columns(2)
        status_f = c1.selectbox("Status", ["all", "open", "investigating", "resolved"])
        sev_f = c2.selectbox("Severity", ["all", "critical", "high", "medium", "low"])

        data = get_incidents(
            status=None if status_f == "all" else status_f,
            severity=None if sev_f == "all" else sev_f,
        )

        if "error" in data:
            st.error(f"Failed to load incidents: {data['error']}")
            return

        incidents = data.get("incidents", [])
        st.caption(f"{len(incidents)} incident(s) shown")

        for inc in incidents:
            s_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(inc["severity"], "⚫")
            with st.expander(f"{s_icon} #{inc['id']} — {inc['title']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Severity:** {format_severity(inc['severity'])}")
                c2.write(f"**Status:** {format_status(inc['status'])}")
                c3.write(f"**Service:** `{inc['affected_service']}`")

                st.write(f"**Opened:** {format_timestamp(inc['timestamp'])}")
                if inc.get("resolved_at"):
                    st.write(f"**Resolved:** {format_timestamp(inc['resolved_at'])}")
                if inc.get("commit_ref"):
                    st.write(f"**Commit Ref:** `{inc['commit_ref']}`")
                if inc.get("notes"):
                    st.info(inc["notes"])

                if inc["status"] != "resolved":
                    st.markdown("---")
                    new_status = st.selectbox(
                        "Update Status",
                        ["open", "investigating", "resolved"],
                        index=["open", "investigating", "resolved"].index(inc["status"]),
                        key=f"sel_{inc['id']}",
                    )
                    note_input = st.text_area("Add Note", key=f"note_{inc['id']}")
                    if st.button("Update", key=f"upd_{inc['id']}"):
                        result = update_incident(inc["id"], status=new_status, notes=note_input or None)
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success("Updated.")
                            st.rerun()

    with tab2:
        st.subheader("Create New Incident")
        with st.form("new_incident"):
            title = st.text_input("Title", placeholder="e.g. Auth service returning 500 errors")
            c1, c2 = st.columns(2)
            severity = c1.selectbox("Severity", ["critical", "high", "medium", "low"])
            service = c2.text_input("Affected Service", placeholder="e.g. auth-service")
            notes = st.text_area("Notes", placeholder="Describe the issue...")
            commit_ref = st.text_input("Commit Ref (optional)", placeholder="e.g. abc1234")

            if st.form_submit_button("Create Incident"):
                if not title or not service:
                    st.error("Title and affected service are required.")
                else:
                    r = create_incident(title, severity, service, notes=notes or None, commit_ref=commit_ref or None)
                    if "error" in r:
                        st.error(r["error"])
                    else:
                        st.success(f"Incident #{r['id']} created.")
                        st.rerun()