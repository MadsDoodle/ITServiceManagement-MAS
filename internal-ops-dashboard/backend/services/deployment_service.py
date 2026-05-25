import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.models import Deployment
from backend.utils.logger import deployment_logger, log_structured


def get_deployments(db: Session, limit: int = 20) -> list[dict]:
    return [_serialize(r) for r in db.query(Deployment).order_by(Deployment.timestamp.desc()).limit(limit).all()]


def get_deployment(db: Session, deployment_id: str) -> dict | None:
    row = db.query(Deployment).filter(Deployment.deployment_id == deployment_id).first()
    return _serialize(row) if row else None


def get_latest_deployment(db: Session) -> dict | None:
    row = db.query(Deployment).order_by(Deployment.timestamp.desc()).first()
    return _serialize(row) if row else None


def create_deployment(
    db: Session, version: str, commit_ref: str, deployed_by: str = "ci-bot", notes: str = None
) -> dict:
    dep_id = f"dep-{uuid.uuid4().hex[:6]}"
    dep = Deployment(
        deployment_id=dep_id,
        version=version,
        status="pending",
        commit_ref=commit_ref,
        deployed_by=deployed_by,
        timestamp=datetime.utcnow(),
        notes=notes,
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    log_structured(
        deployment_logger, "info", "deployment_started",
        deployment_id=dep_id, version=version, commit_ref=commit_ref, deployed_by=deployed_by,
    )
    return _serialize(dep)


def update_deployment_status(
    db: Session, deployment_id: str, status: str, duration_seconds: float = None, notes: str = None
) -> dict | None:
    row = db.query(Deployment).filter(Deployment.deployment_id == deployment_id).first()
    if not row:
        return None
    row.status = status
    if duration_seconds is not None:
        row.duration_seconds = duration_seconds
    if notes:
        row.notes = (row.notes or "") + f"\n{notes}"
    db.commit()
    db.refresh(row)
    level = "info" if status == "success" else "error"
    log_structured(deployment_logger, level, "deployment_status_updated", deployment_id=deployment_id, status=status)
    return _serialize(row)


def _serialize(row: Deployment) -> dict:
    return {
        "id": row.id,
        "deployment_id": row.deployment_id,
        "version": row.version,
        "status": row.status,
        "commit_ref": row.commit_ref,
        "deployed_by": row.deployed_by,
        "timestamp": row.timestamp.isoformat(),
        "notes": row.notes,
        "duration_seconds": row.duration_seconds,
    }