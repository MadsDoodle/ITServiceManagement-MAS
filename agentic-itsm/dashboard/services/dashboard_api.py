"""
Dashboard API — all data access for the Streamlit dashboard.
Reads from: persistent incident store, log files, and live ops endpoints.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from state.persistent_store import (
    init_db,
    get_all_incidents,
    get_open_incidents,
    get_awaiting_review,
    get_incident,
    approve_incident,
    save_workflow_run,
)
from services.log_service import read_log_file, get_workflow_summary
from services.monitoring_service import (
    fetch_health,
    fetch_metrics,
    fetch_services,
    fetch_incidents,
    fetch_deployments,
)

# Re-export for legacy compat
__all__ = [
    "init_state_db",
    "save_workflow_run",
    "get_all_workflow_runs",
    "get_workflow_run",
    "get_dashboard_summary",
    "get_github_activity",
    "get_live_ops_data",
    "get_all_incidents",
    "get_open_incidents",
    "get_awaiting_review",
    "approve_incident",
]


def init_state_db():
    init_db()


def get_all_workflow_runs(limit: int = 200) -> list[dict]:
    """Return incidents for the legacy incident feed / exec trace pages."""
    return get_all_incidents(limit=limit)


def get_workflow_run(incident_id: str) -> dict | None:
    return get_incident(incident_id)


def get_dashboard_summary() -> dict:
    incidents = get_all_incidents(limit=500)
    total     = len(incidents)
    escalated = sum(1 for i in incidents if i.get("escalation_required"))
    with_gh   = sum(1 for i in incidents if i.get("github_issue_number"))
    notified  = sum(1 for i in incidents if i.get("notification_sent"))
    resolved  = sum(1 for i in incidents if i.get("lifecycle_stage") == "resolved")
    open_count = sum(1 for i in incidents if i.get("lifecycle_stage") not in ("resolved", "completed"))
    remediated = sum(1 for i in incidents if i.get("remediation_succeeded"))
    awaiting  = len(get_awaiting_review())

    sev_counts: dict[str, int] = {}
    for inc in incidents:
        sev = inc.get("severity") or "Unknown"
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    stage_counts: dict[str, int] = {}
    for inc in incidents:
        st = inc.get("lifecycle_stage") or "unknown"
        stage_counts[st] = stage_counts.get(st, 0) + 1

    return {
        "total_incidents":        total,
        "open_incidents":         open_count,
        "resolved_incidents":     resolved,
        "escalated_incidents":    escalated,
        "github_issues_created":  with_gh,
        "notifications_sent":     notified,
        "remediated":             remediated,
        "awaiting_human_review":  awaiting,
        "severity_breakdown":     sev_counts,
        "stage_breakdown":        stage_counts,
        "log_summary":            get_workflow_summary(),
    }


def get_github_activity() -> list[dict]:
    incidents = get_all_incidents(limit=50)
    return [
        {
            "incident_id":  i.get("incident_id"),
            "created_at":   i.get("created_at"),
            "severity":     i.get("severity"),
            "incident_type": i.get("incident_type"),
            "issue_number": i.get("github_issue_number"),
            "issue_url":    i.get("github_issue_url"),
            "column":       i.get("github_column"),
            "escalated":    bool(i.get("escalation_required")),
            "lifecycle_stage": i.get("lifecycle_stage"),
        }
        for i in incidents
        if i.get("github_issue_number")
    ]


def get_live_ops_data() -> dict:
    try:
        return {
            "health":      fetch_health(),
            "metrics":     fetch_metrics(),
            "services":    fetch_services(),
            "deployments": fetch_deployments(limit=5),
            "incidents":   fetch_incidents(status="open", limit=10),
        }
    except Exception as exc:
        return {"error": str(exc)}
