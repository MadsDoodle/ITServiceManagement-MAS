from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.incident_service import (
    create_incident,
    get_incident,
    get_incidents,
    update_incident,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncidentRequest(BaseModel):
    title: str
    severity: str
    affected_service: str
    notes: str | None = None
    commit_ref: str | None = None


class UpdateIncidentRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("/")
async def list_incidents(
    status: str = None,
    severity: str = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return {"incidents": get_incidents(db, status=status, severity=severity, limit=limit)}


@router.get("/{incident_id}")
async def get_single_incident(incident_id: int, db: Session = Depends(get_db)):
    inc = get_incident(db, incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.post("/")
async def create_new_incident(body: CreateIncidentRequest, db: Session = Depends(get_db)):
    return create_incident(
        db,
        title=body.title,
        severity=body.severity,
        affected_service=body.affected_service,
        notes=body.notes,
        commit_ref=body.commit_ref,
    )


@router.patch("/{incident_id}")
async def update_existing_incident(incident_id: int, body: UpdateIncidentRequest, db: Session = Depends(get_db)):
    inc = update_incident(db, incident_id, status=body.status, notes=body.notes)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc