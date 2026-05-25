import os

import requests

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
_HEADERS = {"Content-Type": "application/json", "X-API-Key": os.getenv("API_KEY", "dev-secret-key-123")}
_TIMEOUT = 10


def _get(path: str, params: dict = None) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_HEADERS, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot reach backend API — is it running?"}
    except requests.exceptions.Timeout:
        return {"error": "Backend API timed out."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, body: dict) -> dict:
    try:
        r = requests.post(f"{API_BASE}{path}", headers=_HEADERS, json=body, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot reach backend API."}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def _patch(path: str, body: dict = None, params: dict = None) -> dict:
    try:
        r = requests.patch(f"{API_BASE}{path}", headers=_HEADERS, json=body, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Health ────────────────────────────────────────────────────────────────────
def get_health() -> dict:                       return _get("/health/")
def get_services() -> dict:                     return _get("/health/services")
def update_service_status(name, status, notes=None) -> dict:
    return _patch(f"/health/services/{name}", params={"status": status, "notes": notes})


# ── Incidents ─────────────────────────────────────────────────────────────────
def get_incidents(status=None, severity=None) -> dict:
    params = {k: v for k, v in {"status": status, "severity": severity}.items() if v}
    return _get("/incidents/", params=params or None)

def create_incident(title, severity, affected_service, notes=None, commit_ref=None) -> dict:
    return _post("/incidents/", {"title": title, "severity": severity,
                                  "affected_service": affected_service,
                                  "notes": notes, "commit_ref": commit_ref})

def update_incident(incident_id, status=None, notes=None) -> dict:
    return _patch(f"/incidents/{incident_id}", {"status": status, "notes": notes})


# ── Deployments ───────────────────────────────────────────────────────────────
def get_deployments() -> dict:                  return _get("/deployments/")
def get_latest_deployment() -> dict:            return _get("/deployments/latest")
def create_deployment(version, commit_ref, deployed_by="ci-bot", notes=None) -> dict:
    return _post("/deployments/", {"version": version, "commit_ref": commit_ref,
                                    "deployed_by": deployed_by, "notes": notes})


# ── Metrics ───────────────────────────────────────────────────────────────────
def get_metrics() -> dict:                      return _get("/metrics/")
def get_metric_history(hours=24) -> dict:       return _get("/metrics/history", params={"hours": hours})


# ── Logs ──────────────────────────────────────────────────────────────────────
def get_logs(log_type="app", lines=100) -> dict:
    return _get("/logs/", params={"log_type": log_type, "lines": lines})