"""
Incident Injection Console — three-tier incident launcher.

LOW    → auto-resolved quickly, no human needed, fast recovery
MEDIUM → LLM investigates, auto-remediated, standard stability window
HIGH   → escalated, requires human approval before remediation proceeds

One active incident at a time. Inject buttons disabled while an incident
is in-flight. The monitoring loop drives the workflow forward in the background.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import streamlit as st

from state.incident_state import new_state
from state.persistent_store import get_open_incidents, init_db
from integrations.internal_ops.simulation_client import (
    inject_by_type,
    restore_service_healthy,
    _set_service_status,
)
from utils.constants import (
    FAILURE_AUTH_FAILURE,
    FAILURE_LATENCY_SPIKE,
    FAILURE_SERVICE_DEGRADED,
    FAILURE_SERVICE_DOWN,
    FAILURE_DEPLOY_FAILURE,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_DOWN,
)

# ── Tier definitions ──────────────────────────────────────────────────────────
_TIERS = {
    "low": {
        "label":       "🟢 Low — Quick Auto-Fix",
        "colour":      "#2da44e",
        "bg":          "#0d2b18",
        "description": "Minor service hiccup. LLM classifies quickly, remediation runs automatically, resolved in one stability check.",
        "scenarios": [
            {
                "label":       "Notification Queue Backlog",
                "description": "Marks notification-service degraded. Low anomaly count → low risk → instant auto-remediation.",
                "service":     "notification-service",
                "severity":    HEALTH_STATUS_DEGRADED,
                "anomaly_type": "service_degraded",
                "anomaly_hint": "P3",
            },
            {
                "label":       "Metrics Collector Hiccup",
                "description": "Marks metrics-collector degraded. Single anomaly → low risk → fast resolve.",
                "service":     "metrics-collector",
                "severity":    HEALTH_STATUS_DEGRADED,
                "anomaly_type": "service_degraded",
                "anomaly_hint": "P3",
            },
        ],
        "force_human_review": False,
        "fast_recovery":      True,
    },
    "medium": {
        "label":       "🟡 Medium — LLM Investigation",
        "colour":      "#e4c000",
        "bg":          "#2b2200",
        "description": "Service degradation. LLM runs full RCA + classification, auto-remediation executes, standard 60s stability window.",
        "scenarios": [
            {
                "label":       "Auth Service Latency Spike",
                "description": "Marks auth-service degraded. Triggers latency + service anomalies → medium risk → restart strategy.",
                "service":     "auth-service",
                "severity":    HEALTH_STATUS_DEGRADED,
                "anomaly_type": "service_degraded",
                "anomaly_hint": "P2",
            },
            {
                "label":       "API Gateway Degraded",
                "description": "Marks api-gateway degraded. LLM correlates with deployment history → latency remediation.",
                "service":     "api-gateway",
                "severity":    HEALTH_STATUS_DEGRADED,
                "anomaly_type": "service_degraded",
                "anomaly_hint": "P2",
            },
        ],
        "force_human_review": False,
        "fast_recovery":      False,
    },
    "high": {
        "label":       "🔴 High — Human Approval Required",
        "colour":      "#d73a4a",
        "bg":          "#2b0a0a",
        "description": "Critical outage. LLM investigates, workflow pauses at Human Review Queue. You must approve before remediation runs.",
        "scenarios": [
            {
                "label":       "Auth Service Full Outage",
                "description": "Marks auth-service DOWN. P1 anomaly → critical risk → escalation → human review required.",
                "service":     "auth-service",
                "severity":    HEALTH_STATUS_DOWN,
                "anomaly_type": "service_down",
                "anomaly_hint": "P1",
            },
            {
                "label":       "Database Connection Failure",
                "description": "Marks database DOWN. Critical service + P1 → always escalated → human review required.",
                "service":     "database",
                "severity":    HEALTH_STATUS_DOWN,
                "anomaly_type": "service_down",
                "anomaly_hint": "P1",
            },
        ],
        "force_human_review": True,
        "fast_recovery":      False,
    },
}


def _has_active_incident() -> bool:
    """Returns True if any non-resolved incident is currently in flight."""
    try:
        init_db()
        from state.persistent_store import any_workflow_locked
        # Primary: DB lock (cross-process safe)
        if any_workflow_locked():
            return True
        # Secondary: open incident in DB
        return len(get_open_incidents()) > 0
    except Exception:
        return False


def _get_active_incident() -> dict | None:
    try:
        init_db()
        open_incs = get_open_incidents()
        return open_incs[0] if open_incs else None
    except Exception:
        return None


def _build_preset_state(scenario: dict, tier: dict, tier_key: str) -> dict:
    """Build a pre-populated IncidentState for direct workflow launch."""
    incident_id     = f"INC-{uuid.uuid4().hex[:8].upper()}"
    workflow_run_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    created_at      = datetime.now(timezone.utc).isoformat()

    svc  = scenario["service"]
    atype = scenario["anomaly_type"]
    hint  = scenario["anomaly_hint"]

    anomaly = {
        "type":             atype,
        "description":      f"Service '{svc}' is {scenario['severity'].upper()} — injected via dashboard",
        "affected_service": svc,
        "severity_hint":    hint,
        "evidence":         {"service": svc, "status": scenario["severity"], "injected": True},
    }

    state = new_state(incident_id, workflow_run_id, created_at)
    state["anomalies"]                = [anomaly]
    state["pre_populated_anomalies"]  = True
    state["force_human_review"]       = tier["force_human_review"]
    state["fast_recovery"]            = tier["fast_recovery"]
    state["lifecycle_stage"]          = "new"
    return state


def render():
    st.title("💥 Incident Injection Console")
    st.caption(
        "Launch incidents directly from the dashboard — three tiers from quick auto-fix "
        "to human-approval-required. One active incident at a time."
    )

    # ── Loop status ───────────────────────────────────────────────────────────
    _render_loop_status()
    st.divider()

    # ── Active incident lock ──────────────────────────────────────────────────
    active = _get_active_incident()
    blocked = active is not None

    if blocked:
        iid   = active.get("incident_id", "?")
        stage = (active.get("lifecycle_stage") or "unknown").replace("_", " ").title()
        sev   = active.get("severity") or "?"
        url   = active.get("github_issue_url") or ""

        _STAGE_COLOURS = {
            "new": "#0075ca", "triage": "#e4c000", "investigating": "#f0883e",
            "fix_in_progress": "#8957e5", "awaiting_review": "#d73a4a",
            "monitoring": "#0d7377", "resolved": "#2da44e",
        }
        raw_stage = active.get("lifecycle_stage") or "unknown"
        sc = _STAGE_COLOURS.get(raw_stage, "#888")

        st.markdown(
            f"""<div style="border:2px solid {sc};background:{sc}22;padding:14px 16px;
                border-radius:8px;margin-bottom:12px;">
              <b style="font-size:1.1em;">Active incident in progress</b><br/>
              <code>{iid}</code> &nbsp;·&nbsp;
              <b style="color:{sc};">{stage}</b> &nbsp;·&nbsp; severity {sev}
              {"&nbsp;·&nbsp;<a href='" + url + "' target='_blank'>GitHub →</a>" if url else ""}
              <br/><small style="color:#aaa;">
              Injection is disabled until this incident resolves.
              {'<b style="color:#d73a4a;">  ⏳ Awaiting your approval in Human Review Queue.</b>'
               if raw_stage == "awaiting_review" else ""}
              </small>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Tier cards ────────────────────────────────────────────────────────────
    for tier_key, tier in _TIERS.items():
        colour = tier["colour"]
        bg     = tier["bg"]

        st.markdown(
            f"""<div style="border-left:5px solid {colour};background:{bg};
                padding:12px 16px;border-radius:6px;margin-bottom:6px;">
              <span style="font-size:1.15em;font-weight:bold;color:{colour};">
                {tier['label']}
              </span><br/>
              <small style="color:#ccc;">{tier['description']}</small>
            </div>""",
            unsafe_allow_html=True,
        )

        scen_cols = st.columns(len(tier["scenarios"]))
        for col, scenario in zip(scen_cols, tier["scenarios"]):
            with col:
                st.markdown(
                    f"<div style='background:#111;border:1px solid #333;padding:8px 10px;"
                    f"border-radius:5px;min-height:70px;'>"
                    f"<b>{scenario['label']}</b><br/>"
                    f"<small style='color:#999;'>{scenario['description']}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                btn_key = f"inject_{tier_key}_{scenario['service']}"
                if st.button(
                    f"{'🔒 Blocked' if blocked else 'Launch →'}",
                    key=btn_key,
                    disabled=blocked,
                    type="primary" if not blocked else "secondary",
                    use_container_width=True,
                ):
                    _launch_incident(scenario, tier, tier_key)

        st.markdown("<br/>", unsafe_allow_html=True)

    # ── Manual recovery ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🟢 Manual Service Recovery")
    st.caption("Restore a service to healthy — use this if an incident gets stuck or you want to reset.")
    svc_cols = st.columns(5)
    services = ["auth-service", "api-gateway", "notification-service", "database", "metrics-collector"]
    for col, svc in zip(svc_cols, services):
        with col:
            if st.button(f"Restore\n{svc.split('-')[0]}", key=f"restore_{svc}", use_container_width=True):
                result = restore_service_healthy(svc)
                if result.get("success"):
                    st.success(f"✅ {svc}")
                else:
                    st.error(f"❌ {result.get('error')}")

    # ── Current service status ────────────────────────────────────────────────
    st.divider()
    st.markdown("### Current Service State")
    _render_service_status()

    # ── What the loop actually does ───────────────────────────────────────────
    st.divider()
    with st.expander("ℹ️  What does `python app.py --loop` do?", expanded=False):
        st.markdown("""
`python app.py --loop` runs the **background orchestration engine**. It does NOT inject incidents.

What it actually does every 30 seconds:
- Polls the ops dashboard and logs the current anomaly state (for observability)
- Checks all open incidents in the database:
  - Incidents in `monitoring` → runs a recovery health check
  - Incidents in `awaiting_review` where human has approved → resumes workflow
- Writes a heartbeat so the watchdog knows it's alive

**You inject incidents here in the dashboard.** The loop picks them up and drives them forward.

**Three tiers:**

| Tier | Risk Score | Human Review | Recovery |
|------|-----------|--------------|----------|
| 🟢 Low | ~0.1–0.2 | Never | 1 healthy check |
| 🟡 Medium | ~0.3–0.5 | Never (auto-approved) | 60s stability window |
| 🔴 High | ~0.7–0.9 | Always — you must approve | 60s stability window |

Go to **👤 Human Review Queue** to approve High-tier incidents.
        """)


def _launch_incident(scenario: dict, tier: dict, tier_key: str) -> None:
    """Inject the real service failure + launch the workflow thread."""
    svc    = scenario["service"]
    status = scenario["severity"]

    with st.spinner(f"Launching {tier_key} incident — {scenario['label']}..."):
        # 1. Actually degrade the service on the ops dashboard
        svc_result = _set_service_status(
            svc, status,
            f"{tier_key.upper()} tier incident injected via ITSM dashboard"
        )
        if not svc_result.get("success"):
            st.error(f"❌ Could not degrade {svc}: {svc_result.get('error')}")
            return

        # 2. Build pre-populated state and launch workflow in background
        preset = _build_preset_state(scenario, tier, tier_key)
        try:
            from workflows.monitoring_loop import launch_incident
            launch_incident(preset)
            iid = preset["incident_id"]
            st.success(f"✅ **{tier['label']}** incident launched — `{iid}`")
            if tier["force_human_review"]:
                st.warning(
                    "⏳ This is a **High** tier incident. "
                    "The workflow will pause at **👤 Human Review Queue**. "
                    "Go there to approve remediation."
                )
            else:
                st.info(
                    "Watch the workflow progress on **📋 Live Incident Feed** "
                    "and the GitHub board."
                )
        except Exception as exc:
            st.error(f"❌ Workflow launch failed: {exc}")

    st.rerun()


def _render_loop_status() -> None:
    try:
        from state.persistent_store import get_last_heartbeat
        hb = get_last_heartbeat()
        if hb:
            hb_dt = datetime.fromisoformat(hb)
            if hb_dt.tzinfo is None:
                hb_dt = hb_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - hb_dt).total_seconds()
            if age < 90:
                st.success(f"🟢 Monitoring loop running — heartbeat {age:.0f}s ago")
            else:
                st.error(f"🔴 Loop appears stopped (heartbeat {age:.0f}s ago) — run `python app.py --loop`")
        else:
            st.error("🔴 Monitoring loop not started — run `python app.py --loop` in a terminal")
    except Exception:
        st.warning("⚠️ Could not check loop status")


def _render_service_status() -> None:
    try:
        from services.monitoring_service import fetch_services
        services = fetch_services()
        if not services:
            st.caption("Ops dashboard unreachable")
            return
        cols = st.columns(len(services))
        for col, svc in zip(cols, services):
            status = svc.get("status", "?")
            icon   = {"healthy": "🟢", "degraded": "🟡", "down": "🔴"}.get(status, "⚪")
            col.markdown(
                f"<div style='text-align:center;padding:6px;background:#111;"
                f"border-radius:6px;border-top:2px solid "
                f"{'#2da44e' if status=='healthy' else '#e4c000' if status=='degraded' else '#d73a4a'};'>"
                f"<div style='font-size:1.4em;'>{icon}</div>"
                f"<div style='font-size:0.78em;font-weight:bold;'>{svc.get('service_name','?')}</div>"
                f"<div style='font-size:0.72em;color:#888;'>{status}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    except Exception:
        st.caption("Could not fetch service status")
