"""
FastAPI sidecar application.

Exposes:
  GET  /events/stream          — SSE lifecycle event stream
  GET  /api/incidents/         — incident list (REST)
  GET  /api/incidents/{id}     — single incident
  POST /api/incidents/{id}/approve — human review decision
  GET  /health                 — sidecar health check

Start alongside the monitoring loop:
  uvicorn api.app:app --port 8503
or via:
  python app.py --api
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.events import router as events_router
from api.incidents import router as incidents_router
from state.persistent_store import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Agentic ITSM — SSE & REST API",
    version="1.0.0",
    description="Real-time event stream and incident REST API for the Agentic ITSM platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(incidents_router)


@app.get("/health", tags=["root"])
def health():
    return {"status": "running", "service": "agentic-itsm-api"}
