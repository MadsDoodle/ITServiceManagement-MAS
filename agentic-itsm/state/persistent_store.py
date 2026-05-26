"""
Persistent incident store — SQLite via raw sqlite3.
Tracks the full lifecycle of every incident the system manages.
Used by the workflow, the dashboard, and the monitoring loop.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from utils.config import config
from utils.logger import log_event, workflow_logger

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.STATE_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS heartbeats (
    id          INTEGER PRIMARY KEY,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_locks (
    incident_id    TEXT PRIMARY KEY,
    locked_at      TEXT NOT NULL,
    locked_by_pid  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id               TEXT UNIQUE NOT NULL,
    workflow_run_id           TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    lifecycle_stage           TEXT NOT NULL DEFAULT 'new',
    completed                 INTEGER NOT NULL DEFAULT 0,
    completed_at              TEXT,

    -- Classification
    severity                  TEXT,
    incident_type             TEXT,
    ai_confidence             REAL DEFAULT 0.0,
    risk_score                REAL DEFAULT 0.0,

    -- Escalation
    escalation_required       INTEGER DEFAULT 0,
    escalation_reasons_json   TEXT,
    paused_for_human_review   INTEGER DEFAULT 0,
    human_approved            INTEGER,          -- NULL=pending, 1=yes, 0=no
    human_notes               TEXT DEFAULT '',
    assigned_human            TEXT DEFAULT '',

    -- Remediation
    remediation_strategy      TEXT DEFAULT 'none',
    remediation_attempted     INTEGER DEFAULT 0,
    remediation_succeeded     INTEGER DEFAULT 0,
    remediation_retries       INTEGER DEFAULT 0,

    -- Recovery
    monitoring_started_at     TEXT,
    recovery_validated        INTEGER DEFAULT 0,
    stability_checks_passed   INTEGER DEFAULT 0,

    -- GitHub
    github_issue_number       INTEGER,
    github_issue_url          TEXT,
    github_project_item_id    TEXT,
    github_column             TEXT DEFAULT 'New',

    -- Notifications
    notification_sent         INTEGER DEFAULT 0,
    notifications_sent_stages TEXT,             -- JSON list

    -- Summaries
    root_cause_summary        TEXT,
    remediation_detail        TEXT,
    anomaly_count             INTEGER DEFAULT 0,

    -- Correlation
    related_incident_ids_json TEXT,
    root_cause_incident_id    TEXT,
    correlation_reason        TEXT,

    -- Full state blob
    state_json                TEXT
);

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
);
"""


def init_db():
    """Create tables if they don't exist."""
    with _lock:
        conn = _conn()
        conn.executescript(SCHEMA)
        # Add correlation columns to existing DBs (idempotent)
        for col_def in [
            "ADD COLUMN related_incident_ids_json TEXT",
            "ADD COLUMN root_cause_incident_id TEXT",
            "ADD COLUMN correlation_reason TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE incidents {col_def}")
            except Exception:
                pass  # column already exists
        conn.commit()
        conn.close()


# ── Incident CRUD ─────────────────────────────────────────────────────────────

def upsert_incident(state: dict) -> None:
    """Insert or update an incident record from the current workflow state."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _conn()
        conn.execute("""
            INSERT INTO incidents (
                incident_id, workflow_run_id, created_at, updated_at,
                lifecycle_stage, completed, completed_at,
                severity, incident_type, ai_confidence, risk_score,
                escalation_required, escalation_reasons_json,
                paused_for_human_review, human_approved, human_notes, assigned_human,
                remediation_strategy, remediation_attempted, remediation_succeeded,
                remediation_retries,
                monitoring_started_at, recovery_validated, stability_checks_passed,
                github_issue_number, github_issue_url, github_project_item_id, github_column,
                notification_sent, notifications_sent_stages,
                root_cause_summary, remediation_detail, anomaly_count,
                related_incident_ids_json, root_cause_incident_id, correlation_reason,
                state_json
            ) VALUES (
                :incident_id, :workflow_run_id, :created_at, :updated_at,
                :lifecycle_stage, :completed, :completed_at,
                :severity, :incident_type, :ai_confidence, :risk_score,
                :escalation_required, :escalation_reasons_json,
                :paused_for_human_review, :human_approved, :human_notes, :assigned_human,
                :remediation_strategy, :remediation_attempted, :remediation_succeeded,
                :remediation_retries,
                :monitoring_started_at, :recovery_validated, :stability_checks_passed,
                :github_issue_number, :github_issue_url, :github_project_item_id, :github_column,
                :notification_sent, :notifications_sent_stages,
                :root_cause_summary, :remediation_detail, :anomaly_count,
                :related_incident_ids_json, :root_cause_incident_id, :correlation_reason,
                :state_json
            )
            ON CONFLICT(incident_id) DO UPDATE SET
                updated_at               = excluded.updated_at,
                lifecycle_stage          = excluded.lifecycle_stage,
                completed                = excluded.completed,
                completed_at             = excluded.completed_at,
                severity                 = excluded.severity,
                incident_type            = excluded.incident_type,
                ai_confidence            = excluded.ai_confidence,
                risk_score               = excluded.risk_score,
                escalation_required      = excluded.escalation_required,
                escalation_reasons_json  = excluded.escalation_reasons_json,
                paused_for_human_review  = excluded.paused_for_human_review,
                human_approved           = excluded.human_approved,
                human_notes              = excluded.human_notes,
                assigned_human           = excluded.assigned_human,
                remediation_strategy     = excluded.remediation_strategy,
                remediation_attempted    = excluded.remediation_attempted,
                remediation_succeeded    = excluded.remediation_succeeded,
                remediation_retries      = excluded.remediation_retries,
                monitoring_started_at    = excluded.monitoring_started_at,
                recovery_validated       = excluded.recovery_validated,
                stability_checks_passed  = excluded.stability_checks_passed,
                github_issue_number      = excluded.github_issue_number,
                github_issue_url         = excluded.github_issue_url,
                github_project_item_id   = excluded.github_project_item_id,
                github_column            = excluded.github_column,
                notification_sent        = excluded.notification_sent,
                notifications_sent_stages = excluded.notifications_sent_stages,
                root_cause_summary       = excluded.root_cause_summary,
                remediation_detail       = excluded.remediation_detail,
                anomaly_count            = excluded.anomaly_count,
                related_incident_ids_json = excluded.related_incident_ids_json,
                root_cause_incident_id   = excluded.root_cause_incident_id,
                correlation_reason       = excluded.correlation_reason,
                state_json               = excluded.state_json
        """, {
            "incident_id":               state.get("incident_id"),
            "workflow_run_id":            state.get("workflow_run_id"),
            "created_at":                state.get("created_at", now),
            "updated_at":                now,
            "lifecycle_stage":           state.get("lifecycle_stage", "new"),
            "completed":                 1 if state.get("completed") else 0,
            "completed_at":              now if state.get("completed") else None,
            "severity":                  state.get("severity"),
            "incident_type":             state.get("incident_type"),
            "ai_confidence":             state.get("ai_confidence", 0.0),
            "risk_score":                state.get("risk_score", 0.0),
            "escalation_required":       1 if state.get("escalation_required") else 0,
            "escalation_reasons_json":   json.dumps(state.get("escalation_reasons", [])),
            "paused_for_human_review":   1 if state.get("paused_for_human_review") else 0,
            "human_approved":            _bool_to_int(state.get("human_approved")),
            "human_notes":               state.get("human_notes", ""),
            "assigned_human":            state.get("assigned_human", ""),
            "remediation_strategy":      state.get("remediation_strategy", "none"),
            "remediation_attempted":     1 if state.get("remediation_attempted") else 0,
            "remediation_succeeded":     1 if state.get("remediation_succeeded") else 0,
            "remediation_retries":       state.get("remediation_retries", 0),
            "monitoring_started_at":     state.get("monitoring_started_at"),
            "recovery_validated":        1 if state.get("recovery_validated") else 0,
            "stability_checks_passed":   state.get("stability_checks_passed", 0),
            "github_issue_number":       state.get("github_issue_number"),
            "github_issue_url":          state.get("github_issue_url"),
            "github_project_item_id":    state.get("github_project_item_id"),
            "github_column":             state.get("github_column", "New"),
            "notification_sent":         1 if state.get("notification_sent") else 0,
            "notifications_sent_stages": json.dumps(state.get("notifications_sent_stages", [])),
            "root_cause_summary":        state.get("root_cause_summary"),
            "remediation_detail":        state.get("remediation_detail"),
            "anomaly_count":             len(state.get("anomalies", [])),
            "related_incident_ids_json": json.dumps(state.get("related_incident_ids", [])),
            "root_cause_incident_id":    state.get("root_cause_incident_id"),
            "correlation_reason":        state.get("correlation_reason"),
            "state_json":                json.dumps(state, default=str),
        })
        conn.commit()
        conn.close()


def _bool_to_int(val) -> Optional[int]:
    if val is None:
        return None
    return 1 if val else 0


def get_incident(incident_id: str) -> Optional[dict]:
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_dict(row)


def get_all_incidents(limit: int = 200, stage: str | None = None) -> list[dict]:
    conn = _conn()
    if stage:
        rows = conn.execute(
            "SELECT * FROM incidents WHERE lifecycle_stage = ? ORDER BY id DESC LIMIT ?",
            (stage, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_open_incidents() -> list[dict]:
    """Return all non-resolved, non-completed incidents for the monitoring loop."""
    conn = _conn()
    rows = conn.execute("""
        SELECT * FROM incidents
        WHERE completed = 0
          AND lifecycle_stage NOT IN ('resolved')
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_awaiting_review() -> list[dict]:
    """Incidents paused waiting for human approval."""
    conn = _conn()
    rows = conn.execute("""
        SELECT * FROM incidents
        WHERE paused_for_human_review = 1
          AND (human_approved IS NULL)
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def approve_incident(incident_id: str, approved: bool, notes: str = "") -> bool:
    """Human approves or rejects a paused incident. Returns True if found."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _conn()
        rowcount = conn.execute("""
            UPDATE incidents
               SET human_approved = ?,
                   human_notes = ?,
                   paused_for_human_review = 0,
                   updated_at = ?
             WHERE incident_id = ?
        """, (1 if approved else 0, notes, now, incident_id)).rowcount
        conn.commit()
        conn.close()
    log_event(workflow_logger, "info", "human_review_decision",
              incident_id=incident_id, approved=approved, notes=notes[:80])
    return rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("escalation_reasons_json", "notifications_sent_stages",
                "related_incident_ids_json"):
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = []
    if d.get("state_json"):
        try:
            d["state"] = json.loads(d["state_json"])
        except Exception:
            d["state"] = {}
    return d


# ── Correlation queries ───────────────────────────────────────────────────────

def get_incidents_by_commit_ref(commit_ref: str) -> list[dict]:
    """Return all incidents whose correlated deployment has this commit ref."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM incidents WHERE state_json LIKE ? ORDER BY id ASC",
        (f"%{commit_ref}%",),
    ).fetchall()
    conn.close()
    # Filter in Python to be precise
    results = []
    for r in [_row_to_dict(r) for r in rows]:
        state = r.get("state") or {}
        corr  = state.get("correlated_deployment") or {}
        if corr.get("commit_ref") == commit_ref:
            results.append(r)
    return results


def get_incidents_by_service_window(
    service_name: str,
    since,
) -> list[dict]:
    """
    Return incidents affecting service_name created after `since`.
    since: datetime with tzinfo.
    """
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM incidents WHERE created_at >= ? ORDER BY id ASC",
        (since.isoformat(),),
    ).fetchall()
    conn.close()
    results = []
    for r in [_row_to_dict(r) for r in rows]:
        state = r.get("state") or {}
        for a in state.get("anomalies") or []:
            if a.get("affected_service") == service_name:
                results.append(r)
                break
    return results


# ── Heartbeat ─────────────────────────────────────────────────────────────────

def write_heartbeat() -> None:
    """Record the current timestamp as the monitoring loop heartbeat."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _conn()
        conn.execute(
            "INSERT OR REPLACE INTO heartbeats (id, updated_at) VALUES (1, ?)", (now,)
        )
        conn.commit()
        conn.close()


def get_last_heartbeat() -> Optional[str]:
    """Return the last heartbeat ISO timestamp, or None."""
    try:
        conn = _conn()
        row  = conn.execute("SELECT updated_at FROM heartbeats WHERE id = 1").fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


# ── Cross-process workflow locks ──────────────────────────────────────────────

def acquire_workflow_lock(incident_id: str) -> bool:
    """
    Try to acquire an exclusive lock for an incident workflow.
    Returns True if acquired, False if already locked by another process.
    Stale locks (> 10 min old) are automatically cleared.
    """
    import os
    now = datetime.now(timezone.utc).isoformat()
    pid = os.getpid()
    # Clear stale locks older than 10 minutes
    with _lock:
        conn = _conn()
        conn.execute("""
            DELETE FROM incident_locks
             WHERE locked_at < datetime('now', '-10 minutes')
        """)
        try:
            conn.execute(
                "INSERT INTO incident_locks (incident_id, locked_at, locked_by_pid) VALUES (?,?,?)",
                (incident_id, now, pid),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False


def release_workflow_lock(incident_id: str) -> None:
    """Release the workflow lock for an incident."""
    with _lock:
        conn = _conn()
        conn.execute("DELETE FROM incident_locks WHERE incident_id = ?", (incident_id,))
        conn.commit()
        conn.close()


def is_workflow_locked(incident_id: str) -> bool:
    """Check if an incident currently has an active workflow lock."""
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM incident_locks WHERE incident_id = ?", (incident_id,)
    ).fetchone()
    conn.close()
    return row is not None


def any_workflow_locked() -> bool:
    """Returns True if any incident currently has a workflow lock (cross-process safe)."""
    # Clear stale first
    with _lock:
        conn = _conn()
        conn.execute("DELETE FROM incident_locks WHERE locked_at < datetime('now', '-10 minutes')")
        conn.commit()
        row = conn.execute("SELECT COUNT(*) FROM incident_locks").fetchone()
        conn.close()
    return row[0] > 0 if row else False


# ── Legacy workflow_runs table (kept for dashboard backward compat) ──────────

def save_workflow_run(state: dict) -> None:
    """Save to the legacy workflow_runs table (dashboard backward compat)."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _conn()
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
            now,
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
