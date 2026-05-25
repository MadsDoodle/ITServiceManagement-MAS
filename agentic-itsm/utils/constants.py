"""
Shared constants — severity levels, incident types, workflow columns, etc.
Single source of truth referenced by agents, services, and the dashboard.
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

# ── Service health thresholds ─────────────────────────────────────────────────
HEALTH_STATUS_HEALTHY  = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_DOWN     = "down"

# ── Escalation-trigger services ───────────────────────────────────────────────
CRITICAL_SERVICES = {"auth-service", "database", "api-gateway"}

# ── GitHub label colours ──────────────────────────────────────────────────────
LABEL_COLOURS = {
    "P1":         "d73a4a",
    "P2":         "e4e669",
    "P3":         "0075ca",
    "Low":        "cfd3d7",
    "escalated":  "b60205",
    "ai-managed": "0e8a16",
}
