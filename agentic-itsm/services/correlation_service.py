"""
Incident Correlation Service — identifies relationships between incidents.

Correlation signals (strongest → weakest):
  1. Shared commit_ref  → same deployment caused multiple incidents
  2. Same affected_service within a time window → cascading failures
  3. Overlapping anomaly types → systemic issue pattern

Results are written back to incident state so the dashboard can
render an incident relationship view and the RCA agent can include
correlation context in its reasoning.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from utils.logger import log_event, workflow_logger

_CORRELATION_WINDOW_HOURS = 2


def find_correlations(
    incident_id: str,
    commit_ref: Optional[str],
    affected_services: list[str],
    anomaly_types: list[str],
    created_at: str,
) -> dict:
    """
    Search for incidents related to the current one.

    Returns:
        {
            related_incident_ids:   list[str],
            root_cause_incident_id: str | None,
            correlation_reason:     str,
        }
    """
    from state.persistent_store import (
        get_incidents_by_commit_ref,
        get_incidents_by_service_window,
    )

    related: set[str] = set()
    root_cause_id: Optional[str] = None
    reasons: list[str] = []

    # 1. Commit-ref correlation (strongest signal)
    if commit_ref:
        for inc in get_incidents_by_commit_ref(commit_ref):
            iid = inc.get("incident_id")
            if iid and iid != incident_id:
                related.add(iid)
                reasons.append(f"Shared commit_ref '{commit_ref}' with {iid}")
                if root_cause_id is None:
                    root_cause_id = iid   # earliest (lowest id) is root cause

    # 2. Service + time-window correlation
    try:
        created_dt = datetime.fromisoformat(created_at)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        window_start = created_dt - timedelta(hours=_CORRELATION_WINDOW_HOURS)
    except Exception:
        window_start = datetime.now(timezone.utc) - timedelta(hours=_CORRELATION_WINDOW_HOURS)

    for service in affected_services:
        if service in ("system", "application", "deployment-pipeline"):
            continue
        for inc in get_incidents_by_service_window(service, window_start):
            iid = inc.get("incident_id")
            if iid and iid != incident_id:
                related.add(iid)
                reasons.append(
                    f"Same service '{service}' within "
                    f"{_CORRELATION_WINDOW_HOURS}h window"
                )

    related_list       = list(related)
    correlation_reason = "; ".join(dict.fromkeys(reasons)) if reasons else "No correlations found"

    log_event(
        workflow_logger, "info", "correlation_analysis_complete",
        incident_id=incident_id,
        related_count=len(related_list),
        root_cause=root_cause_id,
    )

    return {
        "related_incident_ids":   related_list,
        "root_cause_incident_id": root_cause_id,
        "correlation_reason":     correlation_reason,
    }
