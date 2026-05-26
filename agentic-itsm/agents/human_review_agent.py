"""
Human Review Agent — pauses the workflow when escalation is required.
The workflow enters AWAITING_REVIEW state. The dashboard human review queue
lets operators approve or reject, which unblocks the workflow.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from utils.logger import log_event, workflow_logger

AGENT_NAME = "HumanReviewAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    If escalation_required and human_approved is None → pause workflow.
    If human_approved is True  → let workflow continue to remediation.
    If human_approved is False → mark as needing manual resolution.
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    escalated      = state.get("escalation_required", False)
    human_approved = state.get("human_approved")

    if not escalated:
        # No escalation — pass through
        state = append_trace(state, AGENT_NAME, "human_review_skipped",
                             "No escalation — human review not required")
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, outcome="not_required")
        return state

    if human_approved is None:
        # First visit — enter paused state
        state["paused_for_human_review"] = True
        state["lifecycle_stage"]         = "awaiting_review"
        detail = (
            f"Incident paused for human review. "
            f"Escalation reasons: {state.get('escalation_reasons', [])}"
        )
        state = append_trace(state, AGENT_NAME, "human_review_required", detail)
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, outcome="paused")
        return state

    if human_approved is True:
        state["paused_for_human_review"] = False
        state["lifecycle_stage"]         = "fix_in_progress"
        detail = f"Human approved. Notes: {state.get('human_notes', '')}"
        state = append_trace(state, AGENT_NAME, "human_approved", detail)
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME, outcome="approved")
        return state

    # human_approved is False — rejected
    state["paused_for_human_review"] = False
    state["lifecycle_stage"]         = "investigating"
    state["remediation_strategy"]    = "manual"
    detail = (
        f"Human rejected auto-remediation. "
        f"Notes: {state.get('human_notes', '')}. Manual intervention required."
    )
    state = append_trace(state, AGENT_NAME, "human_rejected", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, outcome="rejected")
    return state
