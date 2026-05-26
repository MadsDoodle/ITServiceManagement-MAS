"""
Shared constants — severity levels, incident types, workflow columns,
lifecycle stages, and everything else used across the system.
Single source of truth.
"""

# ── Severity ─────────────────────────────────────────────────────────────────
SEVERITY_P1  = "P1"
SEVERITY_P2  = "P2"
SEVERITY_P3  = "P3"
SEVERITY_LOW = "Low"

SEVERITY_LEVELS = [SEVERITY_P1, SEVERITY_P2, SEVERITY_P3, SEVERITY_LOW]

# ── Incident types ────────────────────────────────────────────────────────────
INCIDENT_TYPE_DEPLOYMENT    = "Deployment Failure"
INCIDENT_TYPE_API           = "API Failure"
INCIDENT_TYPE_DATABASE      = "Database Issue"
INCIDENT_TYPE_AUTH          = "Authentication"
INCIDENT_TYPE_INFRA         = "Infrastructure"
INCIDENT_TYPE_PERFORMANCE   = "Performance"
INCIDENT_TYPE_MONITORING    = "Monitoring Alert"
INCIDENT_TYPE_OUTAGE        = "Service Outage"
INCIDENT_TYPE_CONFIGURATION = "Configuration Error"

INCIDENT_TYPES = [
    INCIDENT_TYPE_DEPLOYMENT,
    INCIDENT_TYPE_API,
    INCIDENT_TYPE_DATABASE,
    INCIDENT_TYPE_AUTH,
    INCIDENT_TYPE_INFRA,
    INCIDENT_TYPE_PERFORMANCE,
    INCIDENT_TYPE_MONITORING,
    INCIDENT_TYPE_OUTAGE,
    INCIDENT_TYPE_CONFIGURATION,
]

# ── GitHub Project workflow columns ───────────────────────────────────────────
COLUMN_NEW             = "New"
COLUMN_TRIAGE          = "Triage"
COLUMN_INVESTIGATING   = "Investigating"
COLUMN_FIX_IN_PROGRESS = "Fix In Progress"
COLUMN_MONITORING      = "Monitoring"
COLUMN_RESOLVED        = "Resolved"

WORKFLOW_COLUMNS = [
    COLUMN_NEW,
    COLUMN_TRIAGE,
    COLUMN_INVESTIGATING,
    COLUMN_FIX_IN_PROGRESS,
    COLUMN_MONITORING,
    COLUMN_RESOLVED,
]

# ── Incident lifecycle stages (internal) ─────────────────────────────────────
LIFECYCLE_NEW             = "new"
LIFECYCLE_TRIAGE          = "triage"
LIFECYCLE_INVESTIGATING   = "investigating"
LIFECYCLE_FIX_IN_PROGRESS = "fix_in_progress"
LIFECYCLE_AWAITING_REVIEW = "awaiting_review"
LIFECYCLE_MONITORING      = "monitoring"
LIFECYCLE_RESOLVED        = "resolved"

LIFECYCLE_STAGES = [
    LIFECYCLE_NEW,
    LIFECYCLE_TRIAGE,
    LIFECYCLE_INVESTIGATING,
    LIFECYCLE_FIX_IN_PROGRESS,
    LIFECYCLE_AWAITING_REVIEW,
    LIFECYCLE_MONITORING,
    LIFECYCLE_RESOLVED,
]

# Map lifecycle stage → GitHub project column
LIFECYCLE_TO_COLUMN = {
    LIFECYCLE_NEW:             COLUMN_NEW,
    LIFECYCLE_TRIAGE:          COLUMN_TRIAGE,
    LIFECYCLE_INVESTIGATING:   COLUMN_INVESTIGATING,
    LIFECYCLE_FIX_IN_PROGRESS: COLUMN_FIX_IN_PROGRESS,
    LIFECYCLE_AWAITING_REVIEW: COLUMN_INVESTIGATING,   # stays in Investigating while waiting
    LIFECYCLE_MONITORING:      COLUMN_MONITORING,
    LIFECYCLE_RESOLVED:        COLUMN_RESOLVED,
}

# ── Service health statuses ───────────────────────────────────────────────────
HEALTH_STATUS_HEALTHY  = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_DOWN     = "down"

# ── Escalation-trigger services ───────────────────────────────────────────────
CRITICAL_SERVICES = {"auth-service", "database", "api-gateway"}

# ── Remediation strategies ────────────────────────────────────────────────────
REMEDIATION_RESET_AUTH        = "reset_auth"
REMEDIATION_CLEAR_LATENCY     = "clear_latency"
REMEDIATION_RESTART_SERVICE   = "restart_service"
REMEDIATION_ROLLBACK_DEPLOY   = "rollback_deploy"
REMEDIATION_CLEAR_FAILURE_FLAGS = "clear_failure_flags"
REMEDIATION_MARK_HEALTHY      = "mark_healthy"
REMEDIATION_MANUAL            = "manual"        # human must act
REMEDIATION_NONE              = "none"

# ── Email notification stages ────────────────────────────────────────────────
NOTIF_INCIDENT_DETECTED   = "incident_detected"
NOTIF_TRIAGE_STARTED      = "triage_started"
NOTIF_INVESTIGATION_START = "investigation_started"
NOTIF_REMEDIATION_START   = "remediation_started"
NOTIF_ESCALATED           = "escalation_required"
NOTIF_MONITORING_START    = "monitoring_started"
NOTIF_RESOLVED            = "incident_resolved"

NOTIFICATION_STAGES = [
    NOTIF_INCIDENT_DETECTED,
    NOTIF_TRIAGE_STARTED,
    NOTIF_INVESTIGATION_START,
    NOTIF_REMEDIATION_START,
    NOTIF_ESCALATED,
    NOTIF_MONITORING_START,
    NOTIF_RESOLVED,
]

# Email stage → banner colour
NOTIF_BANNER_COLOURS = {
    NOTIF_INCIDENT_DETECTED:   "#0075ca",   # blue
    NOTIF_TRIAGE_STARTED:      "#e4e669",   # yellow
    NOTIF_INVESTIGATION_START: "#f0883e",   # orange
    NOTIF_REMEDIATION_START:   "#8957e5",   # purple
    NOTIF_ESCALATED:           "#d73a4a",   # red
    NOTIF_MONITORING_START:    "#0d7377",   # teal
    NOTIF_RESOLVED:            "#2da44e",   # green
}

# ── Risk thresholds ───────────────────────────────────────────────────────────
RISK_AUTO_REMEDIATE_MAX = 0.6   # risk score ≤ this → auto-remediate (no human needed)
RISK_ESCALATE_MIN       = 0.5   # risk score ≥ this → escalate (overlaps intentionally)

# ── Monitoring validation ─────────────────────────────────────────────────────
MONITORING_STABILITY_SECONDS = 300   # 5 minutes of stability before resolving
MONITORING_CHECK_INTERVAL    = 30    # re-check every 30 seconds during monitoring

# ── GitHub label colours ──────────────────────────────────────────────────────
LABEL_COLOURS = {
    "P1":         "d73a4a",
    "P2":         "e4e669",
    "P3":         "0075ca",
    "Low":        "cfd3d7",
    "escalated":  "b60205",
    "ai-managed": "0e8a16",
    "remediated": "1d76db",
    "monitoring": "0d7377",
}

# ── Failure injection scenarios ───────────────────────────────────────────────
FAILURE_AUTH_FAILURE     = "auth_failure"
FAILURE_LATENCY_SPIKE    = "latency_spike"
FAILURE_SERVICE_DEGRADED = "service_degraded"
FAILURE_SERVICE_DOWN     = "service_down"
FAILURE_DEPLOY_FAILURE   = "deployment_failure"
FAILURE_CRASH            = "crash"
FAILURE_BAD_JSON         = "bad_json"
FAILURE_TIMEOUT          = "timeout"
FAILURE_RANDOM           = "random"

FAILURE_SCENARIOS = [
    FAILURE_AUTH_FAILURE,
    FAILURE_LATENCY_SPIKE,
    FAILURE_SERVICE_DEGRADED,
    FAILURE_SERVICE_DOWN,
    FAILURE_DEPLOY_FAILURE,
    FAILURE_CRASH,
    FAILURE_BAD_JSON,
    FAILURE_TIMEOUT,
    FAILURE_RANDOM,
]
