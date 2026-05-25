"""
Deterministic monitoring service — polls the internal-ops-dashboard and
returns structured anomaly objects. No LLM involved.
"""
from __future__ import annotations

import time
from typing import Optional

import httpx

from utils.config import config
from utils.constants import (
    HEALTH_STATUS_DOWN,
    HEALTH_STATUS_DEGRADED,
)
from utils.logger import log_event, workflow_logger


_client: Optional[httpx.Client] = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            base_url=config.OPS_DASHBOARD_URL,
            headers={"X-API-Key": config.OPS_API_KEY},
            timeout=10.0,
        )
    return _client


# ── Raw data fetchers ─────────────────────────────────────────────────────────

def fetch_health() -> dict:
    try:
        r = _get_client().get("/health/")
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log_event(workflow_logger, "error", "health_fetch_failed", error=str(exc))
        return {"overall": "down", "error": str(exc)}


def fetch_services() -> list[dict]:
    try:
        r = _get_client().get("/health/services")
        r.raise_for_status()
        return r.json().get("services", [])
    except Exception as exc:
        log_event(workflow_logger, "error", "services_fetch_failed", error=str(exc))
        return []


def fetch_metrics() -> dict:
    try:
        r = _get_client().get("/metrics/")
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log_event(workflow_logger, "error", "metrics_fetch_failed", error=str(exc))
        return {}


def fetch_logs(lines: int = 100, since_minutes: int = 15) -> list[dict]:
    try:
        r = _get_client().get(
            "/logs/",
            params={"log_type": "app", "lines": lines, "since_minutes": since_minutes},
        )
        r.raise_for_status()
        return r.json().get("entries", [])
    except Exception as exc:
        log_event(workflow_logger, "error", "logs_fetch_failed", error=str(exc))
        return []


def fetch_deployments(limit: int = 10) -> list[dict]:
    try:
        r = _get_client().get("/deployments/", params={"limit": limit})
        r.raise_for_status()
        return r.json().get("deployments", [])
    except Exception as exc:
        log_event(workflow_logger, "error", "deployments_fetch_failed", error=str(exc))
        return []


def fetch_incidents(status: str = "open", limit: int = 20) -> list[dict]:
    try:
        r = _get_client().get("/incidents/", params={"status": status, "limit": limit})
        r.raise_for_status()
        return r.json().get("incidents", [])
    except Exception as exc:
        log_event(workflow_logger, "error", "incidents_fetch_failed", error=str(exc))
        return []


# ── Anomaly detection (pure deterministic logic) ──────────────────────────────

def detect_anomalies(
    health: dict,
    metrics: dict,
    services: list[dict],
    deployments: list[dict],
    logs: list[dict],
) -> list[dict]:
    """
    Rule-based anomaly detection.
    Returns a list of anomaly dicts each with keys:
      type, description, affected_service, severity_hint, evidence
    """
    anomalies: list[dict] = []

    # 1. Overall health check
    overall = health.get("overall", "")
    if overall in (HEALTH_STATUS_DOWN, HEALTH_STATUS_DEGRADED):
        anomalies.append({
            "type":             "health_check_failure",
            "description":      f"System health reported as '{overall}'",
            "affected_service": "system",
            "severity_hint":    "P1" if overall == HEALTH_STATUS_DOWN else "P2",
            "evidence":         {"overall": overall},
        })

    # 2. Individual service status
    for svc in services:
        status = svc.get("status", "")
        if status == HEALTH_STATUS_DOWN:
            anomalies.append({
                "type":             "service_down",
                "description":      f"Service '{svc['service_name']}' is DOWN",
                "affected_service": svc["service_name"],
                "severity_hint":    "P1",
                "evidence":         svc,
            })
        elif status == HEALTH_STATUS_DEGRADED:
            anomalies.append({
                "type":             "service_degraded",
                "description":      f"Service '{svc['service_name']}' is DEGRADED (uptime {svc.get('uptime_pct', '?')}%)",
                "affected_service": svc["service_name"],
                "severity_hint":    "P2",
                "evidence":         svc,
            })

    # 3. Latency threshold
    latency = metrics.get("request_latency_ms", 0.0)
    if latency > config.LATENCY_THRESHOLD_MS:
        anomalies.append({
            "type":             "high_latency",
            "description":      f"Request latency {latency}ms exceeds threshold {config.LATENCY_THRESHOLD_MS}ms",
            "affected_service": "api-gateway",
            "severity_hint":    "P2",
            "evidence":         {"latency_ms": latency, "threshold_ms": config.LATENCY_THRESHOLD_MS},
        })

    # 4. Error rate threshold
    error_rate = metrics.get("error_rate_pct", 0.0)
    if error_rate > config.ERROR_RATE_THRESHOLD_PCT:
        anomalies.append({
            "type":             "high_error_rate",
            "description":      f"Error rate {error_rate}% exceeds threshold {config.ERROR_RATE_THRESHOLD_PCT}%",
            "affected_service": "api-gateway",
            "severity_hint":    "P2",
            "evidence":         {"error_rate_pct": error_rate, "threshold_pct": config.ERROR_RATE_THRESHOLD_PCT},
        })

    # 5. Failed / rolled-back deployments in the last batch
    for dep in deployments[:5]:
        if dep.get("status") in ("failed", "rolled_back"):
            anomalies.append({
                "type":             "deployment_failure",
                "description":      f"Deployment {dep['deployment_id']} ({dep['version']}) has status '{dep['status']}'",
                "affected_service": "deployment-pipeline",
                "severity_hint":    "P2",
                "evidence":         dep,
            })

    # 6. Error/critical keywords in recent logs
    error_log_count = sum(
        1 for entry in logs
        if isinstance(entry, dict) and entry.get("level", "").lower() in ("error", "critical")
    )
    if error_log_count >= 5:
        anomalies.append({
            "type":             "log_error_spike",
            "description":      f"{error_log_count} error/critical log entries in the last 15 minutes",
            "affected_service": "application",
            "severity_hint":    "P3",
            "evidence":         {"error_log_count": error_log_count},
        })

    log_event(
        workflow_logger, "info", "anomaly_detection_complete",
        anomaly_count=len(anomalies),
        types=[a["type"] for a in anomalies],
    )
    return anomalies
