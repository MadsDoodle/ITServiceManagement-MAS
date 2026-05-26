"""
Incident Correlation View — shows incident relationship graph.
Groups incidents by root cause deployment or service cascade.
"""
from __future__ import annotations

import streamlit as st

from state.persistent_store import get_all_incidents

_SEV_COLOURS = {
    "P1": "#d73a4a", "P2": "#f0883e",
    "P3": "#0075ca", "Low": "#888",
}
_STAGE_ICONS = {
    "new": "🆕", "triage": "🏷️", "investigating": "🔍",
    "fix_in_progress": "🔧", "awaiting_review": "⏳",
    "monitoring": "📡", "resolved": "✅",
}


def render():
    st.title("🔗 Incident Correlation")
    st.caption(
        "Incidents linked by shared deployment commit refs, affected services, or overlapping anomaly patterns."
    )

    incidents = get_all_incidents(limit=500)
    if not incidents:
        st.info("No incidents to correlate yet.")
        return

    # ── Build correlation groups from stored state ────────────────────────────
    groups: dict[str, list[dict]] = {}  # root_cause_id / commit_ref → incidents
    standalone: list[dict] = []

    for inc in incidents:
        state = inc.get("state") or {}
        root  = state.get("root_cause_incident_id")
        corr  = state.get("correlated_deployment") or {}
        commit = corr.get("commit_ref")

        if root:
            groups.setdefault(f"root:{root}", []).append(inc)
        elif commit:
            groups.setdefault(f"commit:{commit}", []).append(inc)
        else:
            standalone.append(inc)

    # ── Summary strip ─────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Correlation Groups", len(groups))
    c2.metric("Correlated Incidents", sum(len(v) for v in groups.values()))
    c3.metric("Standalone Incidents", len(standalone))
    st.divider()

    # ── Render groups ─────────────────────────────────────────────────────────
    if groups:
        st.subheader("Correlated Groups")
        for group_key, group_incidents in sorted(groups.items()):
            label = group_key.replace("root:", "Root: ").replace("commit:", "Commit: ")
            with st.expander(f"🔗 {label} — {len(group_incidents)} incident(s)", expanded=True):
                for inc in group_incidents:
                    _render_compact_card(inc)

    # ── Standalone ────────────────────────────────────────────────────────────
    if standalone:
        st.divider()
        st.subheader("Standalone Incidents (No Correlations)")
        for inc in standalone[:20]:
            _render_compact_card(inc)
        if len(standalone) > 20:
            st.caption(f"... and {len(standalone) - 20} more")

    # ── Commit-ref index ──────────────────────────────────────────────────────
    st.divider()
    with st.expander("📑 Commit Ref Index"):
        commit_map: dict[str, list[str]] = {}
        for inc in incidents:
            state = inc.get("state") or {}
            corr  = (state.get("correlated_deployment") or {})
            ref   = corr.get("commit_ref")
            if ref:
                commit_map.setdefault(ref, []).append(inc.get("incident_id", "N/A"))
        if commit_map:
            for ref, ids in commit_map.items():
                st.markdown(f"`{ref}` → {', '.join(f'`{i}`' for i in ids)}")
        else:
            st.info("No commit refs recorded yet.")


def _render_compact_card(inc: dict):
    iid   = inc.get("incident_id", "N/A")
    sev   = inc.get("severity") or "?"
    itype = inc.get("incident_type") or "Unknown"
    stage = inc.get("lifecycle_stage") or "unknown"
    ts    = (inc.get("created_at") or "")[:16].replace("T", " ")
    colour = _SEV_COLOURS.get(sev, "#888")
    stage_icon = _STAGE_ICONS.get(stage, "⚙️")

    st.markdown(
        f'<div style="border-left:3px solid {colour};padding:6px 12px;'
        f'background:#1a1a2e;border-radius:3px;margin-bottom:4px;">'
        f'<code style="font-size:0.8em;">{iid}</code>'
        f' &nbsp; <b style="color:{colour};">[{sev}]</b> {itype}'
        f' &nbsp; {stage_icon} <small>{stage}</small>'
        f' &nbsp; <small style="color:#888;">{ts}</small>'
        f'</div>',
        unsafe_allow_html=True,
    )
