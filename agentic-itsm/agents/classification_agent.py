"""
Classification Agent — uses OpenAI to classify severity and incident type.
Falls back to deterministic classification if LLM is unavailable.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from services.llm_service import classify_incident
from services.monitoring_service import fetch_services
from utils.logger import log_event, workflow_logger

AGENT_NAME = "ClassificationAgent"


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node function.
    Reads:  anomalies, raw_metrics, raw_health
    Writes: severity, incident_type, ai_confidence, classification_reasoning
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    anomalies = state.get("anomalies", [])
    metrics   = state.get("raw_metrics", {})
    services  = state.get("raw_health", {}).get("services", [])

    # If services list not in health response, re-fetch
    if not services:
        try:
            services = fetch_services()
        except Exception:
            services = []

    result = classify_incident(
        anomalies=anomalies,
        metrics=metrics,
        services=services,
    )

    state["severity"]                  = result["severity"]
    state["incident_type"]             = result["incident_type"]
    state["ai_confidence"]             = result["confidence"]
    state["classification_reasoning"]  = result["reasoning"]

    detail = (
        f"Classified as {result['severity']} / {result['incident_type']} "
        f"(confidence: {result['confidence']:.0%})"
    )
    state = append_trace(state, AGENT_NAME, "classification_complete", detail)
    log_event(
        workflow_logger, "info", "agent_complete",
        agent=AGENT_NAME,
        severity=result["severity"],
        incident_type=result["incident_type"],
        confidence=result["confidence"],
    )
    return state
