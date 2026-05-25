import random

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.utils.config import config
from backend.utils.logger import app_logger, log_structured

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str
    password: str


@router.post("/token")
async def get_token(body: AuthRequest):
    """Intentionally simple auth — designed to be fault-injectable for ITSM testing."""
    if config.SIMULATE_FAILURES and random.random() < config.FAILURE_RATE:
        log_structured(app_logger, "error", "auth_simulated_failure", username=body.username)
        raise HTTPException(status_code=503, detail="Auth service unavailable (simulated failure)")

    if body.username == "admin" and body.password == "admin123":
        log_structured(app_logger, "info", "auth_success", username=body.username)
        return {"token": config.API_KEY, "username": body.username, "role": "admin"}

    log_structured(app_logger, "warning", "auth_failed", username=body.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/validate")
async def validate_token(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != config.API_KEY:
        log_structured(app_logger, "warning", "token_validation_failed")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return {"valid": True, "role": "admin"}


@router.post("/simulate-failure")
async def trigger_auth_failure():
    """Deliberately breaks auth — for testing ITSM escalation on auth failures."""
    log_structured(app_logger, "critical", "auth_failure_manually_triggered")
    raise HTTPException(status_code=503, detail="Auth failure injected for ITSM testing")