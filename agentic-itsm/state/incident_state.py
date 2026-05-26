"""
Shared LangGraph state object for the continuous incident lifecycle.
Every agent reads from and writes back to this TypedDict.
Designed to be serialisable by LangGraph's checkpointer without adapters.
"""
from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class IncidentState(TypedDict, total=False):
    # ── Identity & lifecycle ─────────────────────────────────────────────────
    incident_id: str              # internal UUID, INC-XXXXXXXX
    workflow_run_id: str          # per-execution thread ID
    created_at: str               # ISO-8601
    lifecycle_stage: str          # new / triage / investigating / fix_in_progress /
                                  #   awaiting_review / monitoring / resolved
    completed: bool
    error: Optional[str]

    # ── Monitoring phase ──────────────────────────────────────────────────────
    raw_health: dict
    raw_metrics: dict
    raw_logs: list[dict]
    raw_deployments: list[dict]
    anomalies: list[dict]

    # ── Classification / triage phase ────────────────────────────────────────
    severity: str                 # P1 / P2 / P3 / Low
    incident_type: str
    ai_confidence: float
    classification_reasoning: str
    risk_score: float             # 0.0–1.0 composite risk

    # ── RCA phase ─────────────────────────────────────────────────────────────
    root_cause_summary: str
    correlated_deployment: Optional[dict]
    rca_reasoning: str

    # ── Escalation phase ──────────────────────────────────────────────────────
    escalation_required: bool
    escalation_reasons: list[str]
    paused_for_human_review: bool
    human_approved: Optional[bool]   # None=pending, True=approved, False=rejected
    human_notes: str
    assigned_human: str

    # ── Remediation phase ────────────────────────────────────────────────────
    remediation_strategy: str     # one of constants.REMEDIATION_*
    remediation_attempted: bool
    remediation_succeeded: bool
    remediation_detail: str
    remediation_retries: int

    # ── Recovery validation / monitoring phase ────────────────────────────────
    monitoring_started_at: Optional[str]   # ISO-8601
    recovery_validated: bool
    stability_checks_passed: int
    last_health_check: Optional[str]

    # ── GitHub phase ─────────────────────────────────────────────────────────
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    github_project_item_id: Optional[str]
    github_column: str

    # ── Notification phase ────────────────────────────────────────────────────
    notification_sent: bool
    notification_summary: str
    notifications_sent_stages: list[str]   # which stages emails were sent for

    # ── Execution trace ───────────────────────────────────────────────────────
    trace: list[dict]

    # ── Correlation ───────────────────────────────────────────────────────────
    related_incident_ids: list[str]      # other incidents caused by the same root event
    root_cause_incident_id: Optional[str]  # if this is a cascading incident
    correlation_reason: str              # human-readable explanation of link

    # ── Demo / injection control ─────────────────────────────────────────────
    # Set by the dashboard injection buttons to control workflow behaviour
    pre_populated_anomalies: bool   # if True, monitoring agent skips re-fetching
    force_human_review: bool        # if True, always require human approval (High tier)
    fast_recovery: bool             # if True, recovery validates after 1 healthy check (Low tier)


def new_state(incident_id: str, workflow_run_id: str, created_at: str) -> IncidentState:
    """Return a minimal valid initial state."""
    return IncidentState(
        incident_id=incident_id,
        workflow_run_id=workflow_run_id,
        created_at=created_at,
        lifecycle_stage="new",
        completed=False,
        error=None,
        # monitoring
        raw_health={},
        raw_metrics={},
        raw_logs=[],
        raw_deployments=[],
        anomalies=[],
        # classification
        severity="",
        incident_type="",
        ai_confidence=0.0,
        classification_reasoning="",
        risk_score=0.0,
        # rca
        root_cause_summary="",
        correlated_deployment=None,
        rca_reasoning="",
        # escalation
        escalation_required=False,
        escalation_reasons=[],
        paused_for_human_review=False,
        human_approved=None,
        human_notes="",
        assigned_human="",
        # remediation
        remediation_strategy="none",
        remediation_attempted=False,
        remediation_succeeded=False,
        remediation_detail="",
        remediation_retries=0,
        # recovery
        monitoring_started_at=None,
        recovery_validated=False,
        stability_checks_passed=0,
        last_health_check=None,
        # github
        github_issue_number=None,
        github_issue_url=None,
        github_project_item_id=None,
        github_column="New",
        # notifications
        notification_sent=False,
        notification_summary="",
        notifications_sent_stages=[],
        # correlation
        related_incident_ids=[],
        root_cause_incident_id=None,
        correlation_reason="",
        # injection control flags
        pre_populated_anomalies=False,
        force_human_review=False,
        fast_recovery=False,
        # trace
        trace=[],
    )


def append_trace(state: IncidentState, agent: str, action: str, detail: str = "") -> IncidentState:
    """Append an execution trace entry and return the updated state."""
    from datetime import datetime, timezone
    entry = {
        "agent":     agent,
        "action":    action,
        "detail":    detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage":     state.get("lifecycle_stage", ""),
    }
    state["trace"] = state.get("trace", []) + [entry]
    return state
