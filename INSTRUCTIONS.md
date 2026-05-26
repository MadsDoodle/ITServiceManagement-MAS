# How to Start the ITSM-MAS Platform

Two systems run side by side. The **Internal Ops Dashboard** is the monitored target. The **Agentic ITSM** system monitors it, detects failures, and runs the full incident lifecycle.

---

## First-Time Setup (run once)

### Internal Ops Dashboard

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/internal-ops-dashboard
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Agentic ITSM

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Open `agentic-itsm/.env`. Everything is already filled in. The only values you might need to change:

- `OPENAI_API_KEY` — required for LLM classification and RCA. Without it the system runs on deterministic fallbacks (still functional).
- `GMAIL_SENDER` / `GMAIL_APP_PASSWORD` / `ESCALATION_EMAIL` — required for email notifications. Skip if not needed.
- `GITHUB_TOKEN` / `GITHUB_REPO_OWNER` / `GITHUB_REPO_NAME` / `GITHUB_PROJECT_NUMBER` — already configured for the MadsDoodle project board.

The GitHub Project board is already set up at:
`github.com/MadsDoodle/ITServiceManagement-MAS` → Projects → @MadsDoodle's Agentic ITSM Operations

---

## Starting the Platform

Open **4 terminal tabs**. Run each command and leave it running.

### Tab 1 — Ops Dashboard Backend (the monitored system)

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/internal-ops-dashboard
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running: http://localhost:8000/health/  
API docs: http://localhost:8000/docs

The database is created and seeded automatically on first boot — 5 services, 5 deployments (including one failed, one rolled back), and 5 incidents (2 open).

### Tab 2 — Ops Dashboard Frontend

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/internal-ops-dashboard
source venv/bin/activate
streamlit run frontend/app.py --server.port 8501
```

Open: http://localhost:8501

### Tab 3 — Agentic ITSM Monitoring Loop

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
python app.py --loop
```

This polls the ops dashboard every 30 seconds, detects anomalies, and runs the full incident lifecycle automatically. Stop with `Ctrl+C`.

### Tab 4 — Agentic ITSM Dashboard

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
streamlit run dashboard/app.py --server.port 8502
```

Open: http://localhost:8502

---

## Optional: FastAPI SSE Sidecar (real-time event stream)

If you want to consume lifecycle events over Server-Sent Events (for external tools or a future frontend):

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
python app.py --api
```

Stream endpoint: http://localhost:8503/events/stream  
Incident REST API: http://localhost:8503/api/incidents/

---

## Triggering Incidents

### Option A — Use the Failure Injection Console (recommended)

In the Agentic ITSM dashboard (`:8502`), go to **💥 Failure Injection** and click any scenario button. The monitoring loop will detect the failure on the next poll and the full incident lifecycle begins automatically.

### Option B — Inject from the command line

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
python app.py --simulate
```

This hits `/simulate/crash` on the ops dashboard and runs one detection cycle.

### Option C — Run one detection cycle manually

```bash
python app.py
```

Runs a single detect + triage cycle. Useful for testing without the loop.

---

## Port Reference

| Service | URL |
|---------|-----|
| Ops Dashboard API | http://localhost:8000 |
| Ops Dashboard API docs | http://localhost:8000/docs |
| Ops Dashboard UI | http://localhost:8501 |
| Agentic ITSM Dashboard | http://localhost:8502 |
| SSE / REST sidecar (optional) | http://localhost:8503 |

---

## Dashboard Pages

| Page | What it shows |
|------|---------------|
| 📋 Live Incident Feed | All incidents with lifecycle stage, severity, and escalation state |
| 🔀 Workflow Timeline | Full 11-agent LangGraph execution trace for any incident |
| 💥 Failure Injection | Developer control panel — inject 8 types of real failures |
| 🧠 AI Reasoning | Why the AI made each decision: classification, risk score, RCA, escalation |
| 👤 Human Review Queue | Paused incidents awaiting approval — approve or reject with notes |
| 📄 Live Logs | Workflow, incident, and notification log streams |
| 🐙 GitHub Activity | Issues created and project board column transitions |
| 🩺 System Health | Live service status, metrics, and recent deployments |
| 🔧 Remediation Status | All remediation attempts and recovery validation state |
| 🔗 Incident Correlation | Incidents grouped by shared deployment or service cascade |
| 🧠 Operational Memory | Historical patterns, strategy success rates, instability scores |
| 🔭 Orchestration Health | Monitoring loop liveness, heartbeat age, stuck incidents |

---

## What the incident lifecycle looks like

```
Developer injects auth failure (Failure Injection page)
         ↓
Monitoring loop detects degraded auth-service (next poll)
         ↓
New incident created → GitHub issue created → moves to Triage
         ↓
Classification Agent classifies severity + type (LLM)
         ↓
RCA Agent identifies root cause + deployment correlation (LLM)
         ↓
Risk Scoring Agent computes risk score, picks remediation strategy
         ↓
Escalation Agent evaluates 7 rules
         ↓
If risk ≤ 0.60: Remediation Agent resets auth-service → moves to Monitoring
If risk > 0.60: Workflow pauses → Human Review Queue shows the incident
         ↓
Recovery Validation Agent polls health every 30s for 5 minutes
         ↓
System stable → Resolution Agent closes incident + GitHub issue
         ↓
Email notification sent for every stage transition
```

---

## Stopping Everything

- Monitoring loop: `Ctrl+C` in Tab 3
- Streamlit dashboards: `Ctrl+C` in Tabs 2 and 4
- Ops dashboard backend: `Ctrl+C` in Tab 1
- SSE sidecar: `Ctrl+C` if running

The SQLite databases (`agentic_itsm.db`, `agentic_itsm_checkpoints.db`) persist between runs. To start completely fresh:

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
rm -f agentic_itsm.db agentic_itsm_checkpoints.db logs/*.log
```

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/internal-ops-dashboard
rm -f ops_dashboard.db
```
