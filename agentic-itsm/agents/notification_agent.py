"""
Notification Agent — sends stage-based email notifications at every lifecycle transition.
Uses HTML templates with coloured banners per stage.
Falls back gracefully if Gmail is not configured.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.gmail_service import send_stage_notification
from services.llm_service import summarize_for_email
from utils.constants import (
    NOTIF_INCIDENT_DETECTED,
    NOTIF_TRIAGE_STARTED,
    NOTIF_INVESTIGATION_START,
    NOTIF_REMEDIATION_START,
    NOTIF_ESCALATED,
    NOTIF_MONITORING_START,
    NOTIF_RESOLVED,
)
from utils.logger import log_event, workflow_logger

AGENT_NAME = "NotificationAgent"

# Map lifecycle stage → notification stage key
_STAGE_MAP = {
    "new":             NOTIF_INCIDENT_DETECTED,
    "triage":          NOTIF_TRIAGE_STARTED,
    "investigating":   NOTIF_INVESTIGATION_START,
    "fix_in_progress": NOTIF_REMEDIATION_START,
    "awaiting_review": NOTIF_ESCALATED,
    "monitoring":      NOTIF_MONITORING_START,
    "resolved":        NOTIF_RESOLVED,
}


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node — fires an email for the current lifecycle stage.
    De-duplicates: won't send the same stage twice for the same incident.
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    lifecycle_stage = state.get("lifecycle_stage", "new")
    notif_stage     = _STAGE_MAP.get(lifecycle_stage, NOTIF_INCIDENT_DETECTED)

    sent_stages = state.get("notifications_sent_stages", [])
    if notif_stage in sent_stages:
        detail = f"Notification already sent for stage: {notif_stage}"
        state = append_trace(state, AGENT_NAME, "notification_skipped", detail)
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, sent=False, reason="duplicate")
        return state

    # Generate summary (LLM if available, template fallback)
    email_summary = summarize_for_email(dict(state))

    sent = send_stage_notification(
        stage=notif_stage,
        state=dict(state),
        email_body=email_summary,
    )

    if sent:
        sent_stages = list(sent_stages) + [notif_stage]
        state["notifications_sent_stages"] = sent_stages
        state["notification_sent"]         = True

    state["notification_summary"] = email_summary[:300] + "..." \
        if len(email_summary) > 300 else email_summary

    detail = f"Stage: {notif_stage} | Sent: {sent}"
    state = append_trace(state, AGENT_NAME, "notification_dispatched", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, stage=notif_stage, sent=sent)
    return state
