# Agentic ITSM

Autonomous operational incident management platform that continuously monitors `internal-ops-dashboard`, detects anomalies, runs the full incident lifecycle — triage → investigation → remediation → recovery validation → resolution — orchestrated entirely via LangGraph. The system is stateful and continuous: incidents persist across workflow pauses, the monitoring loop runs indefinitely, and every lifecycle transition is observable in real-time.

---

## Architecture

```
internal-ops-dashboard  (monitored target system)
         ↓  HTTP polling every N seconds
  Continuous Monitoring Loop
         ↓  anomaly detected
  Monitoring Agent         ← deterministic threshold checks
         ↓
  Classification Agent     ← OpenAI: severity + incident type
         ↓
  RCA Agent                ← OpenAI: root cause + deployment correlation
         ↓
  Risk Scoring Agent       ← deterministic: 0.0–1.0 composite risk + strategy selection
         ↓
  Escalation Agent         ← deterministic rule evaluation
         ↓
  GitHub Agent             ← REST + GraphQL: issue + project board
         ↓
  Human Review Agent       ← pauses workflow if escalation required
         ↓  (approved by operator or auto-continues)
  Remediation Agent        ← executes low-risk fix autonomously
         ↓
  Recovery Validation Agent← polls stability window (5 min / 3 clean checks)
         ↓  [regressed → back to RCA] [still monitoring → loop continues]
  Resolution Agent         ← closes issue, moves project card to Resolved
         ↓
  Notification Agent       ← stage-based HTML email at every lifecycle transition
         ↓
  Dashboard (Streamlit)    ← AI Operational Command Center on :8502
```

### Hybrid architecture

| Component              | Approach       | Reason                                        |
|------------------------|----------------|-----------------------------------------------|
| Anomaly detection      | Deterministic  | Predictable, fast, no token cost              |
| Risk scoring           | Deterministic  | Auditable, reproducible escalation decisions  |
| Classification         | LLM            | Semantic interpretation of mixed signals      |
| RCA                    | LLM            | Multi-source reasoning across logs + deploys  |
| Escalation             | Deterministic  | Must be auditable and rule-based              |
| Remediation dispatch   | Deterministic  | Exact low-risk operations only                |
| Recovery validation    | Deterministic  | Health thresholds, not opinion                |
| GitHub operations      | Deterministic  | Exact API calls, no reasoning needed          |
| Email body             | LLM (optional) | Better prose; falls back to template          |

---

## What changed from the original single-pass system

**Before:** detect → classify → escalate → GitHub → notify → stop

**Now:** continuous stateful lifecycle that never terminates until the incident is resolved

- The monitoring loop runs indefinitely and re-evaluates open incidents on every tick
- Incidents persist in SQLite with full lifecycle state — workflow can pause, resume, and loop back
- Five new agents cover the full lifecycle: `RiskScoringAgent`, `RemediationAgent`, `HumanReviewAgent`, `RecoveryValidationAgent`, `ResolutionAgent`
- Autonomous remediation actually modifies system state via the ops dashboard API (auth reset, service restart, deployment rollback, latency clear) and is validated before resolution
- The escalation path pauses the LangGraph workflow, not terminates it — an operator approves/rejects from the dashboard and the graph resumes from where it stopped
- Recovery validation enforces a stability window (5 minutes of healthy checks) before closing an incident; a regression returns the workflow to the RCA node
- Email notifications fire at every lifecycle stage with coloured HTML banners per stage, de-duplicated so no stage sends twice for the same incident
- The Streamlit dashboard is now an AI Operational Command Center with 9 pages including a Failure Injection Console, Human Review Queue with approve/reject controls, AI Reasoning inspector, and live Remediation Status

---

## Setup

### Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment configuration

```
OPS_DASHBOARD_URL=http://localhost:8000
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...                  # repo + project scopes
GITHUB_REPO_OWNER=your-org
GITHUB_REPO_NAME=ITSM-MAS
GITHUB_PROJECT_NUMBER=1
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ESCALATION_EMAIL=oncall@yourcompany.com
POLL_INTERVAL_SECONDS=30
MONITORING_STABILITY_SECONDS=300      # seconds of clean health before resolving
MONITORING_CHECK_INTERVAL=30
LOW_CONFIDENCE_THRESHOLD=0.6
```

Gmail uses an App Password from https://myaccount.google.com/apppasswords. The system runs the full AI pipeline even without any credentials — GitHub and email operations are skipped gracefully.

### Start the monitored system

```bash
# from internal-ops-dashboard/
uvicorn backend.main:app --reload --port 8000
# or: docker-compose up
```

### Run a single detection cycle

```bash
python app.py
```

### Inject a failure and run once

```bash
python app.py --simulate
```

### Continuous monitoring loop

```bash
python app.py --loop
```

### Launch the AI Operations Dashboard

```bash
streamlit run dashboard/app.py --server.port 8502
```

---

## Repository structure

```
agentic-itsm/
│
├── agents/
│   ├── monitoring_agent.py          # Deterministic: poll + anomaly detection
│   ├── classification_agent.py      # LLM: severity + incident type
│   ├── rca_agent.py                 # LLM: root cause + deployment correlation
│   ├── risk_scoring_agent.py        # Deterministic: 0.0–1.0 risk + strategy selection
│   ├── escalation_agent.py          # Deterministic: rule-based escalation (7 rules)
│   ├── github_agent.py              # GitHub REST + GraphQL: issue + project board
│   ├── human_review_agent.py        # Pause/resume gate for escalated incidents
│   ├── remediation_agent.py         # Dispatches low-risk autonomous fixes
│   ├── recovery_validation_agent.py # Stability window: N clean polls → resolved
│   ├── resolution_agent.py          # Close GitHub issue, resolve ops incident
│   └── notification_agent.py        # Stage-based HTML email, de-duplicated
│
├── workflows/
│   ├── incident_workflow.py         # LangGraph StateGraph — 11 nodes, resumable
│   └── monitoring_loop.py           # Continuous loop: detection + open incident re-eval
│
├── state/
│   ├── incident_state.py            # LangGraph TypedDict (30+ fields, full lifecycle)
│   └── persistent_store.py          # SQLite CRUD: upsert, get_open, approve_incident
│
├── integrations/
│   └── internal_ops/
│       └── simulation_client.py     # All 8 failure injection scenarios (real API calls)
│
├── remediation/
│   ├── auth_remediation.py          # PATCH auth-service → healthy
│   ├── latency_remediation.py       # Clear api-gateway latency annotation
│   ├── service_restart.py           # Simulate restart (degraded → healthy)
│   ├── deployment_remediation.py    # Create rollback deployment record
│   └── recovery_validator.py        # Poll health + metrics, check stability
│
├── services/
│   ├── monitoring_service.py        # HTTP polling + anomaly detection rules
│   ├── llm_service.py               # OpenAI wrapper + deterministic fallbacks
│   ├── github_service.py            # GitHub REST + GraphQL operations
│   ├── gmail_service.py             # Stage-based HTML SMTP email
│   ├── log_service.py               # Local log file reader
│   └── deployment_service.py        # Deployment correlation cache
│
├── dashboard/
│   ├── app.py                       # Streamlit entry — 9-page command center
│   ├── pages/
│   │   ├── live_incidents.py        # Real-time feed with lifecycle stage bar
│   │   ├── execution_trace.py       # 11-node pipeline diagram + agent status
│   │   ├── failure_injection.py     # Developer control panel — 8 failure scenarios
│   │   ├── ai_reasoning.py          # Classification, risk, RCA, remediation trace
│   │   ├── human_review_queue.py    # Approve / reject paused incidents
│   │   ├── live_logs.py             # Multi-stream log viewer
│   │   ├── github_activity.py       # Issues + column transitions
│   │   ├── system_health.py         # Live service cards + metrics
│   │   └── remediation_status.py    # All remediation attempts + recovery state
│   ├── components/
│   │   ├── timeline.py              # 11-agent trace renderer
│   │   ├── workflow_graph.py        # Full pipeline diagram
│   │   ├── incident_card.py         # Styled incident card
│   │   └── agent_status.py          # Per-agent status row
│   └── services/
│       └── dashboard_api.py         # All dashboard data access
│
├── prompts/
│   ├── classification_prompt.txt
│   ├── rca_prompt.txt
│   └── summarization_prompt.txt
│
├── utils/
│   ├── config.py                    # Env-driven config (monitoring thresholds, stability window)
│   ├── constants.py                 # All lifecycle stages, columns, strategies, email stages
│   └── logger.py
│
├── logs/
│   ├── workflow.log
│   ├── incidents.log
│   └── notifications.log
│
├── app.py                           # Entry point (--loop / --once / --simulate / --dashboard)
├── requirements.txt
└── .env
```

---

## Incident lifecycle stages

| Stage             | GitHub column   | What's happening                                         |
|-------------------|-----------------|----------------------------------------------------------|
| `new`             | New             | Anomaly detected, incident created                       |
| `triage`          | Triage          | Classification + risk scoring running                    |
| `investigating`   | Investigating   | RCA in progress, deployment correlation                  |
| `fix_in_progress` | Fix In Progress | Remediation agent executing                              |
| `awaiting_review` | Investigating   | Escalated — workflow paused for human approval           |
| `monitoring`      | Monitoring      | Remediation applied, validating stability                |
| `resolved`        | Resolved        | 5-min stability window passed, incident closed           |

If recovery fails during the monitoring stage, the workflow loops back to `investigating` and re-runs RCA.

---

## Remediation strategies

Only low-risk, reversible operations are executed autonomously. High-risk incidents (risk score > 0.60) are always escalated to a human before any action.

| Strategy              | What it does                                              | Triggered by                      |
|-----------------------|-----------------------------------------------------------|-----------------------------------|
| `reset_auth`          | PATCH auth-service → healthy via `/health/services`       | Auth-type anomalies               |
| `clear_latency`       | PATCH api-gateway → healthy                               | High-latency anomalies            |
| `restart_service`     | Brief degraded → healthy cycle on affected service        | Service down/degraded anomalies   |
| `rollback_deploy`     | Creates a rollback deployment record via `/deployments/`  | Failed/rolled-back deployments    |
| `manual`              | No auto-action — human must intervene                     | Risk score > 0.60                 |

---

## Failure injection (developer console)

The dashboard Failure Injection page lets you hit any of these in one click:

| Scenario                   | What actually happens                                         |
|----------------------------|---------------------------------------------------------------|
| Auth Failure               | POST `/auth/simulate-failure` + PATCH auth-service degraded   |
| Latency Spike              | GET `/simulate/latency?ms=4000`                               |
| Service Degraded           | PATCH `/health/services/auth-service?status=degraded`         |
| Service Down               | PATCH `/health/services/notification-service?status=down`     |
| Deployment Failure         | POST `/deployments/` → PATCH status=failed                    |
| API Crash                  | GET `/simulate/crash` → 500                                   |
| Bad JSON Response          | GET `/simulate/bad-json`                                      |
| Random                     | One of the above picked at random                             |

After injection, the monitoring loop detects the failure on the next poll and the full incident lifecycle begins automatically.

---

## Escalation rules

An incident escalates if any of these conditions are true:

1. Severity is P1
2. A critical service is affected (`auth-service`, `database`, `api-gateway`)
3. AI confidence is below 60%
4. Correlated deployment is `failed` or `rolled_back`
5. Three or more simultaneous anomalies
6. P2 incident of type `Service Outage`, `Authentication`, or `Database Issue`
7. System-level health check returns `down`

When escalated, the workflow enters `awaiting_review`. The Human Review Queue in the dashboard shows the incident with its escalation reasons, proposed remediation, and RCA. The operator approves or rejects — the LangGraph graph resumes from that point.

---

## Email notifications

A stage-specific HTML email with a coloured banner fires at every lifecycle transition, de-duplicated per incident.

| Stage                | Banner colour |
|----------------------|---------------|
| Incident Detected    | Blue          |
| Triage Started       | Yellow        |
| Investigation Started| Orange        |
| Fix In Progress      | Purple        |
| Escalated to Human   | Red           |
| Monitoring Recovery  | Teal          |
| Incident Resolved    | Green         |

Each email includes: severity, incident type, affected service, lifecycle stage, risk score, AI confidence, GitHub issue link, RCA summary, escalation reasons, and remediation detail.

---

## LLM usage

Uses `gpt-4o-mini` by default. Change to `gpt-4o` in `.env` for higher accuracy.

If `OPENAI_API_KEY` is not set, every LLM call falls back to deterministic logic. The full incident lifecycle still runs — classification uses severity hints from anomaly types, RCA summarises detected anomalies, email uses a structured template. Nothing breaks.

---

## GitHub Project board

The system manages the following on the configured GitHub Project:

- Creates an issue per incident with a structured body (anomaly list, RCA, correlated deployment, escalation reasons)
- Adds the issue to the project and sets the Status column at each lifecycle stage transition
- Updates custom fields: Severity, Incident Type, Escalation Required, AI Confidence
- Adds a resolution comment when the incident is closed
- Closes the issue on resolution

Columns used: `New → Triage → Investigating → Fix In Progress → Monitoring → Resolved`
