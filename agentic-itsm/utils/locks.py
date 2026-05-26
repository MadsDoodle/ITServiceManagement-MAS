"""
Service-keyed concurrency locks and in-flight incident tracker.

Prevents:
  - Two workflows remediating the same service simultaneously
  - Duplicate incident workflows spawned for the same anomaly signature
  - GitHub race conditions on the same project item
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Optional

from utils.logger import log_event, workflow_logger

# ── Service remediation locks ─────────────────────────────────────────────────
_service_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _get_service_lock(service_name: str) -> threading.Lock:
    with _registry_lock:
        if service_name not in _service_locks:
            _service_locks[service_name] = threading.Lock()
        return _service_locks[service_name]


@contextmanager
def remediation_lock(service_name: str, timeout: float = 30.0):
    """
    Acquire the per-service remediation lock.
    Raises RuntimeError if it cannot be acquired within timeout seconds.

    Usage:
        with remediation_lock("auth-service"):
            ... do remediation ...
    """
    lock     = _get_service_lock(service_name)
    acquired = lock.acquire(timeout=timeout)
    if not acquired:
        raise RuntimeError(
            f"Could not acquire remediation lock for '{service_name}' "
            f"within {timeout}s — another remediation is already in progress"
        )
    log_event(workflow_logger, "debug", "remediation_lock_acquired", service=service_name)
    try:
        yield
    finally:
        lock.release()
        log_event(workflow_logger, "debug", "remediation_lock_released", service=service_name)


def is_service_being_remediated(service_name: str) -> bool:
    """Non-blocking check — returns True if the lock is currently held."""
    lock     = _get_service_lock(service_name)
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
        return False
    return True


# ── In-flight incident tracker ────────────────────────────────────────────────
# Prevents spawning a new workflow for an anomaly that already has an open incident.

_in_flight:   dict[str, str] = {}   # anomaly_sig → incident_id
_flight_lock  = threading.Lock()


def mark_in_flight(anomaly_sig: str, incident_id: str) -> None:
    with _flight_lock:
        _in_flight[anomaly_sig] = incident_id


def clear_in_flight(anomaly_sig: str) -> None:
    with _flight_lock:
        _in_flight.pop(anomaly_sig, None)


def get_in_flight_incident(anomaly_sig: str) -> Optional[str]:
    with _flight_lock:
        return _in_flight.get(anomaly_sig)


def is_in_flight(anomaly_sig: str) -> bool:
    with _flight_lock:
        return anomaly_sig in _in_flight
