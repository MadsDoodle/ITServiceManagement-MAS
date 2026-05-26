"""
Live Logs — structured, colour-coded log viewer with incident grouping,
workflow lifecycle banners, and human-readable + expandable JSON.
"""
from __future__ import annotations

import json
import streamlit as st

from services.log_service import read_log_file

# ── Colours & icons per event category ───────────────────────────────────────
_LEVEL_STYLE = {
    "CRITICAL": {"bg": "#5c0a0a", "border": "#d73a4a", "badge": "#d73a4a", "label": "CRITICAL"},
    "ERROR":    {"bg": "#3d1010", "border": "#d73a4a", "badge": "#d73a4a", "label": "ERROR"},
    "WARNING":  {"bg": "#3d2f00", "border": "#e4c000", "badge": "#e4c000", "label": "WARNING"},
    "INFO":     {"bg": "#0d1a2e", "border": "#1f6feb", "badge": "#1f6feb", "label": "INFO"},
    "DEBUG":    {"bg": "#1a1a1a", "border": "#444",    "badge": "#666",    "label": "DEBUG"},
}

# Landmark events get prominent full-width banners
_BANNER_EVENTS = {
    "workflow_start":       {"colour": "#0075ca", "icon": "🚀", "label": "WORKFLOW START"},
    "workflow_end":         {"colour": "#2da44e", "icon": "✅", "label": "WORKFLOW COMPLETE"},
    "workflow_cycle_start": {"colour": "#0d7377", "icon": "🔄", "label": "CYCLE START"},
    "new_incident_triggered": {"colour": "#8957e5", "icon": "⚡", "label": "INCIDENT TRIGGERED"},
    "monitoring_loop_started": {"colour": "#0d7377", "icon": "▶️", "label": "LOOP STARTED"},
    "monitoring_loop_stopped": {"colour": "#555",   "icon": "⏹️", "label": "LOOP STOPPED"},
    "agent_start":          {"colour": "#1f3a5f", "icon": "▸",  "label": None},   # label built from agent name
    "agent_complete":       {"colour": "#1a3d2e", "icon": "✓",  "label": None},
    "detection_tick_failed": {"colour": "#5c0a0a", "icon": "💥", "label": "DETECTION FAILED"},
    "escalation_evaluated": {"colour": "#5c3300", "icon": "⚠️", "label": "ESCALATION"},
    "github_issue_created": {"colour": "#1a3d2e", "icon": "🐙", "label": "GITHUB ISSUE CREATED"},
    "remediation_start":    {"colour": "#3d1a5c", "icon": "🔧", "label": "REMEDIATION START"},
    "remediation_success":  {"colour": "#1a3d2e", "icon": "🔧", "label": "REMEDIATION SUCCESS"},
    "remediation_failed":   {"colour": "#5c0a0a", "icon": "🔧", "label": "REMEDIATION FAILED"},
    "failure_injected":     {"colour": "#5c2000", "icon": "💉", "label": "FAILURE INJECTED"},
    "recovery_check":       {"colour": "#0d3d3d", "icon": "📡", "label": "RECOVERY CHECK"},
    "incident_resolved":    {"colour": "#2da44e", "icon": "🏁", "label": "INCIDENT RESOLVED"},
    "llm_call_complete":    {"colour": "#1a1a3d", "icon": "🤖", "label": "LLM CALL"},
    "llm_classify_fallback": {"colour": "#3d2f00", "icon": "⚠️", "label": "LLM FALLBACK"},
    "llm_rca_fallback":     {"colour": "#3d2f00", "icon": "⚠️", "label": "LLM FALLBACK"},
    "watchdog_started":     {"colour": "#1a2f3d", "icon": "🐕", "label": "WATCHDOG START"},
    "watchdog_loop_stalled": {"colour": "#5c0a0a", "icon": "🐕", "label": "WATCHDOG: LOOP STALLED"},
    "human_review_required": {"colour": "#5c3300", "icon": "👤", "label": "HUMAN REVIEW NEEDED"},
}

# Fields to always hide from the detail display (noisy / redundant)
_SKIP_FIELDS = {"timestamp", "level", "logger", "message", "event"}

# Agent colour map
_AGENT_COLOURS = {
    "MonitoringAgent":         "#0d7377",
    "ClassificationAgent":     "#8957e5",
    "RCAAgent":                "#d29922",
    "RiskScoringAgent":        "#1f6feb",
    "EscalationAgent":         "#bc4c00",
    "GitHubAgent":             "#2da44e",
    "HumanReviewAgent":        "#d73a4a",
    "RemediationAgent":        "#6f42c1",
    "RecoveryValidationAgent": "#0d7377",
    "ResolutionAgent":         "#2da44e",
    "NotificationAgent":       "#1f6feb",
}


def render():
    st.title("📄 Live Logs")
    st.caption("Structured, colour-coded workflow log viewer with incident grouping and readable output.")

    # ── Controls ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    log_type   = c1.selectbox("Log Stream", ["workflow", "incidents", "notifications"])
    lines      = c2.slider("Lines", 20, 500, 150, 20)
    min_level  = c3.selectbox("Min Level", ["ALL", "INFO", "WARNING", "ERROR"])
    view_mode  = c4.selectbox("View Mode", ["Timeline", "Grouped by Incident", "Errors Only"])

    col_filter, col_auto = st.columns([3, 1])
    event_search = col_filter.text_input("Filter by event / agent / text", placeholder="e.g. agent_complete, GitHub, INC-")
    auto_refresh = col_auto.checkbox("Auto-refresh 10s", value=False)
    if auto_refresh:
        import time; time.sleep(10); st.rerun()

    # ── Load & filter ─────────────────────────────────────────────────────────
    entries = read_log_file(log_type=log_type, lines=lines)
    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}

    if min_level != "ALL":
        min_v    = level_order.get(min_level, 0)
        entries  = [e for e in entries
                    if level_order.get((e.get("level") or "INFO").upper(), 1) >= min_v]

    if view_mode == "Errors Only":
        entries = [e for e in entries
                   if (e.get("level") or "").upper() in ("ERROR", "CRITICAL")]

    if event_search:
        q = event_search.lower()
        entries = [
            e for e in entries
            if q in json.dumps(e, default=str).lower()
        ]

    # ── Stats strip ───────────────────────────────────────────────────────────
    total    = len(entries)
    errors   = sum(1 for e in entries if (e.get("level") or "").upper() in ("ERROR", "CRITICAL"))
    warnings = sum(1 for e in entries if (e.get("level") or "").upper() == "WARNING")
    wf_starts = sum(1 for e in entries if e.get("event") == "workflow_start")

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Entries", total)
    mc2.metric("🔴 Errors", errors)
    mc3.metric("🟡 Warnings", warnings)
    mc4.metric("🚀 Workflows", wf_starts)

    st.divider()

    if not entries:
        st.info("No log entries match the current filters.")
        return

    # ── Render ────────────────────────────────────────────────────────────────
    if view_mode == "Grouped by Incident":
        _render_grouped(entries)
    else:
        _render_timeline(list(reversed(entries)))   # newest first


# ── Timeline renderer ─────────────────────────────────────────────────────────

def _render_timeline(entries: list[dict]):
    for entry in entries:
        event = entry.get("event") or entry.get("message") or ""
        level = (entry.get("level") or "INFO").upper()

        # Landmark banner events
        if event in _BANNER_EVENTS:
            _render_banner(entry)
        else:
            _render_row(entry)


def _render_banner(entry: dict):
    event  = entry.get("event") or ""
    level  = (entry.get("level") or "INFO").upper()
    meta   = _BANNER_EVENTS.get(event, {})
    colour = meta.get("colour", "#333")
    icon   = meta.get("icon", "•")
    label  = meta.get("label")
    ts     = (entry.get("timestamp") or "")[:19].replace("T", " ")
    agent  = entry.get("agent") or ""

    # Build the display label
    if label is None:
        # agent_start / agent_complete — use agent name
        agent_colour = _AGENT_COLOURS.get(agent, "#888")
        action       = "starting" if event == "agent_start" else "done"
        label_html   = (
            f'<span style="color:{agent_colour};font-weight:bold;">{agent}</span>'
            f' <span style="color:#888;font-size:0.85em;">{action}</span>'
        )
    else:
        label_html = f'<span style="font-weight:bold;color:white;">{label}</span>'

    # Extra fields
    extras = _build_extras(entry, exclude={"agent"} | _SKIP_FIELDS)

    # Error level override
    if level in ("ERROR", "CRITICAL"):
        colour = "#d73a4a"

    incident_id = entry.get("incident_id") or ""
    iid_badge = (
        f'<span style="background:#1f3a5f;color:#79c0ff;padding:1px 6px;'
        f'border-radius:8px;font-size:0.78em;margin-left:6px;">{incident_id}</span>'
        if incident_id else ""
    )

    with st.container():
        st.markdown(
            f"""<div style="border-left:4px solid {colour};background:{colour}22;
                padding:8px 12px;border-radius:4px;margin-bottom:3px;">
              <span style="font-size:1.1em;">{icon}</span>
              &nbsp;{label_html}{iid_badge}
              &nbsp;&nbsp;<span style="color:#666;font-size:0.8em;">{ts}</span>
              {f'<div style="margin-top:4px;"><small style="color:#aaa;">{extras}</small></div>' if extras else ''}
            </div>""",
            unsafe_allow_html=True,
        )


def _render_row(entry: dict):
    level   = (entry.get("level") or "INFO").upper()
    style   = _LEVEL_STYLE.get(level, _LEVEL_STYLE["INFO"])
    ts      = (entry.get("timestamp") or "")[:19].replace("T", " ")
    event   = entry.get("event") or entry.get("message") or "(no event)"
    agent   = entry.get("agent") or ""
    extras  = _build_extras(entry, exclude={"agent"} | _SKIP_FIELDS)

    agent_html = ""
    if agent:
        ac = _AGENT_COLOURS.get(agent, "#888")
        agent_html = f'<span style="color:{ac};font-weight:bold;margin-right:6px;">[{agent}]</span>'

    badge_html = (
        f'<span style="background:{style["badge"]}22;color:{style["badge"]};'
        f'padding:0 5px;border-radius:3px;font-size:0.78em;font-weight:bold;">'
        f'{style["label"]}</span>'
    )

    # Raw JSON expander
    raw_json = {k: v for k, v in entry.items() if k not in _SKIP_FIELDS}

    col_main, col_json = st.columns([10, 1])
    with col_main:
        st.markdown(
            f"""<div style="border-left:3px solid {style['border']};background:{style['bg']};
                padding:5px 10px;border-radius:3px;margin-bottom:2px;">
              {badge_html} {agent_html}
              <span style="color:#e6edf3;">{event}</span>
              &nbsp;&nbsp;<span style="color:#555;font-size:0.78em;">{ts}</span>
              {f'<br/><small style="color:#888;">{extras}</small>' if extras else ''}
            </div>""",
            unsafe_allow_html=True,
        )
    with col_json:
        if raw_json:
            with st.expander("{}"):
                st.json(raw_json)


# ── Grouped by incident renderer ──────────────────────────────────────────────

def _render_grouped(entries: list[dict]):
    """Group log entries by incident_id and render each group as a collapsible block."""
    groups: dict[str, list[dict]] = {}
    ungrouped: list[dict] = []

    for entry in entries:
        iid = entry.get("incident_id") or entry.get("workflow_run_id")
        if iid:
            groups.setdefault(iid, []).append(entry)
        else:
            ungrouped.append(entry)

    if ungrouped:
        with st.expander(f"🌐 System / No Incident ({len(ungrouped)} entries)", expanded=False):
            for e in reversed(ungrouped[-30:]):
                _render_row(e)

    for iid, group in sorted(groups.items(), key=lambda x: x[1][-1].get("timestamp", ""), reverse=True):
        # Summarise the group
        has_error  = any((e.get("level") or "").upper() in ("ERROR", "CRITICAL") for e in group)
        has_github = any(e.get("event") == "github_issue_created" for e in group)
        gh_num     = next((e.get("number") for e in group if e.get("event") == "github_issue_created"), None)
        completed  = any(e.get("event") == "workflow_end" for e in group)
        sev        = next((e.get("severity") for e in group if e.get("severity")), None)
        ts_first   = (group[0].get("timestamp") or "")[:16].replace("T", " ")

        header_colour = "#d73a4a" if has_error else ("#2da44e" if completed else "#1f6feb")
        status_icon   = "❌" if has_error else ("✅" if completed else "🔄")
        gh_badge      = f" 🐙 #{gh_num}" if gh_num else ""
        sev_badge     = f" [{sev}]" if sev else ""

        with st.expander(
            f"{status_icon} `{iid}`{sev_badge}{gh_badge}  ·  {ts_first}  ·  {len(group)} events",
            expanded=has_error,
        ):
            # Mini timeline inside the group
            for e in group:
                event = e.get("event") or e.get("message") or ""
                if event in _BANNER_EVENTS:
                    _render_banner(e)
                else:
                    _render_row(e)


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_extras(entry: dict, exclude: set) -> str:
    """Build a readable extras string from non-standard fields."""
    parts = []
    for k, v in entry.items():
        if k in exclude:
            continue
        if isinstance(v, str) and len(v) > 120:
            v = v[:117] + "..."
        if isinstance(v, list) and len(v) > 5:
            v = v[:5] + ["..."]
        parts.append(f"<b>{k}</b>: {v}")
    return "  ·  ".join(parts[:8])
