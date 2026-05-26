"""
Resolution Agent — closes the incident once recovery is validated.
Updates the ops-dashboard incident, closes the GitHub issue,
moves the project card to Resolved, and marks the state complete.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from state.incident_state import IncidentState, append_trace
from services.github_service import add_issue_comment, transition_project_column
from utils.config import config
from utils.constants import COLUMN_RESOLVED
from utils.logger import log_event, workflow_logger

AGENT_NAME = "ResolutionAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    Reads:  recovery_validated, github_issue_number, github_project_item_id
    Writes: github_column, completed, lifecycle_stage
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    if not state.get("recovery_validated"):
        state = append_trace(state, AGENT_NAME, "resolution_skipped",
                             "Recovery not yet validated — skipping resolution")
        return state

    iid  = state.get("incident_id", "N/A")
    rca  = state.get("root_cause_summary", "N/A")
    rem  = state.get("remediation_detail", "N/A")
    stab = state.get("stability_checks_passed", 0)

    # 1. Move GitHub issue to Resolved
    item_id = state.get("github_project_item_id")
    if item_id:
        try:
            transition_project_column(item_id, COLUMN_RESOLVED)
            state["github_column"] = COLUMN_RESOLVED
            log_event(workflow_logger, "info", "github_column_moved", column=COLUMN_RESOLVED)
        except Exception as exc:
            log_event(workflow_logger, "warning", "github_column_move_failed", error=str(exc))

    # 2. Comment on the GitHub issue
    issue_number = state.get("github_issue_number")
    if issue_number:
        comment = (
            f"## ✅ Incident Resolved\n\n"
            f"**Incident ID:** `{iid}`  \n"
            f"**Resolved at:** {datetime.now(timezone.utc).isoformat()}  \n"
            f"**Stability checks passed:** {stab}  \n\n"
            f"**Root Cause:**\n> {rca}\n\n"
            f"**Remediation Applied:**\n> {rem}\n\n"
            f"*Closed automatically by the Agentic ITSM platform.*"
        )
        try:
            add_issue_comment(issue_number, comment)
        except Exception as exc:
            log_event(workflow_logger, "warning", "github_comment_failed", error=str(exc))

    # 3. Resolve the incident on the ops dashboard
    ops_incident_id = _find_ops_incident_id(state)
    if ops_incident_id:
        _resolve_ops_incident(ops_incident_id, rca)

    state["lifecycle_stage"] = "resolved"
    state["completed"]       = True

    detail = f"Incident {iid} resolved after {stab} stability checks"
    state = append_trace(state, AGENT_NAME, "incident_resolved", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, incident_id=iid)
    return state


def _find_ops_incident_id(state: dict) -> int | None:
    """Try to find the ops-dashboard incident ID from anomalies or a recorded field."""
    return state.get("ops_incident_id")


def _resolve_ops_incident(ops_incident_id: int, rca: str) -> None:
    try:
        with httpx.Client(base_url=config.OPS_DASHBOARD_URL,
                          headers={"X-API-Key": config.OPS_API_KEY},
                          timeout=10) as c:
            c.patch(f"/incidents/{ops_incident_id}", json={
                "status": "resolved",
                "notes":  f"Resolved by Agentic ITSM. RCA: {rca[:200]}",
            })
    except Exception as exc:
        log_event(workflow_logger, "warning", "ops_incident_resolve_failed",
                  ops_id=ops_incident_id, error=str(exc))
