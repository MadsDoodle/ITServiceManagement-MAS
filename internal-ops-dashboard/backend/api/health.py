import asyncio
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.health_service import (
    get_all_service_statuses,
    get_service_status,
    get_system_health_summary,
    update_service_status,
)
from backend.utils.config import config
from backend.utils.logger import app_logger, log_structured

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check(db: Session = Depends(get_db)):
    if config.SIMULATE_LATENCY:
        await asyncio.sleep(config.LATENCY_MS / 1000)

    if config.SIMULATE_FAILURES and random.random() < config.FAILURE_RATE:
        log_structured(app_logger, "error", "health_check_simulated_failure")
        raise HTTPException(status_code=503, detail="Simulated health check failure")

    summary = get_system_health_summary(db)
    log_structured(app_logger, "info", "health_check_ok", overall=summary["overall"])
    return summary


@router.get("/services")
async def list_services(db: Session = Depends(get_db)):
    return {"services": get_all_service_statuses(db)}


@router.get("/services/{service_name}")
async def get_single_service(service_name: str, db: Session = Depends(get_db)):
    svc = get_service_status(db, service_name)
    if not svc:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    return svc


@router.patch("/services/{service_name}")
async def patch_service(service_name: str, status: str, notes: str = None, db: Session = Depends(get_db)):
    """Manually override service status — useful for ITSM incident workflows."""
    valid = {"healthy", "degraded", "down"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid}")
    result = update_service_status(db, service_name, status, notes)
    log_structured(app_logger, "warning", "service_status_override", service=service_name, status=status)
    return result