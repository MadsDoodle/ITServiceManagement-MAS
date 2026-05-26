"""
Remediation Agent — executes the chosen low-risk remediation strategy
by delegating to the correct module in remediation/.
Only runs if escalation_required is False OR human_approved is True.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from utils.constants import (
    REMEDIATION_RESET_AUTH,
    REMEDIATION_CLEAR_LATENCY,
    REMEDIATION_RESTART_SERVICE,
    REMEDIATION_ROLLBACK_DEPLOY,
    REMEDIATION_MANUAL,
    REMEDIATION_NONE,
)
from utils.logger import log_event, workflow_logger

AGENT_NAME = "RemediationAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    Reads:  remediation_strategy, escalation_required, human_approved
    Writes: remediation_attempted, remediation_succeeded, remediation_detail, lifecycle_stage
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    strategy         = state.get("remediation_strategy", REMEDIATION_NONE)
    escalated        = state.get("escalation_required", False)
    human_approved   = state.get("human_approved")
    retries          = state.get("remediation_retries", 0)

    # Guard: don't auto-remediate escalated incidents unless human approved
    if escalated and human_approved is not True:
        state["remediation_attempted"] = False
        state["remediation_detail"]    = (
            "Remediation blocked — escalation required and awaiting human approval"
        )
        state["lifecycle_stage"] = "awaiting_review"
        state = append_trace(state, AGENT_NAME, "remediation_blocked",
                             state["remediation_detail"])
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, attempted=False, reason="awaiting_human")
        return state

    if strategy in (REMEDIATION_NONE, REMEDIATION_MANUAL) and human_approved is not True:
        state["remediation_attempted"] = False
        state["remediation_detail"]    = f"No auto-remediation for strategy: {strategy}"
        state["lifecycle_stage"]       = "investigating"
        state = append_trace(state, AGENT_NAME, "remediation_skipped",
                             state["remediation_detail"])
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, attempted=False, strategy=strategy)
        return state

    # When strategy is manual but human approved, pick the best concrete strategy
    if strategy == REMEDIATION_MANUAL and human_approved is True:
        strategy = _infer_strategy_from_anomalies(state)
        state["remediation_strategy"] = strategy
        log_event(workflow_logger, "info", "remediation_strategy_inferred",
                  agent=AGENT_NAME, inferred=strategy)

    # Execute
    result = _execute(strategy, state)
    state["remediation_attempted"]  = True
    state["remediation_succeeded"]  = result.get("success", False)
    state["remediation_detail"]     = result.get("detail", "")
    state["remediation_retries"]    = retries + (0 if result.get("success") else 1)

    # If guardrails forced escalation (budget exhausted), go to awaiting_review
    if not result.get("success") and "Guardrail blocked" in result.get("detail", ""):
        if "budget exhausted" in result.get("detail", "").lower():
            state["escalation_required"] = True
            state["escalation_reasons"]  = state.get("escalation_reasons", []) + [
                result["detail"]
            ]
            state["lifecycle_stage"] = "awaiting_review"
            state["paused_for_human_review"] = True
            state = append_trace(state, AGENT_NAME, "escalated_by_guardrail", result["detail"])
            log_event(workflow_logger, "warning", "remediation_escalated_by_guard",
                      agent=AGENT_NAME, detail=result["detail"])
            return state

    if result.get("success"):
        state["lifecycle_stage"] = "monitoring"
        from datetime import datetime, timezone
        state["monitoring_started_at"] = datetime.now(timezone.utc).isoformat()
    else:
        state["lifecycle_stage"] = "investigating"

    detail = (
        f"Strategy: {strategy} | "
        f"Success: {result.get('success')} | "
        f"{result.get('detail', '')[:120]}"
    )
    state = append_trace(state, AGENT_NAME, "remediation_executed", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, strategy=strategy, success=result.get("success"))
    return state


def _infer_strategy_from_anomalies(state: dict) -> str:
    """
    When a manual-rated incident gets human approval, pick the best
    concrete low-risk strategy based on what anomalies were detected.
    """
    anomalies = state.get("anomalies", [])
    types     = [a.get("type", "") for a in anomalies]
    services  = [a.get("affected_service", "") for a in anomalies]

    if any("auth" in svc for svc in services):
        return REMEDIATION_RESET_AUTH
    if any("latency" in t or "high_latency" in t for t in types):
        return REMEDIATION_CLEAR_LATENCY
    corr = state.get("correlated_deployment")
    if corr and corr.get("status") in ("failed", "rolled_back"):
        return REMEDIATION_ROLLBACK_DEPLOY
    if any(t in ("service_down", "service_degraded", "health_check_failure") for t in types):
        return REMEDIATION_RESTART_SERVICE
    return REMEDIATION_RESTART_SERVICE   # safe default


def _execute(strategy: str, state: dict) -> dict:
    """Dispatch to the correct remediation module."""
    try:
        if strategy == REMEDIATION_RESET_AUTH:
            from remediation.auth_remediation import remediate
            return remediate(state)
        elif strategy == REMEDIATION_CLEAR_LATENCY:
            from remediation.latency_remediation import remediate
            return remediate(state)
        elif strategy == REMEDIATION_RESTART_SERVICE:
            from remediation.service_restart import remediate
            return remediate(state)
        elif strategy == REMEDIATION_ROLLBACK_DEPLOY:
            from remediation.deployment_remediation import remediate
            return remediate(state)
        else:
            return {"success": False, "detail": f"No handler for strategy: {strategy}"}
    except Exception as exc:
        return {"success": False, "detail": f"Remediation exception: {exc}"}
