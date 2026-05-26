from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.models import ServiceStatus


def get_all_service_statuses(db: Session) -> list[dict]:
    return [_serialize(r) for r in db.query(ServiceStatus).all()]


def get_service_status(db: Session, service_name: str) -> dict | None:
    row = db.query(ServiceStatus).filter(ServiceStatus.service_name == service_name).first()
    return _serialize(row) if row else None


def update_service_status(db: Session, service_name: str, status: str, notes: str = None) -> dict:
    row = db.query(ServiceStatus).filter(ServiceStatus.service_name == service_name).first()
    if not row:
        row = ServiceStatus(service_name=service_name)
        db.add(row)
    row.status      = status
    row.last_checked = datetime.utcnow()
    if notes is not None:
        row.notes = notes[:500] if notes else notes   # guard against oversized strings
    db.commit()
    db.refresh(row)
    return _serialize(row)


def get_system_health_summary(db: Session) -> dict:
    statuses = db.query(ServiceStatus).all()
    total = len(statuses)
    healthy = sum(1 for s in statuses if s.status == "healthy")
    degraded = sum(1 for s in statuses if s.status == "degraded")
    down = sum(1 for s in statuses if s.status == "down")

    if down > 0:
        overall = "down" if down == total else "degraded"
    elif degraded > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "total_services": total,
        "healthy": healthy,
        "degraded": degraded,
        "down": down,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _serialize(row: ServiceStatus) -> dict:
    return {
        "service_name": row.service_name,
        "status":       row.status,
        "uptime_pct":   row.uptime_pct,
        "last_checked": row.last_checked.isoformat() if row.last_checked else None,
        "notes":        row.notes,
    }