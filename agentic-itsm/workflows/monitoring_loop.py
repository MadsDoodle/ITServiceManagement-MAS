"""
Continuous monitoring loop — background orchestration engine.

What this loop does every 30 seconds:
  1. Polls the ops dashboard and logs anomaly state (observability only — does NOT
     create new incidents; that is done exclusively via the dashboard injection buttons)
  2. Drives open incidents forward:
       - `monitoring` stage → run recovery health check
       - `awaiting_review` + human decided → resume workflow
  3. Writes a heartbeat so the watchdog knows it's alive
  4. Never starts two threads for the same incident simultaneously

What it does NOT do:
  - Does not auto-create incidents from detected anomalies
  - Does not call the LLM
  - Does not touch GitHub except when resuming an existing incident
"""
from __future__ import annotations

import signal
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from services.monitoring_service import (
    detect_anomalies,
    fetch_deployments,
    fetch_health,
    fetch_logs,
    fetch_metrics,
    fetch_services,
)
from state.persistent_store import (
    get_open_incidents,
    write_heartbeat,
    acquire_workflow_lock,
    release_workflow_lock,
    is_workflow_locked,
    any_workflow_locked,
    init_db,
)
from state.incident_state import IncidentState
from workflows.incident_workflow import run_incident_workflow, resume_incident_workflow
from utils.config import config
from utils.logger import log_event, workflow_logger

_running = True


# ── Signal handling ───────────────────────────────────────────────────────────

def stop():
    global _running
    _running = False


def _signal_handler(sig, frame):
    log_event(workflow_logger, "info", "shutdown_signal_received")
    stop()


# ── Detection tick — observability only ──────────────────────────────────────

def _run_detection_tick():
    """
    Poll the ops dashboard for the current anomaly state.
    ONLY logs the result — does not create incidents.
    Incidents come exclusively from dashboard injection buttons.
    """
    try:
        health      = fetch_health()
        metrics     = fetch_metrics()
        services    = fetch_services()
        logs        = fetch_logs(lines=50, since_minutes=10)
        deployments = fetch_deployments(limit=5)

        anomalies = detect_anomalies(
            health=health, metrics=metrics,
            services=services, deployments=deployments, logs=logs
        )

        # Only log at INFO if there are anomalies so the terminal stays quiet
        if anomalies:
            log_event(workflow_logger, "info", "anomaly_detection_complete",
                      anomaly_count=len(anomalies),
                      types=[a["type"] for a in anomalies],
                      note="observability only — no auto-incident")
        else:
            log_event(workflow_logger, "debug", "system_healthy_no_anomalies")

    except Exception as exc:
        log_event(workflow_logger, "error", "detection_tick_failed", error=str(exc))


# ── Open incidents tick — drives existing incidents forward ───────────────────

def _run_open_incidents_tick():
    """
    For every open incident:
    - If it's in `monitoring` AND not locked → run recovery validation
    - If it's in `awaiting_review` AND human has decided AND not locked → resume

    Uses DB-backed locks so this is safe across the loop process AND the
    Streamlit dashboard process running launch_incident() simultaneously.
    """
    if any_workflow_locked():
        log_event(workflow_logger, "debug", "open_incidents_tick_skipped",
                  reason="workflow lock held by another process or thread")
        return

    try:
        open_incidents = get_open_incidents()
        if not open_incidents:
            return

        for inc in open_incidents:
            incident_id = inc.get("incident_id", "")
            state       = inc.get("state") or {}
            stage       = inc.get("lifecycle_stage", "")

            if is_workflow_locked(incident_id):
                continue

            if stage == "monitoring":
                log_event(workflow_logger, "info", "monitoring_tick_recovery_check",
                          incident_id=incident_id)
                _resume_in_thread(incident_id, state)
                break

            elif stage == "awaiting_review":
                human_approved = inc.get("human_approved")
                if human_approved is not None:
                    log_event(workflow_logger, "info", "resuming_after_human_review",
                              incident_id=incident_id, approved=bool(human_approved))
                    state["human_approved"]          = bool(human_approved)
                    state["human_notes"]             = inc.get("human_notes", "")
                    state["paused_for_human_review"] = False
                    state["lifecycle_stage"]         = "fix_in_progress" if human_approved else "investigating"
                    _resume_in_thread(incident_id, state)
                    break

    except Exception as exc:
        log_event(workflow_logger, "error", "open_incidents_tick_failed", error=str(exc))


def _resume_in_thread(incident_id: str, state: dict) -> None:
    """Resume a workflow in a background thread with a DB lock held."""
    if not acquire_workflow_lock(incident_id):
        log_event(workflow_logger, "debug", "workflow_lock_contention",
                  incident_id=incident_id)
        return

    def _run():
        try:
            resume_incident_workflow(state)
        except Exception as exc:
            log_event(workflow_logger, "error", "resume_workflow_failed",
                      incident_id=incident_id, error=str(exc))
        finally:
            release_workflow_lock(incident_id)

    t = threading.Thread(target=_run, daemon=True, name=f"Resume-{incident_id}")
    t.start()


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop(
    poll_interval: int | None = None,
    on_tick: Callable | None = None,
):
    global _running
    _running = True

    signal.signal(signal.SIGINT,  _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Ensure the incident_locks table exists
    init_db()

    interval = poll_interval or config.POLL_INTERVAL_SECONDS

    log_event(workflow_logger, "info", "monitoring_loop_started",
              poll_interval_seconds=interval,
              target=config.OPS_DASHBOARD_URL)

    tick_count = 0
    while _running:
        tick_count += 1

        # Poll ops dashboard (observability only)
        _run_detection_tick()

        # Heartbeat
        try:
            write_heartbeat()
        except Exception:
            pass

        # Drive open incidents every 3rd tick (~90s)
        if tick_count % 3 == 0:
            _run_open_incidents_tick()

        if on_tick:
            try:
                on_tick(tick_count)
            except Exception:
                pass

        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    log_event(workflow_logger, "info", "monitoring_loop_stopped")


def run_once() -> dict:
    """Single detection + incident refresh cycle."""
    _run_detection_tick()
    _run_open_incidents_tick()
    return {}


def launch_incident(initial_state: dict) -> None:
    """
    Launch a new workflow from the dashboard injection buttons.
    Acquires a DB lock before starting so the loop process can see it.
    Raises if any workflow is currently locked.
    """
    incident_id = initial_state.get("incident_id", "?")

    if any_workflow_locked():
        raise RuntimeError(
            "Another workflow is currently running. "
            "Wait for it to complete before injecting a new incident."
        )

    if not acquire_workflow_lock(incident_id):
        raise RuntimeError(f"Could not acquire lock for {incident_id}")

    state = IncidentState(**{k: v for k, v in initial_state.items()
                             if k in IncidentState.__annotations__})

    def _run():
        try:
            run_incident_workflow(state)
        except Exception as exc:
            log_event(workflow_logger, "error", "launched_workflow_failed",
                      incident_id=incident_id, error=str(exc))
        finally:
            release_workflow_lock(incident_id)

    t = threading.Thread(target=_run, daemon=True, name=f"Workflow-{incident_id}")
    t.start()
    log_event(workflow_logger, "info", "workflow_launched_from_dashboard",
              incident_id=incident_id)
