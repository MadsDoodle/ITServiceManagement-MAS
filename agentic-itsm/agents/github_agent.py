"""
GitHub Operations Agent — deterministic.
Creates GitHub issues, adds them to the Project board, sets workflow columns,
and updates all custom fields. No LLM involved.
"""
from __future__ import annotations

from datetime import datetime, timezone

from state.incident_state import IncidentState, append_trace
from services.github_service import (
    add_issue_comment,
    create_incident_ticket,
    transition_project_column,
)
from utils.constants import COLUMN_TRIAGE
from utils.logger import log_event, workflow_logger

AGENT_NAME = "GitHubAgent"


def _build_issue_body(state: IncidentState) -> str:
    anomalies = state.get("anomalies", [])
    anomaly_lines = "\n".join(
        f"- **{a.get('type', 'unknown')}**: {a.get('description', '')} (affected: `{a.get('affected_service', 'N/A')}`)"
        for a in anomalies
    ) or "_No anomalies recorded_"

    corr = state.get("correlated_deployment")
    corr_line = (
        f"`{corr.get('deployment_id')}` — version {corr.get('version')} "
        f"(status: **{corr.get('status')}**, commit: `{corr.get('commit_ref')}`)"
        if corr
        else "_None identified_"
    )

    esc_reasons = "\n".join(
        f"- {r}" for r in state.get("escalation_reasons", [])
    ) or "_No escalation triggered_"

    return f"""## 🤖 AI-Managed ITSM Incident

| Field | Value |
|-------|-------|
| **Incident ID** | `{state.get('incident_id', 'N/A')}` |
| **Severity** | `{state.get('severity', 'N/A')}` |
| **Incident Type** | {state.get('incident_type', 'N/A')} |
| **AI Confidence** | {state.get('ai_confidence', 0):.0%} |
| **Escalation Required** | {'⚠️ YES' if state.get('escalation_required') else '✅ No'} |
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

## Classification Reasoning

> {state.get('classification_reasoning', '_Not available_')}

---

## Escalation Evaluation

{esc_reasons}

---

*This issue was created automatically by the Agentic ITSM platform. Do not edit the header table manually.*
"""


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node function.
    Reads:  severity, incident_type, escalation_required, ai_confidence, all analysis fields
    Writes: github_issue_number, github_issue_url, github_project_item_id, github_column
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    severity        = state.get("severity", "P3")
    incident_type   = state.get("incident_type", "Monitoring Alert")
    anomalies       = state.get("anomalies", [])
    incident_id     = state.get("incident_id", "N/A")
    escalation_req  = state.get("escalation_required", False)
    ai_confidence   = state.get("ai_confidence", 0.0)

    # Build issue title from primary anomaly
    primary_anomaly = anomalies[0] if anomalies else {}
    service         = primary_anomaly.get("affected_service", "system")
    description     = primary_anomaly.get("description", "Operational anomaly detected")
    title = f"[{severity}] {incident_type} — {service}: {description[:80]}"

    body = _build_issue_body(state)

    try:
        result = create_incident_ticket(
            title=title,
            body=body,
            severity=severity,
            incident_type=incident_type,
            escalation_required=escalation_req,
            ai_confidence=ai_confidence,
            column=COLUMN_TRIAGE,
        )

        state["github_issue_number"]    = result["issue_number"]
        state["github_issue_url"]       = result["issue_url"]
        state["github_project_item_id"] = result["item_id"]
        state["github_column"]          = COLUMN_TRIAGE

        detail = f"Issue #{result['issue_number']} created: {result['issue_url']}"
        state = append_trace(state, AGENT_NAME, "github_issue_created", detail)
        log_event(
            workflow_logger, "info", "agent_complete",
            agent=AGENT_NAME,
            issue_number=result["issue_number"],
            issue_url=result["issue_url"],
        )
    except Exception as exc:
        log_event(workflow_logger, "error", "github_agent_failed", error=str(exc))
        state = append_trace(state, AGENT_NAME, "github_failed", str(exc))
        state["error"] = str(exc)

    return state
