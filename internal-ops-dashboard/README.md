# Internal Ops Dashboard

A lightweight internal engineering operations dashboard — built as the **monitored target system** for an Agentic ITSM platform.

## What this is

This is NOT a production SaaS product. It's a realistic-feeling internal ops tool designed to:

- experience failures
- expose operational metrics
- generate incidents  
- contain deployment bugs
- provide meaningful debugging context for AI-driven ITSM workflows

## Stack

| Layer | Tech |
|---|---|
| Frontend | Streamlit |
| Backend API | FastAPI |
| Database | SQLite (via SQLAlchemy) |
| CI | GitHub Actions |
| Container | Docker / docker-compose |

## Quick start (local)

```bash
# Install deps
pip install -r requirements.txt

# Start backend (from repo root)
uvicorn backend.main:app --reload

# Start frontend (new terminal)
streamlit run frontend/app.py
```

Backend: http://localhost:8000  
API Docs: http://localhost:8000/docs  
Dashboard: http://localhost:8501

## Docker

```bash
mkdir -p logs data
docker compose up --build
```

## Failure simulation

Flip env vars to inject failures for ITSM testing:

| Variable | Default | Effect |
|---|---|---|
| `SIMULATE_LATENCY` | `false` | Adds artificial delay to all responses |
| `SIMULATE_FAILURES` | `false` | Randomly fails requests at `FAILURE_RATE` probability |
| `LATENCY_MS` | `2000` | Delay in ms when latency simulation is on |
| `FAILURE_RATE` | `0.3` | 0.0–1.0 probability of failure |

Or hit the dedicated simulation endpoints directly:

GET /simulate/latency?ms=5000   # artificial delay
GET /simulate/crash             # forced 500
GET /simulate/timeout           # never responds
GET /simulate/bad-json          # malformed response
POST /auth/simulate-failure     # break auth service
PATCH /health/services/{name}?status=down   # force a service down

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /health/` | System health summary |
| `GET /health/services` | Per-service status |
| `GET /incidents/` | Incident list |
| `POST /incidents/` | Create incident |
| `PATCH /incidents/{id}` | Update incident |
| `GET /deployments/` | Deployment history |
| `POST /deployments/` | Trigger deployment |
| `GET /metrics/` | Current metrics |
| `GET /metrics/history` | Historical metrics |
| `GET /logs/` | Log viewer |
| `POST /auth/token` | Get auth token |

## Running tests

```bash
pytest tests/ -v
```

## Logs

Structured logs written to `logs/`:
- `logs/app.log` — API request + app events
- `logs/incidents.log` — Incident lifecycle events
- `logs/deployment.log` — Deployment events

All log lines use the format:  
`TIMESTAMP | logger | LEVEL | {json_payload}`

__init__.py files needed
Create empty __init__.py files at each of these paths:

backend/__init__.py
backend/api/__init__.py
backend/services/__init__.py
backend/db/__init__.py
backend/middleware/__init__.py
backend/utils/__init__.py
backend/mock_data/__init__.py
frontend/__init__.py
frontend/pages/__init__.py
frontend/components/__init__.py
frontend/services/__init__.py
frontend/utils/__init__.py
tests/__init__.py

All empty — just needed for Python package resolution when running uvicorn backend.main:app from the repo root.

## How to run it
bash

# 1. Clone / create repo, install deps
pip install -r requirements.txt

# 2. Create log dirs
mkdir -p logs data

# 3. Start backend (seeds DB on first run)
uvicorn backend.main:app --reload --port 8000

# 4. Start frontend (new terminal)
streamlit run frontend/app.py

# 5. Run tests
pytest tests/ -v
Backend docs: http://localhost:8000/docs
Dashboard: http://localhost:8501