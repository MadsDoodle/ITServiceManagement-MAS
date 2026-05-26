"""
Watchdog Service — monitors the orchestration platform itself.

Checks:
  1. Monitoring loop heartbeat — alerts if the loop has gone silent
  2. Stuck incident detection — incidents in the same stage too long
  3. Exposes get_orchestration_health() for the dashboard page

Runs as a daemon thread started from app.py --loop.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

from utils.logger import log_event, workflow_logger

# Per-stage stuck thresholds in seconds
_STAGE_TIMEOUTS: dict[str, int] = {
    "new":             300,     # 5 min
    "triage":          600,     # 10 min
    "investigating":   1800,    # 30 min
    "fix_in_progress": 1800,    # 30 min
    "awaiting_review": 86400,   # 24 h  (human review can take time)
    "monitoring":      7200,    # 2 h
}
_DEFAULT_STAGE_TIMEOUT = 3600   # 1 h fallback

_running      = False
_thread: Optional[threading.Thread] = None
_health_lock  = threading.Lock()

_last_health: dict = {
    "loop_status":     "unknown",
    "heartbeat_age_s": None,
    "stuck_incidents": [],
    "last_checked":    None,
}


def _check_health() -> None:
    from state.persistent_store import get_last_heartbeat, get_open_incidents
    from utils.config import config

    now = datetime.now(timezone.utc)

    # ── 1. Heartbeat ─────────────────────────────────────────────────────────
    hb_raw     = get_last_heartbeat()
    loop_status   = "unknown"
    heartbeat_age = None

    if hb_raw:
        try:
            hb_dt = datetime.fromisoformat(hb_raw)
            if hb_dt.tzinfo is None:
                hb_dt = hb_dt.replace(tzinfo=timezone.utc)
            heartbeat_age = (now - hb_dt).total_seconds()
            stale         = config.WATCHDOG_STALE_SECONDS
            loop_status   = "running" if heartbeat_age < stale else "stalled"
            if loop_status == "stalled":
                log_event(workflow_logger, "warning", "watchdog_loop_stalled",
                          heartbeat_age_s=heartbeat_age, threshold=stale)
        except Exception:
            loop_status = "unknown"
    else:
        loop_status = "not_started"

    # ── 2. Stuck incidents ────────────────────────────────────────────────────
    stuck = []
    try:
        for inc in get_open_incidents():
            stage       = inc.get("lifecycle_stage") or ""
            updated_str = inc.get("updated_at") or inc.get("created_at") or ""
            if not updated_str:
                continue
            try:
                updated_dt = datetime.fromisoformat(updated_str)
                if updated_dt.tzinfo is None:
                    updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                time_in_stage = (now - updated_dt).total_seconds()
                threshold     = _STAGE_TIMEOUTS.get(stage, _DEFAULT_STAGE_TIMEOUT)
                if time_in_stage > threshold:
                    stuck.append({
                        "incident_id":   inc.get("incident_id"),
                        "stage":         stage,
                        "time_in_stage_s": int(time_in_stage),
                        "threshold_s":   threshold,
                    })
                    log_event(workflow_logger, "warning", "watchdog_stuck_incident",
                              incident_id=inc.get("incident_id"),
                              stage=stage, time_in_stage_s=int(time_in_stage))
            except Exception:
                pass
    except Exception as exc:
        log_event(workflow_logger, "error", "watchdog_open_incidents_failed", error=str(exc))

    with _health_lock:
        _last_health.update({
            "loop_status":     loop_status,
            "heartbeat_age_s": heartbeat_age,
            "stuck_incidents": stuck,
            "last_checked":    now.isoformat(),
        })


def get_orchestration_health() -> dict:
    """Return latest cached health snapshot. Safe to call from any thread."""
    with _health_lock:
        return dict(_last_health)


def _watchdog_loop() -> None:
    global _running
    while _running:
        try:
            _check_health()
        except Exception as exc:
            log_event(workflow_logger, "error", "watchdog_error", error=str(exc))
        for _ in range(60):   # check every 60 s
            if not _running:
                break
            time.sleep(1)


def start() -> None:
    """Start the watchdog as a daemon thread."""
    global _running, _thread
    if _thread and _thread.is_alive():
        return
    _running = True
    _thread  = threading.Thread(
        target=_watchdog_loop, daemon=True, name="WatchdogThread"
    )
    _thread.start()
    log_event(workflow_logger, "info", "watchdog_started")


def stop() -> None:
    global _running
    _running = False
    log_event(workflow_logger, "info", "watchdog_stopped")
