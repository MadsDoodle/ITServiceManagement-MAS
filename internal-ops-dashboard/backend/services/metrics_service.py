import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.db.models import Deployment, MetricSnapshot
from backend.services.incident_service import get_open_incident_count


def get_current_metrics(db: Session) -> dict:
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "request_latency_ms": round(random.uniform(35, 180), 1),
        "error_rate_pct": round(random.uniform(0.0, 3.5), 2),
        "requests_per_min": round(random.uniform(150, 900), 0),
        "active_incidents": get_open_incident_count(db),
        "deployment_frequency_per_week": _deployments_last_week(db),
        "service_uptime_pct": round(random.uniform(96.0, 99.99), 2),
    }


def get_metric_history(db: Session, hours: int = 24) -> list[dict]:
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.timestamp >= since)
        .order_by(MetricSnapshot.timestamp.asc())
        .all()
    )
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "service_name": r.service_name,
            "request_latency_ms": r.request_latency_ms,
            "error_rate_pct": r.error_rate_pct,
            "requests_per_min": r.requests_per_min,
            "active_incidents": r.active_incidents,
        }
        for r in rows
    ]


def record_metric_snapshot(db: Session, service_name: str, **kwargs):
    snap = MetricSnapshot(timestamp=datetime.utcnow(), service_name=service_name, **kwargs)
    db.add(snap)
    db.commit()


def _deployments_last_week(db: Session) -> int:
    since = datetime.utcnow() - timedelta(days=7)
    return db.query(Deployment).filter(Deployment.timestamp >= since).count()