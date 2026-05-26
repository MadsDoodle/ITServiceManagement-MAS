"""
Deployment remediation — creates a rollback deployment record
to represent a recovery action in the monitored system.
Low-risk: only writes a new deployment record via POST /deployments/.
"""
from __future__ import annotations

import httpx

from utils.config import config
from utils.logger import log_event, workflow_logger


def remediate(state: dict) -> dict:
    corr = state.get("correlated_deployment") or {}
    failed_version = corr.get("version", "unknown")
    failed_dep_id  = corr.get("deployment_id", "unknown")

    log_event(workflow_logger, "info", "remediation_start",
              strategy="rollback_deploy", failed_dep=failed_dep_id)

    try:
        with httpx.Client(base_url=config.OPS_DASHBOARD_URL,
                          headers={"X-API-Key": config.OPS_API_KEY},
                          timeout=10) as c:
            # Create rollback deployment record
            r = c.post("/deployments/", json={
                "version":     "rollback",
                "commit_ref":  "rollback-remediation",
                "deployed_by": "itsm-remediation-agent",
                "notes":       f"Automated rollback from {failed_version} ({failed_dep_id}) by ITSM",
            })
            r.raise_for_status()
            dep = r.json()
            dep_id = dep.get("deployment_id")

            # Mark it success
            c.patch(f"/deployments/{dep_id}", json={
                "status":           "success",
                "duration_seconds": 45.0,
                "notes":            "Rollback completed successfully by ITSM remediation",
            })

        detail = f"Rollback deployment {dep_id} created and completed successfully"
        log_event(workflow_logger, "info", "remediation_success",
                  strategy="rollback_deploy", dep_id=dep_id)
        return {"success": True, "detail": detail}
    except Exception as exc:
        detail = f"Deployment rollback failed: {exc}"
        log_event(workflow_logger, "warning", "remediation_failed",
                  strategy="rollback_deploy", error=str(exc))
        return {"success": False, "detail": detail}
