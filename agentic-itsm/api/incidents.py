"""
REST endpoints for incident data — thin wrapper over persistent_store.
Lets external tools and a future frontend query incident state
without going through Streamlit or direct SQLite access.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from state.persistent_store import (
    get_all_incidents,
    get_incident,
    get_open_incidents,
    get_awaiting_review,
    approve_incident,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("/")
def list_incidents(limit: int = 100, stage: str | None = None):
    return {"incidents": get_all_incidents(limit=limit, stage=stage)}


@router.get("/open")
def list_open():
    return {"incidents": get_open_incidents()}


@router.get("/awaiting-review")
def list_awaiting_review():
    return {"incidents": get_awaiting_review()}


@router.get("/{incident_id}")
def get_one(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.post("/{incident_id}/approve")
def approve(incident_id: str, approved: bool, notes: str = ""):
    ok = approve_incident(incident_id, approved=approved, notes=notes)
    if not ok:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"ok": True, "incident_id": incident_id, "approved": approved}
