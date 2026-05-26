"""
Escalation Agent — deterministic rule-based evaluation.

When AUTO_APPROVE_ESCALATIONS=true (default for demo), escalated incidents
are automatically approved so the full lifecycle (remediation → monitoring →
resolved) runs without waiting for manual human input.

Set AUTO_APPROVE_ESCALATIONS=false for real operational use — escalated
incidents will pause at the Human Review Queue instead.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from utils.config import config
from utils.constants import CRITICAL_SERVICES, SEVERITY_P1, SEVERITY_P2
from utils.logger import log_event, workflow_logger

AGENT_NAME = "EscalationAgent"


def _get_rules(state: IncidentState):
    return [
        (
            "P1 severity incident detected",
            lambda s: s.get("severity") == SEVERITY_P1,
        ),
        (
            "Critical service affected (auth-service, database, api-gateway)",
            lambda s: any(
                a.get("affected_service", "") in CRITICAL_SERVICES
                for a in s.get("anomalies", [])
            ),
        ),
        (
            f"AI confidence below threshold ({config.LOW_CONFIDENCE_THRESHOLD:.0%})",
            lambda s: 0.0 < s.get("ai_confidence", 1.0) < config.LOW_CONFIDENCE_THRESHOLD,
        ),
        (
            "Deployment failure or rollback in correlated deployment",
            lambda s: s.get("correlated_deployment") is not None
            and s["correlated_deployment"].get("status") in ("failed", "rolled_back"),
        ),
        (
            "Multiple anomalies detected (≥3)",
            lambda s: len(s.get("anomalies", [])) >= 3,
        ),
        (
            "P2 incident with service outage type",
            lambda s: s.get("severity") == SEVERITY_P2
            and s.get("incident_type") in ("Service Outage", "Authentication", "Database Issue"),
        ),
        (
            "Health check endpoint returning system-level failure",
            lambda s: s.get("raw_health", {}).get("overall") == "down",
        ),
    ]


def run(state: IncidentState) -> IncidentState:
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    triggered_reasons: list[str] = []
    for reason, predicate in _get_rules(state):
        try:
            if predicate(state):
                triggered_reasons.append(reason)
        except Exception as exc:
            log_event(workflow_logger, "warning", "escalation_rule_error",
                      reason=reason, error=str(exc))

    escalation_required = len(triggered_reasons) > 0
    state["escalation_required"] = escalation_required
    state["escalation_reasons"]  = triggered_reasons

    if escalation_required or state.get("force_human_review"):
        if config.AUTO_APPROVE_ESCALATIONS and not state.get("force_human_review"):
            state["human_approved"]          = True
            state["paused_for_human_review"] = False
            state["lifecycle_stage"]         = "fix_in_progress"
            log_event(workflow_logger, "info", "escalation_auto_approved",
                      agent=AGENT_NAME,
                      rules_triggered=len(triggered_reasons),
                      note="AUTO_APPROVE_ESCALATIONS=true — proceeding to remediation")
        else:
            # High-tier incident or AUTO_APPROVE off — require human
            state["escalation_required"]     = True
            state["human_approved"]          = None
            state["paused_for_human_review"] = False
            state["lifecycle_stage"]         = "awaiting_review"
    else:
        state["lifecycle_stage"] = "fix_in_progress"

    detail = (
        f"Escalation REQUIRED ({len(triggered_reasons)} rules) — "
        f"{'auto-approved' if config.AUTO_APPROVE_ESCALATIONS else 'awaiting human review'}: "
        f"{triggered_reasons}"
        if escalation_required
        else "No escalation required"
    )
    state = append_trace(state, AGENT_NAME, "escalation_evaluated", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME,
              escalation_required=escalation_required,
              auto_approved=config.AUTO_APPROVE_ESCALATIONS if escalation_required else None,
              triggered_rules=triggered_reasons)
    return state
