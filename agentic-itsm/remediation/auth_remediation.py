"""
Auth remediation — resets auth failure injection state in the monitored system.
Low-risk: only calls PATCH /health/services/auth-service and POSTs a note.
Protected by service-level remediation lock and guardrails.
"""
from __future__ import annotations

from integrations.internal_ops.simulation_client import restore_service_healthy
from utils.locks import remediation_lock
from utils.remediation_guard import check as guard_check, record_action
from utils.logger import log_event, workflow_logger


def remediate(state: dict) -> dict:
    service = "auth-service"
    allowed, reason = guard_check(service, "reset_auth", state)
    if not allowed:
        return {"success": False, "detail": f"Guardrail blocked: {reason}"}

    log_event(workflow_logger, "info", "remediation_start", strategy="reset_auth")
    try:
        with remediation_lock(service):
            result = restore_service_healthy(service)
            record_action(service)
    except RuntimeError as exc:
        return {"success": False, "detail": str(exc)}

    if result.get("success"):
        detail = "Auth-service status reset to healthy via PATCH /health/services/auth-service"
        log_event(workflow_logger, "info", "remediation_success", strategy="reset_auth")
        return {"success": True, "detail": detail}
    else:
        detail = f"Auth reset failed: {result.get('error')}"
        log_event(workflow_logger, "warning", "remediation_failed", strategy="reset_auth", error=detail)
        return {"success": False, "detail": detail}
