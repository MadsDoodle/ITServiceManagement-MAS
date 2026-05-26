"""
In-process event bus for real-time lifecycle event streaming.

Publishers  — agents and workflow wrappers call publish() on each
              lifecycle stage transition.
Subscribers — the SSE endpoint in api/events.py subscribes to receive
              a stream of events to forward to connected HTTP clients.

Thread-safe. Each subscriber gets its own queue so multiple browser
tabs all receive every event independently.
"""
from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone
from typing import Generator

_lock        = threading.Lock()
_subscribers: list[queue.Queue] = []

_MAX_QUEUE = 500   # max buffered events per subscriber before dropping oldest


# ── Core pub/sub ──────────────────────────────────────────────────────────────

def publish(event_type: str, payload: dict) -> None:
    """Broadcast an event to all active SSE subscribers. Non-blocking."""
    event = {
        "type":      event_type,
        "payload":   payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        dead = []
        for q in _subscribers:
            try:
                if q.qsize() >= _MAX_QUEUE:
                    try:
                        q.get_nowait()   # drop oldest to make room
                    except queue.Empty:
                        pass
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def subscribe() -> tuple[queue.Queue, callable]:
    """
    Register a new subscriber.
    Returns: (queue, unsubscribe_fn)
    Caller reads from the queue; calls unsubscribe_fn when the connection closes.
    """
    q = queue.Queue(maxsize=_MAX_QUEUE)
    with _lock:
        _subscribers.append(q)

    def unsubscribe():
        with _lock:
            if q in _subscribers:
                _subscribers.remove(q)

    return q, unsubscribe


def event_stream(timeout: float = 30.0) -> Generator[str, None, None]:
    """
    Generator that yields SSE-formatted strings.
    Yields a keep-alive comment every `timeout` seconds if no events arrive.
    Use directly in a FastAPI StreamingResponse.
    """
    q, unsub = subscribe()
    try:
        while True:
            try:
                event = q.get(timeout=timeout)
                data  = json.dumps(event, default=str)
                yield f"data: {data}\n\n"
            except queue.Empty:
                yield ": keep-alive\n\n"   # SSE comment prevents connection timeout
    finally:
        unsub()


# ── Typed convenience publishers ─────────────────────────────────────────────

def publish_lifecycle_transition(
    incident_id: str,
    from_stage: str,
    to_stage: str,
    agent: str,
    detail: str = "",
) -> None:
    publish("lifecycle_transition", {
        "incident_id": incident_id,
        "from_stage":  from_stage,
        "to_stage":    to_stage,
        "agent":       agent,
        "detail":      detail,
    })


def publish_remediation_event(
    incident_id: str,
    strategy: str,
    success: bool,
    detail: str = "",
) -> None:
    publish("remediation_event", {
        "incident_id": incident_id,
        "strategy":    strategy,
        "success":     success,
        "detail":      detail,
    })


def publish_new_incident(
    incident_id: str,
    severity: str,
    incident_type: str,
) -> None:
    publish("new_incident", {
        "incident_id":   incident_id,
        "severity":      severity,
        "incident_type": incident_type,
    })


def publish_resolution(incident_id: str, stability_checks: int) -> None:
    publish("incident_resolved", {
        "incident_id":      incident_id,
        "stability_checks": stability_checks,
    })


def publish_human_review_needed(incident_id: str, reasons: list[str]) -> None:
    publish("human_review_required", {
        "incident_id": incident_id,
        "reasons":     reasons,
    })
