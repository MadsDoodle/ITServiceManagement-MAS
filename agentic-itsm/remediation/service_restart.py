"""
Service restart remediation — simulates a service restart.
Protected by service-level lock and guardrails.
"""
from __future__ import annotations

import time

from integrations.internal_ops.simulation_client import _set_service_status, restore_service_healthy
from utils.locks import remediation_lock
from utils.remediation_guard import check as guard_check, record_action
from utils.logger import log_event, workflow_logger


def remediate(state: dict) -> dict:
    anomalies = state.get("anomalies", [])
    affected  = None
    for a in anomalies:
        svc = a.get("affected_service")
        if svc and svc not in ("system", "application", "deployment-pipeline", "api-gateway"):
            affected = svc
            break
    if not affected:
        affected = "notification-service"

    allowed, reason = guard_check(affected, "restart_service", state)
    if not allowed:
        return {"success": False, "detail": f"Guardrail blocked: {reason}"}

    log_event(workflow_logger, "info", "remediation_start", strategy="restart_service", service=affected)
    try:
        with remediation_lock(affected):
            _set_service_status(affected, "degraded", "Service restart in progress — ITSM remediation")
            time.sleep(2)
            result = restore_service_healthy(affected)
            record_action(affected)
    except RuntimeError as exc:
        return {"success": False, "detail": str(exc)}

    if result.get("success"):
        detail = f"Service '{affected}' restarted and restored to healthy"
        log_event(workflow_logger, "info", "remediation_success", strategy="restart_service", service=affected)
        return {"success": True, "detail": detail}
    else:
        detail = f"Service restart failed for '{affected}': {result.get('error')}"
        log_event(workflow_logger, "warning", "remediation_failed", strategy="restart_service", error=detail)
        return {"success": False, "detail": detail}
