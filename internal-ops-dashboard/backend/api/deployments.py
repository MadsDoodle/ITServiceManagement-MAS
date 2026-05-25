from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.deployment_service import (
    create_deployment,
    get_deployment,
    get_deployments,
    get_latest_deployment,
    update_deployment_status,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])


class CreateDeploymentRequest(BaseModel):
    version: str
    commit_ref: str
    deployed_by: str = "ci-bot"
    notes: str | None = None


class UpdateDeploymentRequest(BaseModel):
    status: str
    duration_seconds: float | None = None
    notes: str | None = None


@router.get("/")
async def list_deployments(limit: int = 20, db: Session = Depends(get_db)):
    return {"deployments": get_deployments(db, limit=limit)}


@router.get("/latest")
async def latest_deployment(db: Session = Depends(get_db)):
    dep = get_latest_deployment(db)
    if not dep:
        raise HTTPException(status_code=404, detail="No deployments found")
    return dep


@router.get("/{deployment_id}")
async def get_single_deployment(deployment_id: str, db: Session = Depends(get_db)):
    dep = get_deployment(db, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return dep


@router.post("/")
async def create_new_deployment(body: CreateDeploymentRequest, db: Session = Depends(get_db)):
    return create_deployment(
        db,
        version=body.version,
        commit_ref=body.commit_ref,
        deployed_by=body.deployed_by,
        notes=body.notes,
    )


@router.patch("/{deployment_id}")
async def update_deployment(deployment_id: str, body: UpdateDeploymentRequest, db: Session = Depends(get_db)):
    dep = update_deployment_status(
        db, deployment_id,
        status=body.status,
        duration_seconds=body.duration_seconds,
        notes=body.notes,
    )
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return dep