"""
Escalation Agent — fully deterministic rule-based evaluation.
Decides whether human escalation is required based on operational risk factors.
No LLM involved — escalation logic must be predictable and auditable.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from utils.config import config
from utils.constants import CRITICAL_SERVICES, SEVERITY_P1, SEVERITY_P2
from utils.logger import log_event, workflow_logger

AGENT_NAME = "EscalationAgent"

# ── Escalation rules ─────────────────────────────────────────────────────────
# Each rule is a (reason_string, predicate) pair.
# A single match triggers escalation.

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
    """
    LangGraph node function.
    Reads:  severity, ai_confidence, anomalies, correlated_deployment, raw_health, incident_type
    Writes: escalation_required, escalation_reasons
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    triggered_reasons: list[str] = []
    for reason, predicate in _get_rules(state):
        try:
            if predicate(state):
                triggered_reasons.append(reason)
        except Exception as exc:
            log_event(workflow_logger, "warning", "escalation_rule_error", reason=reason, error=str(exc))

    escalation_required = len(triggered_reasons) > 0
    state["escalation_required"] = escalation_required
    state["escalation_reasons"]  = triggered_reasons

    detail = (
        f"Escalation REQUIRED — {len(triggered_reasons)} rule(s) triggered: {triggered_reasons}"
        if escalation_required
        else "No escalation required"
    )
    state = append_trace(state, AGENT_NAME, "escalation_evaluated", detail)
    log_event(
        workflow_logger, "info", "agent_complete",
        agent=AGENT_NAME,
        escalation_required=escalation_required,
        triggered_rules=triggered_reasons,
    )
    return state
