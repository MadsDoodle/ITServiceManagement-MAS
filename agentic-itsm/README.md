# Agentic ITSM

AI-driven operational incident management platform that monitors `internal-ops-dashboard`,
detects anomalies, classifies incidents, performs root cause analysis, creates GitHub issues,
updates the GitHub Project board, and sends escalation emails — all orchestrated via LangGraph.

---

## Architecture

```
internal-ops-dashboard (monitored system)
        ↓  HTTP polling
Monitoring Agent        ← deterministic threshold checks
        ↓
Classification Agent    ← OpenAI: severity + incident type
        ↓
RCA Agent               ← OpenAI: root cause + deployment correlation
        ↓
Escalation Agent        ← deterministic rule evaluation
        ↓
GitHub Agent            ← REST + GraphQL: issue + project update
        ↓
Notification Agent      ← Gmail SMTP + optional LLM email body
        ↓
Dashboard (Streamlit)   ← AI observability console
```

## Hybrid Architecture Principle

| Component          | Approach      | Reason                                        |
|--------------------|---------------|-----------------------------------------------|
| Anomaly detection  | Deterministic | Predictable, fast, no token cost              |
| Classification     | LLM           | Semantic interpretation of mixed signals      |
| RCA                | LLM           | Multi-source reasoning across logs + deploys  |
| Escalation         | Deterministic | Must be auditable and rule-based              |
| GitHub operations  | Deterministic | Exact API calls, no reasoning needed          |
| Email body         | LLM (optional)| Better prose; falls back to template          |

---

## Setup

### 1. Prerequisites

```bash
cd agentic-itsm
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env` and fill in your credentials:

```
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...          # repo + project scopes required
GITHUB_REPO_OWNER=your-org
GITHUB_REPO_NAME=ITSM-MAS
GITHUB_PROJECT_NUMBER=1
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ESCALATION_EMAIL=oncall@yourcompany.com
```

> **Gmail**: Use an App Password from https://myaccount.google.com/apppasswords
> The system gracefully skips email and GitHub if credentials are absent — it still runs the full AI pipeline.

### 3. Start the monitored system

```bash
cd internal-ops-dashboard
docker-compose up
# or: uvicorn backend.main:app --reload --port 8000
```

### 4. Run a single workflow cycle

```bash
python app.py
```

### 5. Simulate a failure and run

```bash
python app.py --simulate
```

### 6. Continuous monitoring loop

```bash
python app.py --loop
```

### 7. Launch the AI Operations Dashboard

```bash
streamlit run dashboard/app.py --server.port 8502
```

---

## GitHub Project Board

The system updates the **Agentic ITSM Operations** GitHub Project with:

| Custom Field       | Type          | Set By              |
|--------------------|---------------|---------------------|
| Severity           | Single Select | GitHub Agent        |
| Incident Type      | Single Select | GitHub Agent        |
| Escalation Required| Single Select | GitHub Agent        |
| AI Confidence      | Number        | GitHub Agent        |

Workflow columns traversed: `New → Triage → Investigating → Fix In Progress → Monitoring → Resolved`

---

## Repository Structure

```
agentic-itsm/
├── agents/
│   ├── monitoring_agent.py      # Deterministic: poll + anomaly detect
│   ├── classification_agent.py  # LLM: severity + type
│   ├── rca_agent.py             # LLM: root cause analysis
│   ├── escalation_agent.py      # Deterministic: rule-based escalation
│   ├── github_agent.py          # Deterministic: GitHub REST+GraphQL
│   └── notification_agent.py    # Gmail + optional LLM summary
├── workflows/
│   └── incident_workflow.py     # LangGraph StateGraph
├── services/
│   ├── monitoring_service.py    # HTTP polling + anomaly detection
│   ├── llm_service.py           # OpenAI wrapper + fallbacks
│   ├── github_service.py        # GitHub REST + GraphQL
│   ├── gmail_service.py         # SMTP email
│   ├── log_service.py           # Local log reader
│   └── deployment_service.py    # Deployment correlation cache
├── state/
│   └── incident_state.py        # LangGraph TypedDict state
├── dashboard/
│   ├── app.py                   # Streamlit entry point
│   ├── pages/                   # incidents, trace, github, notifications, logs
│   ├── components/              # timeline, incident_card, agent_status, workflow_graph
│   └── services/
│       └── dashboard_api.py     # SQLite state DB + data aggregation
├── prompts/
│   ├── classification_prompt.txt
│   ├── rca_prompt.txt
│   └── summarization_prompt.txt
├── utils/
│   ├── config.py
│   ├── logger.py
│   └── constants.py
├── app.py                       # Main entry point
├── requirements.txt
└── .env
```

---

## Escalation Rules

An incident is escalated if **any** of these conditions are true:

1. Severity is P1
2. A critical service is affected (`auth-service`, `database`, `api-gateway`)
3. AI confidence is below 60%
4. Correlated deployment is `failed` or `rolled_back`
5. 3 or more anomalies detected simultaneously
6. P2 incident of type `Service Outage`, `Authentication`, or `Database Issue`
7. System-level health check returns `down`

---

## LLM Usage

The system uses `gpt-4o-mini` by default (cheap, fast, sufficient for operational reasoning).
Change to `gpt-4o` in `.env` for higher accuracy classification and RCA.

If `OPENAI_API_KEY` is not set, every LLM call falls back gracefully to deterministic logic.
The system remains fully operational — just with rule-based classification instead of AI reasoning.
