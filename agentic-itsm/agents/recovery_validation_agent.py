"""
Recovery Validation Agent — validates that the system has stabilised
after remediation. Runs during the MONITORING lifecycle stage.

Uses a stability window: must see N consecutive healthy checks
over MONITORING_STABILITY_SECONDS before declaring recovery confirmed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from state.incident_state import IncidentState, append_trace
from remediation.recovery_validator import check_recovery
from utils.config import config
from utils.logger import log_event, workflow_logger

AGENT_NAME = "RecoveryValidationAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    Reads:  monitoring_started_at, stability_checks_passed
    Writes: recovery_validated, stability_checks_passed, lifecycle_stage, last_health_check
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    now          = datetime.now(timezone.utc)
    started_str  = state.get("monitoring_started_at")
    checks       = state.get("stability_checks_passed", 0)
    required_s   = config.MONITORING_STABILITY_SECONDS  # default 300s

    result = check_recovery(state)
    state["last_health_check"] = now.isoformat()

    if result["healthy"]:
        checks += 1
        state["stability_checks_passed"] = checks

        # fast_recovery (Low tier): resolve after first healthy check, no wait
        if state.get("fast_recovery"):
            state["recovery_validated"] = True
            state["lifecycle_stage"]    = "resolved"
            detail = f"Fast recovery — service healthy after {checks} check(s)"
        else:
            elapsed = 0.0
            if started_str:
                try:
                    started = datetime.fromisoformat(started_str)
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    elapsed = (now - started).total_seconds()
                except Exception:
                    elapsed = 0.0

            if elapsed >= required_s and checks >= 2:
                state["recovery_validated"] = True
                state["lifecycle_stage"]    = "resolved"
                detail = (
                    f"Recovery validated after {elapsed:.0f}s "
                    f"({checks} consecutive healthy checks)"
                )
            else:
                state["recovery_validated"] = False
                state["lifecycle_stage"]    = "monitoring"
                detail = (
                    f"Stability check {checks} passed — "
                    f"{elapsed:.0f}s / {required_s}s required"
                )
    else:
        # Health check failed
        state["stability_checks_passed"] = 0
        state["recovery_validated"]      = False

        # For fast_recovery incidents: if remediation ran but service is still not
        # healthy, just wait — do NOT re-enter the remediate loop (avoids oscillation)
        if state.get("fast_recovery"):
            state["lifecycle_stage"] = "monitoring"
            detail = f"Fast recovery: service not yet healthy — waiting. {result.get('detail', '')}"
        else:
            state["lifecycle_stage"] = "investigating"
            detail = f"Recovery check failed: {result.get('detail', '')} — returning to Investigating"

    state = append_trace(state, AGENT_NAME, "recovery_check", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME,
              validated=state.get("recovery_validated"),
              checks=state.get("stability_checks_passed"),
              stage=state.get("lifecycle_stage"))
    return state
