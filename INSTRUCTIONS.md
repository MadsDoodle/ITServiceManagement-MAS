# How to Start the ITSM-MAS Platform

---

## Prerequisites

- Python 3.11 installed (`python3.11 --version`)
- Docker Desktop running (for the ops dashboard)
- Git clone of this repo on your machine

---

## Step 1 — Configure Secrets

Open `agentic-itsm/.env` and fill in any missing values:

```
OPENAI_API_KEY=sk-...
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ESCALATION_EMAIL=you@gmail.com
```

Gmail is optional — escalation emails are skipped gracefully if not set.

To get a Gmail App Password: https://myaccount.google.com/apppasswords
(Use an App Password, not your regular account password.)

---

## Step 2 — Start the Internal Ops Dashboard

This is the system the AI will monitor.

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/internal-ops-dashboard
docker-compose up 
or 
uvicorn backend.main:app --reload --port 8000
```

Wait until you see the backend is healthy.
Verify it's running: http://localhost:8000/health/

Leave this terminal running.

---

## Step 3 — Activate the Agentic ITSM Virtual Environment

Open a new terminal tab.

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
```

Your prompt should now show `(.venv)`.

---

## Step 4 — Run a Single Workflow Cycle

This runs one full detection → classification → RCA → GitHub → notification cycle.

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
python app.py
```

The terminal will print the incident summary when complete.

---

## Step 5 — Simulate a Failure (Optional but Recommended First Run)

This injects a crash into the ops dashboard so the AI has something real to detect.

```bash
python app.py --simulate
```

---

## Step 6 — Start the AI Operations Dashboard

Open another new terminal tab.

```bash
cd /Users/madhavbaidya/Desktop/ITSM-MAS/agentic-itsm
source .venv/bin/activate
streamlit run dashboard/app.py --server.port 8502
```

Open in browser: http://localhost:8502

---

## Step 7 — Run Continuous Monitoring Loop (Optional)

This polls every 30 seconds automatically and runs the full workflow on each cycle.

```bash
python app.py --loop
```

Stop with `Ctrl+C`.

---

## Port Reference

| Service                      | URL                        |
|------------------------------|----------------------------|
| Ops Dashboard API            | http://localhost:8000      |
| Ops Dashboard UI (Streamlit) | http://localhost:8501      |
| Agentic ITSM AI Console      | http://localhost:8502      |

---

## Terminal Layout (Recommended)

| Tab | What runs there                          |
|-----|------------------------------------------|
| 1   | `docker-compose up` (ops dashboard)      |
| 2   | `python app.py --loop` (AI monitoring)   |
| 3   | `streamlit run dashboard/app.py` (UI)    |

---

## Stopping Everything

- Ops dashboard: `Ctrl+C` in docker-compose tab, then `docker-compose down`
- AI loop: `Ctrl+C`
- Streamlit: `Ctrl+C`
