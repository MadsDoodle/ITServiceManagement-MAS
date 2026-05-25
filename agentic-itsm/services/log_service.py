"""
Local log reading service — reads the agentic-itsm log files for the dashboard.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utils.config import config


def read_log_file(log_type: str = "workflow", lines: int = 200) -> list[dict]:
    """
    Read the last N lines from a named log file.
    log_type: workflow | incidents | notifications
    Returns list of parsed JSON dicts (falls back to raw text if not JSON).
    """
    log_map = {
        "workflow":      "workflow.log",
        "incidents":     "incidents.log",
        "notifications": "notifications.log",
    }
    filename = log_map.get(log_type, "workflow.log")
    path = Path(config.LOG_DIR) / filename

    if not path.exists():
        return []

    all_lines = path.read_text(errors="replace").splitlines()
    recent = all_lines[-lines:]

    entries = []
    for line in recent:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"message": line, "timestamp": datetime.now(timezone.utc).isoformat()})
    return entries


def get_workflow_summary() -> dict:
    """Aggregate counts from the workflow log for the dashboard summary."""
    entries = read_log_file("workflow", lines=500)
    events = [e.get("event", "") for e in entries]
    return {
        "total_log_entries":    len(entries),
        "anomaly_detections":   events.count("anomaly_detection_complete"),
        "llm_calls":            events.count("llm_call_complete"),
        "github_issues_created": events.count("github_issue_created"),
        "notifications_sent":   events.count("gmail_sent"),
        "errors":               sum(1 for e in entries if e.get("level") == "ERROR"),
    }
