from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import auth, deployments, health, incidents, logs, metrics
from backend.db.database import engine
from backend.db.models import Base
from backend.db.seed import seed
from backend.middleware.request_logger import RequestLoggerMiddleware
from backend.utils.config import config
from backend.utils.logger import app_logger, log_structured


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed()
    log_structured(app_logger, "info", "app_startup", env=config.ENV, debug=config.DEBUG, version="1.3.0")
    yield
    log_structured(app_logger, "info", "app_shutdown")


app = FastAPI(
    title="Internal Ops Dashboard API",
    version="1.3.0",
    description="Internal engineering operations API — target system for Agentic ITSM integration",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestLoggerMiddleware)

app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(deployments.router)
app.include_router(metrics.router)
app.include_router(auth.router)
app.include_router(logs.router)


@app.get("/", tags=["root"])
async def root():
    return {
        "service": config.APP_NAME,
        "version": "1.3.0",
        "env": config.ENV,
        "status": "running",
        "docs": "/docs",
    }


# ── Failure injection endpoints ──────────────────────────────────────────────
# These exist specifically so the future Agentic ITSM system can trigger
# known failure scenarios and validate its detection + response logic.

@app.get("/simulate/latency", tags=["simulate"])
async def simulate_latency(ms: int = 3000):
    """Introduce artificial response delay."""
    import asyncio
    await asyncio.sleep(ms / 1000)
    return {"message": f"Responded after {ms}ms artificial delay"}


@app.get("/simulate/crash", tags=["simulate"])
async def simulate_crash():
    """Force a 500 — triggers ITSM error detection."""
    log_structured(app_logger, "critical", "simulated_crash_triggered")
    raise Exception("Simulated application crash for ITSM failure testing")


@app.get("/simulate/timeout", tags=["simulate"])
async def simulate_timeout():
    """Never responds — for timeout / circuit-breaker testing."""
    import asyncio
    await asyncio.sleep(300)


@app.get("/simulate/bad-json", tags=["simulate"])
async def simulate_bad_json():
    """Returns malformed response body."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("{ broken json :::}", status_code=200)