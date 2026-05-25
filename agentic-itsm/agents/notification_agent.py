"""
Notification Agent — sends Gmail alerts for escalated incidents
and optionally uses the LLM to generate a polished email body.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.gmail_service import send_escalation_email
from services.llm_service import summarize_for_email
from utils.logger import log_event, workflow_logger

AGENT_NAME = "NotificationAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node function.
    Only sends notification if escalation_required is True.
    Reads:  escalation_required, all incident fields
    Writes: notification_sent, notification_summary
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    if not state.get("escalation_required", False):
        state["notification_sent"]    = False
        state["notification_summary"] = "Notification skipped — no escalation required"
        state = append_trace(state, AGENT_NAME, "notification_skipped", "No escalation — no email sent")
        log_event(workflow_logger, "info", "agent_complete", agent=AGENT_NAME, sent=False)
        return state

    # Generate email body (LLM optional, falls back to template)
    email_body = summarize_for_email(dict(state))

    sent = send_escalation_email(state=dict(state), email_body=email_body)

    state["notification_sent"]    = sent
    state["notification_summary"] = email_body[:300] + "..." if len(email_body) > 300 else email_body

    detail = f"Email sent: {sent} | Severity: {state.get('severity')} | Escalation reasons: {len(state.get('escalation_reasons', []))}"
    state = append_trace(state, AGENT_NAME, "notification_complete", detail)
    log_event(
        workflow_logger, "info", "agent_complete",
        agent=AGENT_NAME,
        sent=sent,
        severity=state.get("severity"),
    )
    return state
