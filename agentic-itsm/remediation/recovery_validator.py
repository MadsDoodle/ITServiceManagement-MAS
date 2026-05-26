"""
Recovery validator — checks whether the monitored system has stabilised.

Key behaviour:
- Checks the SPECIFIC affected service, not just global health
  (global health may be degraded from other pre-existing issues)
- When fast_recovery=True (Low tier), a single healthy service check is enough
"""
from __future__ import annotations

from services.monitoring_service import fetch_health, fetch_metrics, fetch_services
from utils.constants import HEALTH_STATUS_HEALTHY
from utils.logger import log_event, workflow_logger


def check_recovery(state: dict) -> dict:
    """
    Poll the monitored system and determine if recovery is confirmed.

    Uses the affected service from the incident anomalies as the primary signal.
    Global health is checked as a secondary signal only — pre-existing degradation
    of unrelated services does not block resolution.

    Returns: {healthy: bool, detail: str, health: dict, metrics: dict}
    """
    try:
        health   = fetch_health()
        metrics  = fetch_metrics()
        services = fetch_services()
    except Exception as exc:
        return {"healthy": False, "detail": f"Health check failed: {exc}"}

    issues: list[str] = []

    # ── Primary: check the specific affected service ──────────────────────────
    affected = _get_affected_service(state)
    if affected:
        svc_map = {s.get("service_name"): s for s in services}
        svc = svc_map.get(affected)
        if svc and svc.get("status") != HEALTH_STATUS_HEALTHY:
            issues.append(
                f"Affected service '{affected}' is still {svc.get('status')} — remediation incomplete"
            )
        # If the affected service is healthy, we consider it recovered
        # even if OTHER services are degraded (they're not our incident)
    else:
        # No specific service — fall back to global check
        overall = health.get("overall", "")
        if overall == "down":
            issues.append("System overall status is DOWN")
        elif overall == "degraded":
            degraded_services = [
                s.get("service_name") for s in services
                if s.get("status") != HEALTH_STATUS_HEALTHY
            ]
            issues.append(f"System degraded — services: {degraded_services}")

    # ── Secondary: error rate spike ───────────────────────────────────────────
    error_rate = metrics.get("error_rate_pct", 0.0)
    if error_rate > 10.0:
        issues.append(f"Error rate critically elevated at {error_rate:.1f}%")

    healthy = len(issues) == 0
    detail  = "Recovery confirmed — affected service healthy" if healthy else "; ".join(issues)

    log_event(workflow_logger, "info", "recovery_check",
              healthy=healthy, affected_service=affected, issues=issues)
    return {"healthy": healthy, "detail": detail, "health": health, "metrics": metrics}


def _get_affected_service(state: dict) -> str | None:
    anomalies = state.get("anomalies", [])
    for a in anomalies:
        svc = a.get("affected_service")
        if svc and svc not in ("system", "application", "deployment-pipeline"):
            return svc
    return None
