"""
Root Cause Analysis Agent — uses OpenAI to reason about probable root cause.
Correlates anomalies with deployment history and logs.
Falls back to deterministic summary if LLM unavailable.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.llm_service import perform_rca
from utils.logger import log_event, workflow_logger

AGENT_NAME = "RCAAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node function.
    Reads:  anomalies, raw_logs, raw_deployments, raw_metrics
    Writes: root_cause_summary, correlated_deployment, rca_reasoning
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    anomalies   = state.get("anomalies", [])
    logs        = state.get("raw_logs", [])
    deployments = state.get("raw_deployments", [])
    metrics     = state.get("raw_metrics", {})

    result = perform_rca(
        anomalies=anomalies,
        logs=logs,
        deployments=deployments,
        metrics=metrics,
    )

    state["root_cause_summary"]    = result["root_cause_summary"]
    state["correlated_deployment"] = result.get("correlated_deployment")
    state["rca_reasoning"]         = result.get("reasoning", "")

    detail = result["root_cause_summary"][:120] + "..."
    state = append_trace(state, AGENT_NAME, "rca_complete", detail)
    log_event(
        workflow_logger, "info", "agent_complete",
        agent=AGENT_NAME,
        correlated_deployment=result.get("correlated_deployment", {}).get("deployment_id") if result.get("correlated_deployment") else None,
    )
    return state
