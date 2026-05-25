from fastapi import APIRouter, Query

from backend.services.logging_service import read_log_lines

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/")
async def get_logs(
    log_type: str = Query("app", description="app | incidents | deployment"),
    lines: int = Query(100, ge=1, le=500),
    since_minutes: int = Query(None, description="Only return entries from the last N minutes"),
):
    entries = read_log_lines(log_type=log_type, lines=lines, since_minutes=since_minutes)
    return {"log_type": log_type, "count": len(entries), "entries": entries}