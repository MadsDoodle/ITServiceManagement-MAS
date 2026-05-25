"""
Shared LangGraph state object passed through the entire incident workflow.
Every agent reads from and writes back to this TypedDict.
Keeping it as a plain dataclass-style TypedDict means LangGraph's
checkpointer can serialise it without any custom adapters.
"""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class IncidentState(TypedDict, total=False):
    # ── Monitoring phase ──────────────────────────────────────────────────────
    raw_health: dict          # /health/ response
    raw_metrics: dict         # /metrics/ response
    raw_logs: list[dict]      # recent log entries
    raw_deployments: list[dict]  # recent deployments
    anomalies: list[dict]     # detected anomaly objects

    # ── Classification phase ──────────────────────────────────────────────────
    severity: str             # P1 / P2 / P3 / Low
    incident_type: str        # one of INCIDENT_TYPES
    ai_confidence: float      # 0.0 – 1.0
    classification_reasoning: str

    # ── RCA phase ─────────────────────────────────────────────────────────────
    root_cause_summary: str
    correlated_deployment: Optional[dict]
    rca_reasoning: str

    # ── Escalation phase ──────────────────────────────────────────────────────
    escalation_required: bool
    escalation_reasons: list[str]

    # ── GitHub phase ─────────────────────────────────────────────────────────
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    github_project_item_id: Optional[str]
    github_column: str

    # ── Notification phase ────────────────────────────────────────────────────
    notification_sent: bool
    notification_summary: str

    # ── Execution trace ───────────────────────────────────────────────────────
    trace: list[dict]         # [{agent, action, timestamp, detail}, ...]

    # ── Lifecycle ────────────────────────────────────────────────────────────
    incident_id: str          # internal UUID
    workflow_run_id: str      # for deduplication
    created_at: str           # ISO-8601
    completed: bool
    error: Optional[str]      # last unrecoverable error message


def new_state(incident_id: str, workflow_run_id: str, created_at: str) -> IncidentState:
    """Return a minimal valid initial state."""
    return IncidentState(
        raw_health={},
        raw_metrics={},
        raw_logs=[],
        raw_deployments=[],
        anomalies=[],
        severity="",
        incident_type="",
        ai_confidence=0.0,
        classification_reasoning="",
        root_cause_summary="",
        correlated_deployment=None,
        rca_reasoning="",
        escalation_required=False,
        escalation_reasons=[],
        github_issue_number=None,
        github_issue_url=None,
        github_project_item_id=None,
        github_column="New",
        notification_sent=False,
        notification_summary="",
        trace=[],
        incident_id=incident_id,
        workflow_run_id=workflow_run_id,
        created_at=created_at,
        completed=False,
        error=None,
    )


def append_trace(state: IncidentState, agent: str, action: str, detail: str = "") -> IncidentState:
    """Append an execution trace entry and return the updated state."""
    from datetime import datetime, timezone
    entry = {
        "agent": agent,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state["trace"] = state.get("trace", []) + [entry]
    return state
