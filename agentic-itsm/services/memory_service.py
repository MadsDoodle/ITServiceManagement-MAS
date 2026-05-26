"""
Operational Memory Service — turns the incident history database into
adaptive intelligence for risk scoring and RCA.

Instead of treating every incident as isolated, this service queries past
outcomes to answer: How often does this service fail? Does this remediation
strategy work for this service? Is this a known recurring pattern?
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from utils.logger import log_event, workflow_logger

_DEFAULT_LOOKBACK_DAYS = 14


def service_stability_score(
    service_name: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> float:
    """
    Returns a 0.0–0.8 instability score for a service.
    0.0 = stable (no recent incidents)
    0.8 = very unstable (5+ incidents in the lookback window)
    Capped at 0.8 so it can't dominate the full risk score on its own.
    """
    from state.persistent_store import get_incidents_by_service_window
    since     = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    incidents = get_incidents_by_service_window(service_name, since)
    count     = len(incidents)
    score     = min(count * 0.15, 0.80)
    log_event(workflow_logger, "debug", "memory_stability_score",
              service=service_name, count=count, score=round(score, 2))
    return score


def strategy_success_rate(
    strategy: str,
    service_name: str,
) -> Optional[float]:
    """
    Returns the historical success rate (0.0–1.0) of a strategy for a service.
    Returns None if there is no historical data.
    """
    from state.persistent_store import get_all_incidents
    incidents = get_all_incidents(limit=500)
    relevant  = [
        i for i in incidents
        if i.get("remediation_strategy") == strategy
        and _incident_affects_service(i, service_name)
        and i.get("remediation_attempted")
    ]
    if not relevant:
        return None
    successes = sum(1 for i in relevant if i.get("remediation_succeeded"))
    rate      = successes / len(relevant)
    log_event(workflow_logger, "debug", "memory_strategy_rate",
              strategy=strategy, service=service_name,
              rate=round(rate, 2), sample=len(relevant))
    return rate


def recurring_pattern_summary(
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> dict:
    """
    Returns aggregated pattern data for the Operational Memory dashboard page.
    {
        total_incidents,
        lookback_days,
        top_incident_types:     [{type, count}],
        top_unstable_services:  [{service, count}],
        most_failed_strategies: [{strategy, failures}],
    }
    """
    from state.persistent_store import get_all_incidents
    incidents = get_all_incidents(limit=1000)
    since     = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    recent: list[dict] = []
    for inc in incidents:
        try:
            ts = datetime.fromisoformat(inc.get("created_at") or "")
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= since:
                recent.append(inc)
        except Exception:
            pass

    type_counts: dict[str, int] = {}
    for inc in recent:
        t = inc.get("incident_type") or "Unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    service_counts: dict[str, int] = {}
    for inc in recent:
        state = inc.get("state") or {}
        for a in state.get("anomalies") or []:
            svc = a.get("affected_service") or ""
            if svc and svc not in ("system", "application", "deployment-pipeline"):
                service_counts[svc] = service_counts.get(svc, 0) + 1

    strategy_failures: dict[str, int] = {}
    for inc in recent:
        if inc.get("remediation_attempted") and not inc.get("remediation_succeeded"):
            s = inc.get("remediation_strategy") or "unknown"
            strategy_failures[s] = strategy_failures.get(s, 0) + 1

    return {
        "total_incidents":        len(recent),
        "lookback_days":          lookback_days,
        "top_incident_types": sorted(
            [{"type": k, "count": v} for k, v in type_counts.items()],
            key=lambda x: x["count"], reverse=True,
        )[:5],
        "top_unstable_services": sorted(
            [{"service": k, "count": v} for k, v in service_counts.items()],
            key=lambda x: x["count"], reverse=True,
        )[:5],
        "most_failed_strategies": sorted(
            [{"strategy": k, "failures": v} for k, v in strategy_failures.items()],
            key=lambda x: x["failures"], reverse=True,
        ),
    }


def get_historical_context_for_rca(
    affected_services: list[str],
    incident_type: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> str:
    """
    Build a plain-text historical context string to inject into the RCA LLM prompt.
    Returns empty string if there is nothing useful to add.
    """
    lines = [f"Historical context (last {lookback_days} days):"]

    for service in affected_services:
        score = service_stability_score(service, lookback_days)
        if score > 0:
            count = int(score / 0.15)
            lines.append(
                f"- {service}: instability score {score:.2f} "
                f"(≈{count} recent incident(s))"
            )

    pattern = recurring_pattern_summary(lookback_days)
    for item in pattern["top_incident_types"]:
        if item["type"] == incident_type and item["count"] > 1:
            lines.append(
                f"- '{incident_type}' is a recurring pattern: "
                f"{item['count']} occurrences in {lookback_days} days"
            )

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _incident_affects_service(inc: dict, service_name: str) -> bool:
    state = inc.get("state") or {}
    for a in state.get("anomalies") or []:
        if a.get("affected_service") == service_name:
            return True
    return False
