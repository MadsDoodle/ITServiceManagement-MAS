"""
Latency remediation — clears artificial latency from the monitored system.
Protected by service-level lock and guardrails.
"""
from __future__ import annotations

from integrations.internal_ops.simulation_client import restore_service_healthy
from utils.locks import remediation_lock
from utils.remediation_guard import check as guard_check, record_action
from utils.logger import log_event, workflow_logger


def remediate(state: dict) -> dict:
    service = "api-gateway"
    allowed, reason = guard_check(service, "clear_latency", state)
    if not allowed:
        return {"success": False, "detail": f"Guardrail blocked: {reason}"}

    log_event(workflow_logger, "info", "remediation_start", strategy="clear_latency")
    try:
        with remediation_lock(service):
            result = restore_service_healthy(service)
            record_action(service)
    except RuntimeError as exc:
        return {"success": False, "detail": str(exc)}

    if result.get("success"):
        detail = "API gateway latency annotation cleared — service marked healthy"
        log_event(workflow_logger, "info", "remediation_success", strategy="clear_latency")
        return {"success": True, "detail": detail}
    else:
        detail = f"Latency clear failed: {result.get('error')}"
        log_event(workflow_logger, "warning", "remediation_failed", strategy="clear_latency", error=detail)
        return {"success": False, "detail": detail}
