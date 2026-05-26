"""
Agentic ITSM — main entry point.

Modes:
  python app.py              → single detection + open incident refresh
  python app.py --loop       → continuous monitoring loop
  python app.py --simulate   → inject a failure, then run
  python app.py --dashboard  → start the Streamlit dashboard

The loop polls the internal-ops-dashboard every POLL_INTERVAL_SECONDS,
runs the LangGraph incident workflow when anomalies are detected,
and continuously re-evaluates open incidents.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

from state.persistent_store import init_db
from utils.config import config
from utils.logger import log_event, workflow_logger


def main():
    init_db()

    parser = argparse.ArgumentParser(description="Agentic ITSM Platform")
    parser.add_argument("--loop",      action="store_true",
                        help="Run continuous monitoring loop")
    parser.add_argument("--once",      action="store_true",
                        help="Run a single detection + refresh cycle")
    parser.add_argument("--simulate",  action="store_true",
                        help="Inject a failure before running")
    parser.add_argument("--dashboard", action="store_true",
                        help="Start the Streamlit dashboard")
    parser.add_argument("--api",       action="store_true",
                        help="Start the FastAPI SSE sidecar")
    args = parser.parse_args()

    if args.dashboard:
        _start_dashboard()
        return

    if args.api:
        _start_api()
        return

    if args.simulate:
        _inject_failure()
        time.sleep(2)

    if args.loop:
        # Start watchdog as daemon before the loop
        import services.watchdog_service as watchdog
        watchdog.start()

        from workflows.monitoring_loop import run_loop
        run_loop()

        watchdog.stop()
    else:
        from workflows.monitoring_loop import run_once
        run_once()
        print("Single detection cycle complete. Use --loop for continuous monitoring.")


def _inject_failure():
    from integrations.internal_ops.simulation_client import inject_crash
    print("Injecting simulated failure into ops dashboard...")
    result = inject_crash()
    log_event(workflow_logger, "info", "failure_simulation_triggered", result=result)


def _start_api():
    import os
    port = str(config.API_PORT)
    print(f"Starting Agentic ITSM SSE/REST API on port {port}...")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "api.app:app",
        "--port", port, "--host", "0.0.0.0",
    ])


def _start_dashboard():
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    port = str(config.DASHBOARD_PORT)
    print(f"Starting Agentic ITSM dashboard on port {port}...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", dashboard_path,
        "--server.port", port, "--server.address", "0.0.0.0",
    ])


if __name__ == "__main__":
    main()
