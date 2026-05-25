import random
from datetime import datetime, timedelta

from backend.db.database import SessionLocal, engine
from backend.db.models import Base, Deployment, Incident, MetricSnapshot, ServiceStatus


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(Incident).count() > 0:
        db.close()
        return

    now = datetime.utcnow()

    # --- Services ---
    db.add_all([
        ServiceStatus(service_name="api-gateway",           status="healthy",  uptime_pct=99.8),
        ServiceStatus(service_name="auth-service",          status="degraded", uptime_pct=94.2, notes="Intermittent JWT validation errors post v1.3.0"),
        ServiceStatus(service_name="database",              status="healthy",  uptime_pct=99.99),
        ServiceStatus(service_name="notification-service",  status="healthy",  uptime_pct=98.5),
        ServiceStatus(service_name="metrics-collector",     status="healthy",  uptime_pct=97.1),
    ])

    # --- Deployments ---
    db.add_all([
        Deployment(deployment_id="dep-001", version="v1.0.0", status="success",     commit_ref="a1b2c3d", deployed_by="ci-bot", timestamp=now - timedelta(days=7),   notes="Initial release",                              duration_seconds=120),
        Deployment(deployment_id="dep-002", version="v1.1.0", status="success",     commit_ref="e4f5g6h", deployed_by="ci-bot", timestamp=now - timedelta(days=5),   notes="Auth module improvements",                     duration_seconds=95),
        Deployment(deployment_id="dep-003", version="v1.2.0", status="failed",      commit_ref="i7j8k9l", deployed_by="ci-bot", timestamp=now - timedelta(days=3),   notes="DB migration failed — schema mismatch on incidents table", duration_seconds=45),
        Deployment(deployment_id="dep-004", version="v1.2.1", status="success",     commit_ref="m0n1o2p", deployed_by="alice",   timestamp=now - timedelta(days=2),   notes="Hotfix: reverted broken migration",            duration_seconds=60),
        Deployment(deployment_id="dep-005", version="v1.3.0", status="rolled_back", commit_ref="q3r4s5t", deployed_by="ci-bot", timestamp=now - timedelta(hours=12), notes="Auth service latency spike post-deploy. Rollback triggered.", duration_seconds=200),
    ])

    # --- Incidents ---
    db.add_all([
        Incident(title="Auth service returning 500 errors",         severity="high",     status="resolved",      affected_service="auth-service",         timestamp=now - timedelta(days=5),    resolved_at=now - timedelta(days=4, hours=22), notes="JWT secret misconfiguration after v1.1.0 deploy.",             commit_ref="e4f5g6h"),
        Incident(title="Database connection pool exhausted",        severity="critical", status="resolved",      affected_service="database",             timestamp=now - timedelta(days=3),    resolved_at=now - timedelta(days=2, hours=20), notes="Failed migration in dep-003 left connections unreleased.",     commit_ref="i7j8k9l"),
        Incident(title="Notification service queue backlog",        severity="medium",   status="resolved",      affected_service="notification-service", timestamp=now - timedelta(days=2),    resolved_at=now - timedelta(days=1),           notes="Downstream email provider hit rate limits. Queue drained after 24h."),
        Incident(title="Auth service elevated latency",             severity="high",     status="investigating", affected_service="auth-service",         timestamp=now - timedelta(hours=13),                                                 notes="Latency spike after v1.3.0 rollout. Rollback triggered but p99 still elevated at 1.8s.", commit_ref="q3r4s5t"),
        Incident(title="API gateway intermittent 502s",             severity="medium",   status="open",          affected_service="api-gateway",          timestamp=now - timedelta(hours=2),                                                  notes="Sporadic upstream connection resets. ~2% of requests affected. Under investigation."),
    ])

    # --- Metric snapshots: last 24 hours, hourly ---
    for i in range(24):
        db.add(MetricSnapshot(
            timestamp=now - timedelta(hours=24 - i),
            service_name="api-gateway",
            request_latency_ms=round(random.uniform(40, 180), 1),
            error_rate_pct=round(random.uniform(0.1, 3.5), 2),
            requests_per_min=round(random.uniform(200, 900), 0),
            active_incidents=random.randint(0, 3),
        ))

    db.commit()
    db.close()
    print("[seed] Database seeded.")