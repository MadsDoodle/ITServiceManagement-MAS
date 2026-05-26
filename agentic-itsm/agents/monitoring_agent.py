"""
Monitoring Agent — purely deterministic.
Polls the internal-ops-dashboard for health, metrics, logs, and deployments.
Detects anomalies using threshold rules. No LLM involved.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.monitoring_service import (
    detect_anomalies,
    fetch_deployments,
    fetch_health,
    fetch_logs,
    fetch_metrics,
    fetch_services,
)
from utils.logger import log_event, workflow_logger

AGENT_NAME = "MonitoringAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    If state already has pre_populated_anomalies=True (set by dashboard injection),
    skip the real poll and use the anomalies already in state.
    Otherwise poll the ops dashboard for real anomalies.
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    if state.get("pre_populated_anomalies") and state.get("anomalies"):
        anomalies = state["anomalies"]
        log_event(workflow_logger, "info", "monitoring_using_preset_anomalies",
                  agent=AGENT_NAME, anomaly_count=len(anomalies))
    else:
        health      = fetch_health()
        metrics     = fetch_metrics()
        services    = fetch_services()
        logs        = fetch_logs(lines=100, since_minutes=15)
        deployments = fetch_deployments(limit=10)

        anomalies = detect_anomalies(
            health=health,
            metrics=metrics,
            services=services,
            deployments=deployments,
            logs=logs,
        )

        state["raw_health"]      = health
        state["raw_metrics"]     = metrics
        state["raw_logs"]        = logs
        state["raw_deployments"] = deployments

    state["anomalies"] = anomalies

    detail = (
        f"{'Preset' if state.get('pre_populated_anomalies') else 'Detected'} "
        f"{len(anomalies)} anomalies: {[a['type'] for a in anomalies]}"
    ) if anomalies else "No anomalies"

    state = append_trace(state, AGENT_NAME, "monitoring_complete", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, anomaly_count=len(anomalies))
    return state
