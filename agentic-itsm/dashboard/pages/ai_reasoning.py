"""
AI Decision Trace — shows why the AI made each decision for a selected incident.
Displays: classification reasoning, RCA, escalation reasons, remediation choice, risk score.
"""
from __future__ import annotations

import json
import streamlit as st

from dashboard.services.dashboard_api import get_all_incidents, get_workflow_run
from dashboard.components.timeline import render_timeline


def render():
    st.title("🧠 AI Reasoning")
    st.caption("Inspect the AI's decision-making for any incident in the system.")

    incidents = get_all_incidents(limit=100)
    if not incidents:
        st.info("No incidents recorded yet.")
        return

    options = {
        f"{i.get('incident_id')} — {i.get('severity','?')} — {(i.get('created_at') or '')[:16]}": i.get("incident_id")
        for i in incidents
    }
    selected_label = st.selectbox("Select Incident", list(options.keys()))
    selected_id    = options[selected_label]

    inc = get_workflow_run(selected_id)
    if not inc:
        st.error("Could not load incident details.")
        return

    state = inc.get("state") or {}
    trace = state.get("trace") or []

    # ── Overview strip ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Severity",    inc.get("severity") or "?")
    c2.metric("Risk Score",  f"{inc.get('risk_score', 0.0) or 0.0:.2f}")
    c3.metric("Confidence",  f"{inc.get('ai_confidence', 0.0) or 0.0:.0%}")
    c4.metric("Stage",       (inc.get("lifecycle_stage") or "?").replace("_", " ").title())
    st.divider()

    # ── Classification ────────────────────────────────────────────────────────
    st.subheader("🏷️ Classification")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Type:** {state.get('incident_type') or 'N/A'}")
    c2.markdown(f"**Severity:** {state.get('severity') or 'N/A'}")
    if state.get("classification_reasoning"):
        st.info(state["classification_reasoning"])

    # ── Risk scoring ──────────────────────────────────────────────────────────
    st.subheader("📊 Risk Scoring")
    risk = state.get("risk_score", 0.0) or 0.0
    st.progress(min(risk, 1.0), text=f"Risk Score: {risk:.2f} / 1.00")
    strategy = state.get("remediation_strategy") or "none"
    st.markdown(f"**Chosen Remediation Strategy:** `{strategy}`")
    if risk > 0.6:
        st.warning("⚠️ High risk — human escalation required before remediation")
    else:
        st.success("✅ Risk within auto-remediation threshold")

    # ── Escalation ────────────────────────────────────────────────────────────
    st.subheader("⚠️ Escalation Decision")
    esc_reasons = state.get("escalation_reasons") or []
    if esc_reasons:
        st.error(f"Escalation triggered — {len(esc_reasons)} rule(s) matched")
        for r in esc_reasons:
            st.markdown(f"- {r}")
    else:
        st.success("No escalation triggered")

    # ── RCA ───────────────────────────────────────────────────────────────────
    st.subheader("🔍 Root Cause Analysis")
    rca = state.get("root_cause_summary") or "_Not available_"
    st.markdown(rca)

    corr = state.get("correlated_deployment")
    if corr:
        st.markdown("**Correlated Deployment:**")
        st.json(corr)
    if state.get("rca_reasoning"):
        with st.expander("AI Reasoning Detail"):
            st.text(state["rca_reasoning"])

    # ── Remediation ───────────────────────────────────────────────────────────
    st.subheader("🔧 Remediation")
    rem_detail = state.get("remediation_detail") or "_Not attempted_"
    if state.get("remediation_succeeded"):
        st.success(rem_detail)
    elif state.get("remediation_attempted"):
        st.error(rem_detail)
    else:
        st.info(rem_detail)

    # ── Execution timeline ────────────────────────────────────────────────────
    st.divider()
    st.subheader("⏱️ Execution Timeline")
    render_timeline(trace)

    # ── Raw state ─────────────────────────────────────────────────────────────
    with st.expander("🔎 Raw State JSON", expanded=False):
        display = {k: v for k, v in state.items() if k not in ("trace", "raw_logs")}
        st.json(display)
