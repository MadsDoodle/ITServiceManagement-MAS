# Internal Ops Dashboard

A lightweight internal engineering operations app — service health, deployments, incidents, metrics, and logs — built to act as the **monitored target system** for the Agentic ITSM platform in this repo.

> This is **not** a production SaaS product. It is intentionally small, realistic-feeling, and includes deliberate failure-injection hooks so a separate Agentic ITSM system can monitor it, detect failures, correlate incidents with deployments, open GitHub issues, send notifications, and escalate to humans.

---

## Architecture

Two processes, one SQLite DB, structured logs.

| Layer    | Tech                          | Where it runs            |
| -------- | ----------------------------- | ------------------------ |
| Backend  | FastAPI + Uvicorn             | `http://localhost:8000`  |
| Frontend | Streamlit                     | `http://localhost:8501`  |
| DB       | SQLite via SQLAlchemy ORM     | `ops_dashboard.db`       |
| Logs     | Pipe-delimited + JSON payload | `logs/`                  |
| CI       | GitHub Actions                | `.github/workflows/`     |
| Container| Docker + docker-compose       | `Dockerfile.{backend,frontend}` |

Interactive API docs: `http://localhost:8000/docs`

---

## Repository layout

```
internal-ops-dashboard/
├── backend/
│   ├── main.py                  # FastAPI app, routers, /simulate/* endpoints
│   ├── api/                     # Route handlers: health, incidents, deployments,
│   │                            #   metrics, auth, logs
│   ├── services/                # Business logic per domain
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── models.py            # 4 tables (see below)
│   │   └── seed.py              # First-boot seed data
│   ├── middleware/
│   │   └── request_logger.py    # Logs every HTTP request as JSON
│   ├── mock_data/               # Sample payloads
│   └── utils/
│       ├── config.py            # Env-driven config (failure flags live here)
│       └── logger.py            # Structured logger
├── frontend/
│   ├── app.py                   # Streamlit entry, sidebar router
│   ├── pages/                   # dashboard, incidents, deployments, metrics, logs
│   ├── components/              # alert_banner, log_viewer, navbar, status_cards
│   ├── services/api_client.py   # HTTP client for the backend
│   └── utils/formatting.py
├── tests/
├── logs/                        # app.log, incidents.log, deployment.log
├── .github/workflows/
│   ├── ci.yml                   # flake8 + pytest on push/PR
│   └── health_check.yml         # cron pings /health/ every 30 min
├── Dockerfile.backend
├── Dockerfile.frontend
├── requirements.txt
└── ops_dashboard.db
```

---

## Database schema

Four tables, all SQLite:

- **`incidents`** — `id`, `title`, `severity` (`critical`/`high`/`medium`/`low`), `status` (`open`/`investigating`/`resolved`), `affected_service`, `timestamp`, `resolved_at`, `notes`, `commit_ref`
- **`deployments`** — `id`, `deployment_id` (e.g. `dep-001`), `version`, `status` (`pending`/`success`/`failed`/`rolled_back`), `commit_ref`, `deployed_by`, `timestamp`, `notes`, `duration_seconds`
- **`service_status`** — `id`, `service_name` (unique), `status` (`healthy`/`degraded`/`down`), `uptime_pct`, `last_checked`, `notes`
- **`metric_snapshots`** — `id`, `timestamp`, `service_name`, `request_latency_ms`, `error_rate_pct`, `requests_per_min`, `active_incidents`

### Seed data (auto-loaded on first boot)

- **5 services** — `api-gateway`, `auth-service` (degraded), `database`, `notification-service`, `metrics-collector`
- **5 deployments** — `dep-001`…`dep-005`, including one `failed` (`dep-003`) and one `rolled_back` (`dep-005`, v1.3.0)
- **5 incidents** — 3 resolved, 1 `investigating`, 1 `open`. Incident #4 shares `commit_ref` `q3r4s5t` with the rolled-back deployment — that correlation is intentional and is what the ITSM agent should detect.
- **24 hourly metric snapshots** for `api-gateway`

---

## Running locally

### Prerequisites

- Python 3.11+
- (Optional) Docker + docker-compose

### Setup

```bash
# from internal-ops-dashboard/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start the backend (terminal 1)

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The DB schema is created and seeded automatically on first boot via the `lifespan` hook in `backend/main.py`.

### Start the frontend (terminal 2)

```bash
streamlit run frontend/app.py
```

### Or with Docker

A root-level `docker-compose.yml` exists in the repo. From that root:

```bash
docker-compose up --build
```

---

## Configuration (env vars)

All flags read from the environment via `backend/utils/config.py`. Nothing here needs code changes to flip the app into failure mode.

| Variable            | Default               | What it does |
| ------------------- | --------------------- | ------------ |
| `ENV`               | `development`         | Reported in `/` and startup logs |
| `DEBUG`             | `true`                | Log verbosity |
| `API_HOST`          | `0.0.0.0`             | Bind address |
| `API_PORT`          | `8000`                | Port |
| `DB_PATH`           | `ops_dashboard.db`    | SQLite file path |
| `LOG_DIR`           | `logs`                | Where log files are written |
| `API_KEY`           | `dev-secret-key-123`  | Set to a wrong value to break token validation |
| `SIMULATE_LATENCY`  | `false`               | If `true`, every request sleeps `LATENCY_MS` before responding |
| `LATENCY_MS`        | `2000`                | Artificial delay |
| `SIMULATE_FAILURES` | `false`               | If `true`, requests randomly return 503 at `FAILURE_RATE` |
| `FAILURE_RATE`      | `0.3`                 | Probability of failure (0.0–1.0) |

---

## API surface

Base URL: `http://localhost:8000` · Docs: `/docs`

### Root
- `GET /` — service identity + status

### Health — `/health`
- `GET /health/` — aggregated overall (`healthy` / `degraded` / `down`)
- `GET /health/services` — all service statuses
- `GET /health/services/{name}` — single service
- `PATCH /health/services/{name}?status=&notes=` — manual override (used by the ITSM agent to formally reflect a confirmed outage)

### Incidents — `/incidents`
- `GET /incidents/` — list, filterable by `status`, `severity`, `limit`
- `GET /incidents/{id}` — single incident
- `POST /incidents/` — create (writes `WARNING` to `logs/incidents.log`)
- `PATCH /incidents/{id}` — update status and/or append timestamped note. Setting `status=resolved` auto-sets `resolved_at`.

### Deployments — `/deployments`
- `GET /deployments/` — history (most recent first)
- `GET /deployments/latest` — most recent record
- `GET /deployments/{deployment_id}` — by string ID (e.g. `dep-003`)
- `POST /deployments/` — create in `pending` status, auto-generates `dep-{6-char hex}`
- `PATCH /deployments/{deployment_id}` — update status, duration, append notes

### Metrics — `/metrics`
- `GET /metrics/` — current snapshot. `active_incidents` is live-counted from the DB; `deployment_frequency_per_week` is live-counted; latency / error rate / RPM are randomised within realistic ranges per call.
- `GET /metrics/history?hours=24` — historical snapshots from `metric_snapshots`

### Auth — `/auth`
- `POST /auth/token` — hardcoded `admin` / `admin123` returns `dev-secret-key-123`. Intentionally weak.
- `GET /auth/validate` — validates `X-API-Key` header
- `POST /auth/simulate-failure` — always returns 503, writes `CRITICAL` log

### Logs — `/logs`
- `GET /logs/?log_type={app|incidents|deployment}&lines=100&since_minutes=` — parsed log entries

### Failure simulation — `/simulate`
Built specifically so the ITSM agent can validate its detection and recovery logic.
- `GET /simulate/latency?ms=3000` — artificial delay
- `GET /simulate/crash` — raises, returns 500, writes `CRITICAL` log
- `GET /simulate/timeout` — sleeps 300s (for timeout / circuit-breaker tests)
- `GET /simulate/bad-json` — HTTP 200 with malformed body

---

## Logging

Every entry uses:

```
TIMESTAMP | logger_name | LEVEL | {json_payload}
```

Three files in `logs/`:

- **`app.log`** — every HTTP request (via `RequestLoggerMiddleware`: method, path, status code, duration_ms), auth events, startup/shutdown, crash simulations. INFO for 2xx/3xx, WARNING for 4xx, ERROR for 5xx.
- **`incidents.log`** — incident create/update events
- **`deployment.log`** — deployment start and status update events

---

## Frontend pages

Routed via the sidebar radio in `frontend/app.py`:

1. **Dashboard** — system health summary, open incident count, current latency/error rate, service health cards for all 5 services, top 5 active incidents with expandable detail, latest deployment summary. Critical/high incidents render an alert banner at the top.
2. **Incidents** — Tab 1: filterable list with inline status update + note append on open incidents. Tab 2: create form (title, severity, affected service, notes, optional commit ref).
3. **Deployments** — Tab 1: deployment history with failed/rolled-back notes rendered as error blocks. Tab 2: manual deployment trigger form.
4. **Metrics** — 6 metric cards + 3 time-series line charts (latency, error rate, throughput) with a 1–24h window slider.
5. **Logs** — viewer with source selector, line count control, refresh, and level-based colour coding.

---

## CI / scheduled checks

- **`ci.yml`** — push to `main`/`develop` and PRs to `main`. Runs `flake8 backend/` (non-blocking; lint failures are surfaced as a signal but don't hard-fail), then `pytest tests/ -v --tb=short --cov=backend`.
- **`health_check.yml`** — cron every 30 min + manually dispatchable. `GET {API_URL}/health/`. Exits 1 if `overall == "down"`, warns on `degraded`, exits clean on `healthy`. A failing run here is a direct signal for the ITSM agent.

---

## How the Agentic ITSM system interacts with this app

The integration surface this dashboard exposes:

| Concern                          | Endpoint(s) the agent uses |
| -------------------------------- | -------------------------- |
| Detect overall degradation       | `GET /health/`             |
| Identify affected service        | `GET /health/services`     |
| Detect latency / error spikes    | `GET /metrics/`            |
| Recent incident events           | `GET /logs/?log_type=incidents&since_minutes=30` |
| Recent deployment events         | `GET /logs/?log_type=deployment&since_minutes=60` |
| Correlate incident ↔ deployment  | Match `commit_ref` between `incidents` and `deployments` |
| Open an incident autonomously    | `POST /incidents/`         |
| Track investigation              | `PATCH /incidents/{id}`    |
| Reflect confirmed outage         | `PATCH /health/services/{name}?status=down` |
| Inject failures during testing   | `/simulate/*`, `SIMULATE_*` env flags |
| Watch CI / scheduled health      | GitHub Actions: `ci.yml`, `health_check.yml` |

### Escalate to a human when

- A `critical` incident is open, **or**
- An incident's `commit_ref` matches a recent deployment (a deploy caused the failure), **or**
- `auth-service` is involved (auth failures are high-risk), **or**
- A deployment is `failed` / `rolled_back` and a related incident is still open.

---

## Quick smoke test

```bash
curl http://localhost:8000/health/
curl http://localhost:8000/incidents/?status=open
curl http://localhost:8000/deployments/latest
curl http://localhost:8000/metrics/

# Trigger a known failure for the ITSM agent to react to
curl http://localhost:8000/simulate/crash
curl "http://localhost:8000/simulate/latency?ms=5000"
```
