import streamlit as st

from frontend.services.api_client import create_deployment, get_deployments
from frontend.utils.formatting import format_status, format_timestamp


def render():
    st.title("🚀 Deployment Tracker")
    tab1, tab2 = st.tabs(["Deployment History", "Trigger Deployment"])

    with tab1:
        data = get_deployments()
        if "error" in data:
            st.error(f"Failed to load deployments: {data['error']}")
            return

        deployments = data.get("deployments", [])
        st.caption(f"{len(deployments)} deployment(s) shown")

        for dep in deployments:
            icon = {"success": "🟢", "failed": "🔴", "rolled_back": "🟠", "pending": "⚪"}.get(dep["status"], "⚫")
            with st.expander(f"{icon} {dep['deployment_id']} — {dep['version']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Status:** {format_status(dep['status'])}")
                c2.write(f"**Version:** `{dep['version']}`")
                c3.write(f"**By:** {dep['deployed_by']}")

                st.write(f"**Commit:** `{dep['commit_ref']}`")
                st.write(f"**Time:** {format_timestamp(dep['timestamp'])}")
                if dep.get("duration_seconds"):
                    st.write(f"**Duration:** {dep['duration_seconds']}s")
                if dep.get("notes"):
                    fn = st.error if dep["status"] in ("failed", "rolled_back") else st.info
                    fn(dep["notes"])

    with tab2:
        st.subheader("Trigger New Deployment")
        st.warning("⚠️ Creates a live deployment record. Use for ITSM testing only.")
        with st.form("new_deployment"):
            version = st.text_input("Version", placeholder="e.g. v1.4.0")
            commit_ref = st.text_input("Commit Ref", placeholder="e.g. abc1234")
            deployed_by = st.text_input("Deployed By", value="ci-bot")
            notes = st.text_area("Notes")

            if st.form_submit_button("Trigger Deployment"):
                if not version or not commit_ref:
                    st.error("Version and commit ref are required.")
                else:
                    r = create_deployment(version, commit_ref, deployed_by=deployed_by, notes=notes or None)
                    if "error" in r:
                        st.error(r["error"])
                    else:
                        st.success(f"Deployment `{r['deployment_id']}` created — status: {r['status']}")
                        st.rerun()