"""
Failure injection client — calls the internal-ops-dashboard /simulate/* and
/auth/simulate-failure endpoints to inject real failures into the monitored system.
Also sets SIMULATE_FAILURES / SIMULATE_LATENCY via PATCH /health/services/* 
and direct API calls when the env-var path is not available at runtime.
"""
from __future__ import annotations

import random
from typing import Optional

import httpx

from utils.config import config
from utils.constants import (
    FAILURE_AUTH_FAILURE,
    FAILURE_BAD_JSON,
    FAILURE_CRASH,
    FAILURE_DEPLOY_FAILURE,
    FAILURE_LATENCY_SPIKE,
    FAILURE_RANDOM,
    FAILURE_SERVICE_DEGRADED,
    FAILURE_SERVICE_DOWN,
    FAILURE_TIMEOUT,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_DOWN,
)
from utils.logger import log_event, workflow_logger


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=config.OPS_DASHBOARD_URL,
        headers={"X-API-Key": config.OPS_API_KEY},
        timeout=10.0,
    )


def inject_auth_failure() -> dict:
    """Trigger /auth/simulate-failure — always returns 503, writes CRITICAL log."""
    try:
        with _client() as c:
            r = c.post("/auth/simulate-failure")
        # 503 is expected — that IS the failure
        log_event(workflow_logger, "info", "failure_injected", type="auth_failure", status=r.status_code)
        # Also mark auth-service as degraded so monitoring detects it
        _set_service_status("auth-service", HEALTH_STATUS_DEGRADED,
                             "Auth failure injected by ITSM developer console")
        return {"success": True, "type": "auth_failure", "status_code": r.status_code}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def inject_latency_spike(ms: int = 4000) -> dict:
    """
    Inject a latency spike that the monitoring loop can actually detect.
    Two-pronged:
      1. Hit /simulate/latency to create a real slow response
      2. Mark api-gateway as degraded so detect_anomalies() picks it up via
         the service-status check (the /metrics/ latency value is randomised
         and won't reliably exceed the threshold from a single simulate call)
    """
    result: dict = {"success": True, "type": "latency_spike", "ms": ms}
    try:
        with httpx.Client(base_url=config.OPS_DASHBOARD_URL, timeout=ms / 1000 + 5) as c:
            r = c.get(f"/simulate/latency?ms={ms}")
        result["status_code"] = r.status_code
    except Exception as exc:
        # Timeout is fine — the endpoint deliberately blocks
        result["status_code"] = "timeout"

    # Mark api-gateway degraded so monitoring detects it
    svc_result = _set_service_status(
        "api-gateway",
        HEALTH_STATUS_DEGRADED,
        f"Latency spike injected ({ms}ms artificial delay) — ITSM developer console",
    )
    result["service_patched"] = svc_result.get("success", False)

    log_event(workflow_logger, "info", "failure_injected", type="latency_spike", ms=ms)
    return result


def inject_service_degraded(service_name: str = "auth-service") -> dict:
    """Mark a service as degraded via PATCH /health/services/{name}."""
    result = _set_service_status(service_name, HEALTH_STATUS_DEGRADED,
                                  "Service degraded — injected by ITSM developer console")
    log_event(workflow_logger, "info", "failure_injected", type="service_degraded", service=service_name)
    return result


def inject_service_down(service_name: str = "notification-service") -> dict:
    """Mark a service as down via PATCH /health/services/{name}."""
    result = _set_service_status(service_name, HEALTH_STATUS_DOWN,
                                  "Service down — injected by ITSM developer console")
    log_event(workflow_logger, "info", "failure_injected", type="service_down", service=service_name)
    return result


def inject_deployment_failure() -> dict:
    """Create a failed deployment record in the monitored system."""
    try:
        with _client() as c:
            # Create a pending deploy
            r = c.post("/deployments/", json={
                "version":     "v1.4.0-test",
                "commit_ref":  "injected-fail-001",
                "deployed_by": "itsm-failure-injector",
                "notes":       "Injected deployment failure for ITSM testing",
            })
            r.raise_for_status()
            dep_id = r.json().get("deployment_id")
            # Mark it failed
            if dep_id:
                c.patch(f"/deployments/{dep_id}", json={
                    "status":           "failed",
                    "duration_seconds": 12.0,
                    "notes":            "Health check failed post-deploy — injected for ITSM testing",
                })
        log_event(workflow_logger, "info", "failure_injected", type="deployment_failure", dep_id=dep_id)
        return {"success": True, "type": "deployment_failure", "deployment_id": dep_id}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def inject_crash() -> dict:
    """
    Hit /simulate/crash and also mark api-gateway degraded so
    detect_anomalies() has a persistent signal to detect on the next poll.
    """
    try:
        with httpx.Client(base_url=config.OPS_DASHBOARD_URL, timeout=5) as c:
            try:
                c.get("/simulate/crash")
            except Exception:
                pass  # 500 is expected
    except Exception:
        pass

    # Persistent signal for the monitoring loop
    _set_service_status(
        "api-gateway",
        HEALTH_STATUS_DEGRADED,
        "Crash injected — ITSM developer console",
    )
    log_event(workflow_logger, "info", "failure_injected", type="crash")
    return {"success": True, "type": "crash"}


def inject_bad_json() -> dict:
    """Hit /simulate/bad-json."""
    try:
        with _client() as c:
            r = c.get("/simulate/bad-json")
        log_event(workflow_logger, "info", "failure_injected", type="bad_json", status=r.status_code)
        return {"success": True, "type": "bad_json", "status_code": r.status_code}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def inject_random_failure() -> dict:
    """Pick a random low-severity failure scenario."""
    scenarios = [
        FAILURE_AUTH_FAILURE,
        FAILURE_LATENCY_SPIKE,
        FAILURE_SERVICE_DEGRADED,
        FAILURE_CRASH,
    ]
    chosen = random.choice(scenarios)
    return inject_by_type(chosen)


def inject_by_type(failure_type: str, **kwargs) -> dict:
    dispatch = {
        FAILURE_AUTH_FAILURE:     inject_auth_failure,
        FAILURE_LATENCY_SPIKE:    lambda: inject_latency_spike(kwargs.get("ms", 4000)),
        FAILURE_SERVICE_DEGRADED: lambda: inject_service_degraded(kwargs.get("service", "auth-service")),
        FAILURE_SERVICE_DOWN:     lambda: inject_service_down(kwargs.get("service", "notification-service")),
        FAILURE_DEPLOY_FAILURE:   inject_deployment_failure,
        FAILURE_CRASH:            inject_crash,
        FAILURE_BAD_JSON:         inject_bad_json,
        FAILURE_RANDOM:           inject_random_failure,
    }
    fn = dispatch.get(failure_type)
    if fn is None:
        return {"success": False, "error": f"Unknown failure type: {failure_type}"}
    return fn()


# ── Recovery helpers ──────────────────────────────────────────────────────────

def restore_service_healthy(service_name: str) -> dict:
    """Mark a service healthy — called by remediation."""
    result = _set_service_status(service_name, "healthy",
                                  "Service restored by Agentic ITSM remediation")
    log_event(workflow_logger, "info", "service_restored", service=service_name)
    return result


def _set_service_status(service_name: str, status: str, notes: str = "") -> dict:
    # Strip non-ASCII characters from notes — some older SQLite/FastAPI builds
    # can 500 on emoji in query string parameters
    safe_notes = notes.encode("ascii", errors="ignore").decode("ascii").strip()
    try:
        with _client() as c:
            r = c.patch(
                f"/health/services/{service_name}",
                params={"status": status, "notes": safe_notes},
            )
            r.raise_for_status()
        return {"success": True, "service": service_name, "status": status}
    except Exception as exc:
        return {"success": False, "service": service_name, "error": str(exc)}
