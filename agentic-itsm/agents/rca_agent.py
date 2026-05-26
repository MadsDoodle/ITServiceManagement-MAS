"""
Root Cause Analysis Agent — uses OpenAI to reason about probable root cause.
Correlates anomalies with deployment history, historical patterns, and related incidents.
Falls back to deterministic summary if LLM unavailable.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.llm_service import perform_rca
from services.correlation_service import find_correlations
from services.memory_service import get_historical_context_for_rca
from services.event_bus import publish_lifecycle_transition
from utils.logger import log_event, workflow_logger

AGENT_NAME = "RCAAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node function.
    Reads:  anomalies, raw_logs, raw_deployments, raw_metrics
    Writes: root_cause_summary, correlated_deployment, rca_reasoning,
            related_incident_ids, root_cause_incident_id, correlation_reason
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    anomalies   = state.get("anomalies", [])
    logs        = state.get("raw_logs", [])
    deployments = state.get("raw_deployments", [])
    metrics     = state.get("raw_metrics", {})

    # Gather historical context for the LLM
    affected_services = list({a.get("affected_service", "") for a in anomalies
                              if a.get("affected_service")})
    incident_type     = state.get("incident_type", "")
    historical_ctx    = get_historical_context_for_rca(
        affected_services, incident_type
    )

    result = perform_rca(
        anomalies=anomalies,
        logs=logs,
        deployments=deployments,
        metrics=metrics,
        historical_context=historical_ctx,
    )

    state["root_cause_summary"]    = result["root_cause_summary"]
    state["correlated_deployment"] = result.get("correlated_deployment")
    state["rca_reasoning"]         = result.get("reasoning", "")
    state["lifecycle_stage"]       = "investigating"

    # Incident correlation
    corr_dep    = result.get("correlated_deployment") or {}
    commit_ref  = corr_dep.get("commit_ref")
    corr_result = find_correlations(
        incident_id=state.get("incident_id", ""),
        commit_ref=commit_ref,
        affected_services=affected_services,
        anomaly_types=[a.get("type", "") for a in anomalies],
        created_at=state.get("created_at", ""),
    )
    state["related_incident_ids"]   = corr_result.get("related_incident_ids", [])
    state["root_cause_incident_id"] = corr_result.get("root_cause_incident_id")
    state["correlation_reason"]     = corr_result.get("correlation_reason", "")

    # Publish lifecycle event
    publish_lifecycle_transition(
        incident_id=state.get("incident_id", ""),
        from_stage="triage",
        to_stage="investigating",
        agent=AGENT_NAME,
        detail=result["root_cause_summary"][:120],
    )

    detail = result["root_cause_summary"][:120] + "..."
    if corr_result.get("related_incident_ids"):
        detail += f" | Related: {corr_result['related_incident_ids']}"
    state = append_trace(state, AGENT_NAME, "rca_complete", detail)
    log_event(
        workflow_logger, "info", "agent_complete",
        agent=AGENT_NAME,
        correlated_deployment=corr_dep.get("deployment_id"),
        related_incidents=len(corr_result.get("related_incident_ids", [])),
    )
    return state
