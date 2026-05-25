"""
Agentic ITSM — main entry point.

Modes:
  python app.py              → run one workflow cycle (useful for manual testing)
  python app.py --loop       → continuous monitoring loop
  python app.py --once       → alias for single run (same as default)
  python app.py --simulate   → inject a simulated failure, then run workflow

The loop polls the internal-ops-dashboard every POLL_INTERVAL_SECONDS,
runs the LangGraph incident workflow when anomalies are detected,
and persists each run to the local SQLite state DB.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time

import httpx

from dashboard.services.dashboard_api import init_state_db, save_workflow_run
from utils.config import config
from utils.logger import log_event, workflow_logger
from workflows.incident_workflow import run_incident_workflow

_running = True


def _signal_handler(sig, frame):
    global _running
    log_event(workflow_logger, "info", "shutdown_signal_received")
    _running = False


def _simulate_failure():
    """Hit the crash endpoint on the monitored system to trigger a detectable failure."""
    try:
        url = f"{config.OPS_DASHBOARD_URL}/simulate/crash"
        httpx.get(url, timeout=5)
    except Exception:
        pass  # 500 expected
    log_event(workflow_logger, "info", "failure_simulation_triggered")


def run_once() -> dict:
    """Execute a single workflow cycle and persist the result."""
    log_event(workflow_logger, "info", "workflow_cycle_start")
    state = run_incident_workflow()
    save_workflow_run(dict(state))
    log_event(
        workflow_logger, "info", "workflow_cycle_end",
        incident_id=state.get("incident_id"),
        anomalies=len(state.get("anomalies", [])),
        severity=state.get("severity"),
        escalated=state.get("escalation_required"),
        github_issue=state.get("github_issue_number"),
    )
    return dict(state)


def run_loop():
    """Continuously poll and run the workflow on each cycle."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    log_event(
        workflow_logger, "info", "monitoring_loop_started",
        poll_interval_seconds=config.POLL_INTERVAL_SECONDS,
        target=config.OPS_DASHBOARD_URL,
    )

    while _running:
        try:
            run_once()
        except Exception as exc:
            log_event(workflow_logger, "error", "workflow_cycle_error", error=str(exc))

        if _running:
            log_event(
                workflow_logger, "info", "sleeping",
                seconds=config.POLL_INTERVAL_SECONDS,
            )
            # Sleep in 1s increments to allow clean shutdown
            for _ in range(config.POLL_INTERVAL_SECONDS):
                if not _running:
                    break
                time.sleep(1)

    log_event(workflow_logger, "info", "monitoring_loop_stopped")


def main():
    init_state_db()

    parser = argparse.ArgumentParser(description="Agentic ITSM Platform")
    parser.add_argument("--loop",     action="store_true", help="Run continuous monitoring loop")
    parser.add_argument("--once",     action="store_true", help="Run a single workflow cycle")
    parser.add_argument("--simulate", action="store_true", help="Inject a failure before running")
    args = parser.parse_args()

    if args.simulate:
        print("Injecting simulated failure into ops dashboard...")
        _simulate_failure()
        time.sleep(2)

    if args.loop:
        run_loop()
    else:
        # Default: single run
        state = run_once()
        print("\n" + "=" * 60)
        print(f"Incident ID   : {state.get('incident_id')}")
        print(f"Severity      : {state.get('severity') or 'N/A (no anomalies)'}")
        print(f"Type          : {state.get('incident_type') or 'N/A'}")
        print(f"Confidence    : {state.get('ai_confidence', 0):.0%}")
        print(f"Escalated     : {state.get('escalation_required')}")
        print(f"GitHub Issue  : {state.get('github_issue_url') or 'N/A'}")
        print(f"Anomalies     : {len(state.get('anomalies', []))}")
        print(f"Completed     : {state.get('completed')}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
