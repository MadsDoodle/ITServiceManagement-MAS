"""
GitHub Operations Agent — deterministic.
Creates GitHub issues in the NEW column, waits STAGE_TRANSITION_DELAY_SECONDS
so the board is visibly observable, then moves to TRIAGE.
Subsequent lifecycle transitions are driven by move_to_column() called from
the workflow node wrappers.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from state.incident_state import IncidentState, append_trace
from services.github_service import (
    add_issue_comment,
    create_incident_ticket,
    transition_project_column,
)
from utils.config import config
from utils.constants import COLUMN_NEW, COLUMN_TRIAGE, LIFECYCLE_TO_COLUMN
from utils.logger import log_event, workflow_logger

AGENT_NAME = "GitHubAgent"


def move_to_column(state: IncidentState, column: str) -> IncidentState:
    """
    Move the GitHub project item to `column` and update state.
    Safe to call even if there is no project item (silently skips).
    Respects STAGE_TRANSITION_DELAY_SECONDS so column changes are visible.
    """
    item_id = state.get("github_project_item_id")
    if not item_id:
        return state
    if state.get("github_column") == column:
        return state   # already there

    delay = config.STAGE_TRANSITION_DELAY_SECONDS
    if delay > 0:
        log_event(workflow_logger, "info", "github_column_transition_delay",
                  delay_s=delay, target_column=column)
        time.sleep(delay)

    try:
        transition_project_column(item_id, column)
        state["github_column"] = column
        log_event(workflow_logger, "info", "github_column_moved",
                  column=column, item_id=item_id)
        state = append_trace(state, AGENT_NAME, "column_moved", f"→ {column}")
    except Exception as exc:
        log_event(workflow_logger, "warning", "github_column_move_failed",
                  column=column, error=str(exc))
    return state


def post_lifecycle_comment(state: IncidentState, stage: str, detail: str = "") -> None:
    """Add a timestamped lifecycle comment to the GitHub issue."""
    issue_number = state.get("github_issue_number")
    if not issue_number:
        return
    stage_labels = {
        "triage":          "🏷️ Triage",
        "investigating":   "🔍 Investigating",
        "fix_in_progress": "🔧 Fix In Progress",
        "awaiting_review": "👤 Awaiting Human Review",
        "monitoring":      "📡 Monitoring Recovery",
        "resolved":        "✅ Resolved",
    }
    label = stage_labels.get(stage, stage.replace("_", " ").title())
    ts    = datetime.now(timezone.utc).isoformat()
    body  = f"**{label}** — `{ts}`"
    if detail:
        body += f"\n\n> {detail}"
    try:
        add_issue_comment(issue_number, body)
    except Exception as exc:
        log_event(workflow_logger, "warning", "github_comment_failed", error=str(exc))


def _build_issue_body(state: IncidentState) -> str:
    anomalies = state.get("anomalies", [])
    anomaly_lines = "\n".join(
        f"- **{a.get('type', 'unknown')}**: {a.get('description', '')} (service: `{a.get('affected_service', 'N/A')}`)"
        for a in anomalies
    ) or "_No anomalies recorded_"

    corr = state.get("correlated_deployment")
    corr_line = (
        f"`{corr.get('deployment_id')}` — version {corr.get('version')} "
        f"(status: **{corr.get('status')}**, commit: `{corr.get('commit_ref')}`)"
        if corr else "_None identified_"
    )

    esc_reasons = "\n".join(
        f"- {r}" for r in state.get("escalation_reasons", [])
    ) or "_No escalation triggered_"

    risk = state.get("risk_score", 0.0) or 0.0

    return f"""## 🤖 AI-Managed ITSM Incident

| Field | Value |
|-------|-------|
| **Incident ID** | `{state.get('incident_id', 'N/A')}` |
| **Severity** | `{state.get('severity', 'N/A')}` |
| **Incident Type** | {state.get('incident_type', 'N/A')} |
| **Risk Score** | {risk:.2f} / 1.00 |
| **AI Confidence** | {state.get('ai_confidence', 0):.0%} |
| **Escalation Required** | {'⚠️ YES' if state.get('escalation_required') else '✅ No'} |
| **Remediation Strategy** | `{state.get('remediation_strategy', 'none')}` |
| **Detected At** | {state.get('created_at', 'N/A')} |
| **Workflow Run** | `{state.get('workflow_run_id', 'N/A')}` |

---

## Detected Anomalies

{anomaly_lines}

---

## Root Cause Analysis

{state.get('root_cause_summary', '_Not available_')}

**Correlated Deployment:** {corr_line}

**AI Reasoning:**
> {state.get('rca_reasoning', '_Not available_')}

---

## Escalation Evaluation

{esc_reasons}

---

*Auto-created by the Agentic ITSM platform. Lifecycle updates posted as comments.*
"""


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    1. Creates issue in NEW column
    2. Pauses STAGE_TRANSITION_DELAY_SECONDS (visible on board)
    3. Moves to TRIAGE
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    severity       = state.get("severity", "P3")
    incident_type  = state.get("incident_type", "Monitoring Alert")
    anomalies      = state.get("anomalies", [])
    incident_id    = state.get("incident_id", "N/A")
    escalation_req = state.get("escalation_required", False)
    ai_confidence  = state.get("ai_confidence", 0.0)

    primary_anomaly = anomalies[0] if anomalies else {}
    service         = primary_anomaly.get("affected_service", "system")
    description     = primary_anomaly.get("description", "Operational anomaly detected")
    title = f"[{severity}] {incident_type} — {service}: {description[:80]}"
    body  = _build_issue_body(state)

    try:
        # If issue already exists (re-entry from regressed path), just move to Triage and skip creation
        if state.get("github_issue_number"):
            log_event(workflow_logger, "info", "github_issue_already_exists",
                      agent=AGENT_NAME, issue_number=state["github_issue_number"])
            state = move_to_column(state, COLUMN_TRIAGE)
            state["lifecycle_stage"] = "triage"
            state = append_trace(state, AGENT_NAME, "github_issue_reused",
                                 f"Reusing existing issue #{state['github_issue_number']}")
            return state

        # Step 1: create in NEW column
        result = create_incident_ticket(
            title=title,
            body=body,
            severity=severity,
            incident_type=incident_type,
            escalation_required=escalation_req,
            ai_confidence=ai_confidence,
            column=COLUMN_NEW,
        )

        state["github_issue_number"]    = result["issue_number"]
        state["github_issue_url"]       = result["issue_url"]
        state["github_project_item_id"] = result["item_id"]
        state["github_column"]          = COLUMN_NEW

        log_event(workflow_logger, "info", "github_issue_created",
                  incident_id=incident_id,
                  issue_number=result["issue_number"],
                  issue_url=result["issue_url"],
                  column=COLUMN_NEW)

        # Step 2: pause so "New" is visible on the board
        delay = config.STAGE_TRANSITION_DELAY_SECONDS
        if delay > 0:
            log_event(workflow_logger, "info", "github_new_column_pause",
                      delay_s=delay, note=f"Issue visible in New for {delay}s")
            time.sleep(delay)

        # Step 3: move to Triage
        state = move_to_column(state, COLUMN_TRIAGE)
        state["lifecycle_stage"] = "triage"
        post_lifecycle_comment(state, "triage",
                               f"Severity: {severity} | Type: {incident_type} | Confidence: {ai_confidence:.0%}")

        detail = f"Issue #{result['issue_number']} created → New → Triage: {result['issue_url']}"
        state  = append_trace(state, AGENT_NAME, "github_issue_created", detail)
        log_event(workflow_logger, "info", "agent_complete",
                  agent=AGENT_NAME,
                  issue_number=result["issue_number"],
                  column=COLUMN_TRIAGE)

    except Exception as exc:
        log_event(workflow_logger, "error", "github_agent_failed", error=str(exc))
        state = append_trace(state, AGENT_NAME, "github_failed", str(exc))
        state["error"] = str(exc)

    return state
