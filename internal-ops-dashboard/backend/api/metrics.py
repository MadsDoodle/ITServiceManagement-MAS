from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.services.metrics_service import get_current_metrics, get_metric_history

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/")
async def current_metrics(db: Session = Depends(get_db)):
    return get_current_metrics(db)


@router.get("/history")
async def metric_history(hours: int = 24, db: Session = Depends(get_db)):
    return {"history": get_metric_history(db, hours=hours)}