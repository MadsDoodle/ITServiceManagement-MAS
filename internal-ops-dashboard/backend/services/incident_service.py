from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.models import Incident
from backend.utils.logger import incident_logger, log_structured


def get_incidents(db: Session, status: str = None, severity: str = None, limit: int = 50) -> list[dict]:
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    if severity:
        q = q.filter(Incident.severity == severity)
    return [_serialize(r) for r in q.order_by(Incident.timestamp.desc()).limit(limit).all()]


def get_incident(db: Session, incident_id: int) -> dict | None:
    row = db.query(Incident).filter(Incident.id == incident_id).first()
    return _serialize(row) if row else None


def create_incident(
    db: Session, title: str, severity: str, affected_service: str, notes: str = None, commit_ref: str = None
) -> dict:
    inc = Incident(
        title=title,
        severity=severity,
        status="open",
        affected_service=affected_service,
        timestamp=datetime.utcnow(),
        notes=notes,
        commit_ref=commit_ref,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    log_structured(
        incident_logger, "warning", "incident_created",
        incident_id=inc.id, title=title, severity=severity, service=affected_service,
    )
    return _serialize(inc)


def update_incident(db: Session, incident_id: int, status: str = None, notes: str = None) -> dict | None:
    row = db.query(Incident).filter(Incident.id == incident_id).first()
    if not row:
        return None
    if status:
        row.status = status
        if status == "resolved":
            row.resolved_at = datetime.utcnow()
    if notes:
        timestamp_note = f"\n[{datetime.utcnow().isoformat()}] {notes}"
        row.notes = (row.notes or "") + timestamp_note
    db.commit()
    db.refresh(row)
    log_structured(incident_logger, "info", "incident_updated", incident_id=incident_id, new_status=status)
    return _serialize(row)


def get_open_incident_count(db: Session) -> int:
    return db.query(Incident).filter(Incident.status != "resolved").count()


def _serialize(row: Incident) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "severity": row.severity,
        "status": row.status,
        "affected_service": row.affected_service,
        "timestamp": row.timestamp.isoformat(),
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "notes": row.notes,
        "commit_ref": row.commit_ref,
    }