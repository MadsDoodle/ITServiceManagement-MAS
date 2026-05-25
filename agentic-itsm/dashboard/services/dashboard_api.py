"""
Dashboard API layer — reads from the agentic-itsm SQLite state DB
and log files to feed the Streamlit dashboard pages.
All data access for the dashboard goes through here.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.config import config
from services.log_service import read_log_file, get_workflow_summary
from services.monitoring_service import (
    fetch_health,
    fetch_metrics,
    fetch_services,
    fetch_incidents,
    fetch_deployments,
)


# ── Incident state DB ─────────────────────────────────────────────────────────

def _get_db_conn():
    return sqlite3.connect(config.STATE_DB_PATH, check_same_thread=False)


def init_state_db():
    """Create tables if they don't exist."""
    conn = _get_db_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id     TEXT NOT NULL,
            workflow_run_id TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            completed_at    TEXT,
            severity        TEXT,
            incident_type   TEXT,
            ai_confidence   REAL,
            escalation_required INTEGER DEFAULT 0,
            github_issue_number INTEGER,
            github_issue_url    TEXT,
            github_column       TEXT,
            notification_sent   INTEGER DEFAULT 0,
            root_cause_summary  TEXT,
            anomaly_count       INTEGER DEFAULT 0,
            state_json          TEXT,
            completed           INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def save_workflow_run(state: dict):
    """Persist a completed workflow run to the local state DB."""
    init_state_db()
    conn = _get_db_conn()
    conn.execute("""
        INSERT OR REPLACE INTO workflow_runs (
            incident_id, workflow_run_id, created_at, completed_at,
            severity, incident_type, ai_confidence, escalation_required,
            github_issue_number, github_issue_url, github_column,
            notification_sent, root_cause_summary, anomaly_count,
            state_json, completed
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        state.get("incident_id"),
        state.get("workflow_run_id"),
        state.get("created_at"),
        datetime.now(timezone.utc).isoformat(),
        state.get("severity"),
        state.get("incident_type"),
        state.get("ai_confidence", 0.0),
        1 if state.get("escalation_required") else 0,
        state.get("github_issue_number"),
        state.get("github_issue_url"),
        state.get("github_column"),
        1 if state.get("notification_sent") else 0,
        state.get("root_cause_summary"),
        len(state.get("anomalies", [])),
        json.dumps(state, default=str),
        1 if state.get("completed") else 0,
    ))
    conn.commit()
    conn.close()


def get_all_workflow_runs(limit: int = 100) -> list[dict]:
    """Return recent workflow runs from the state DB."""
    init_state_db()
    conn = _get_db_conn()
    cursor = conn.execute(
        "SELECT * FROM workflow_runs ORDER BY id DESC LIMIT ?", (limit,)
    )
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_workflow_run(incident_id: str) -> dict | None:
    """Fetch a single workflow run by incident_id."""
    init_state_db()
    conn = _get_db_conn()
    cursor = conn.execute(
        "SELECT * FROM workflow_runs WHERE incident_id = ?", (incident_id,)
    )
    cols = [d[0] for d in cursor.description]
    row  = cursor.fetchone()
    conn.close()
    if not row:
        return None
    result = dict(zip(cols, row))
    if result.get("state_json"):
        try:
            result["state"] = json.loads(result["state_json"])
        except Exception:
            result["state"] = {}
    return result


# ── Dashboard data aggregation ────────────────────────────────────────────────

def get_dashboard_summary() -> dict:
    """High-level summary card data for the main dashboard."""
    runs    = get_all_workflow_runs(limit=500)
    summary = get_workflow_summary()
    total   = len(runs)
    escalated    = sum(1 for r in runs if r.get("escalation_required"))
    with_issues  = sum(1 for r in runs if r.get("github_issue_number"))
    notifications = sum(1 for r in runs if r.get("notification_sent"))

    sev_counts: dict[str, int] = {}
    for r in runs:
        sev = r.get("severity") or "Unknown"
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    return {
        "total_workflow_runs":    total,
        "escalated_incidents":    escalated,
        "github_issues_created":  with_issues,
        "notifications_sent":     notifications,
        "severity_breakdown":     sev_counts,
        "log_summary":            summary,
    }


def get_github_activity() -> list[dict]:
    """Pull GitHub-related fields from workflow runs for the GitHub Activity page."""
    runs = get_all_workflow_runs(limit=50)
    return [
        {
            "incident_id":    r.get("incident_id"),
            "created_at":     r.get("created_at"),
            "severity":       r.get("severity"),
            "incident_type":  r.get("incident_type"),
            "issue_number":   r.get("github_issue_number"),
            "issue_url":      r.get("github_issue_url"),
            "column":         r.get("github_column"),
            "escalated":      bool(r.get("escalation_required")),
        }
        for r in runs
        if r.get("github_issue_number")
    ]


def get_live_ops_data() -> dict:
    """Fetch real-time data from the monitored ops dashboard."""
    try:
        health   = fetch_health()
        metrics  = fetch_metrics()
        services = fetch_services()
        deps     = fetch_deployments(limit=5)
        incs     = fetch_incidents(status="open", limit=10)
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "health":      health,
        "metrics":     metrics,
        "services":    services,
        "deployments": deps,
        "incidents":   incs,
    }
