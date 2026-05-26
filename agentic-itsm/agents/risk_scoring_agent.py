"""
Risk Scoring Agent — deterministic composite risk score (0.0–1.0).
High risk → escalation required / no auto-remediation.
Low risk  → auto-remediation allowed.
"""
from __future__ import annotations

from state.incident_state import IncidentState, append_trace
from utils.constants import (
    CRITICAL_SERVICES,
    SEVERITY_P1, SEVERITY_P2,
    REMEDIATION_RESET_AUTH,
    REMEDIATION_CLEAR_LATENCY,
    REMEDIATION_RESTART_SERVICE,
    REMEDIATION_ROLLBACK_DEPLOY,
    REMEDIATION_MANUAL,
    REMEDIATION_NONE,
    INCIDENT_TYPE_AUTH,
    INCIDENT_TYPE_DATABASE,
)
from utils.logger import log_event, workflow_logger

AGENT_NAME = "RiskScoringAgent"


def _compute_risk(state: IncidentState) -> float:
    """Return a 0.0–1.0 composite risk score, incorporating historical memory."""
    score = 0.0

    sev = state.get("severity", "")
    if sev == SEVERITY_P1:
        score += 0.40
    elif sev == SEVERITY_P2:
        score += 0.25

    anomalies = state.get("anomalies", [])
    affected  = {a.get("affected_service", "") for a in anomalies}
    if affected & CRITICAL_SERVICES:
        score += 0.20

    confidence = state.get("ai_confidence", 1.0)
    if confidence < 0.5:
        score += 0.15
    elif confidence < 0.7:
        score += 0.08

    corr = state.get("correlated_deployment")
    if corr and corr.get("status") in ("failed", "rolled_back"):
        score += 0.15

    if state.get("remediation_retries", 0) >= 2:
        score += 0.15

    itype = state.get("incident_type", "")
    if itype in (INCIDENT_TYPE_AUTH, INCIDENT_TYPE_DATABASE):
        score += 0.10

    # Historical memory boost — unstable services increase risk
    try:
        from services.memory_service import service_stability_score
        for svc in affected:
            if svc and svc not in ("system", "application", "deployment-pipeline"):
                hist_score = service_stability_score(svc)
                score += hist_score * 0.25   # scale: max +0.20 contribution
                break   # only apply for primary service to avoid double-counting
    except Exception:
        pass

    # Correlated incidents boost — if there are related open incidents, risk is higher
    related = state.get("related_incident_ids") or []
    if related:
        score += min(len(related) * 0.05, 0.15)

    return min(score, 1.0)


def _choose_strategy(state: IncidentState, risk_score: float) -> str:
    """
    Choose a remediation strategy.
    Only low-risk strategies are returned for auto-execution.
    High-risk → MANUAL (requires human approval).
    """
    if risk_score > 0.60:
        return REMEDIATION_MANUAL

    itype    = state.get("incident_type", "")
    anomalies = state.get("anomalies", [])
    types    = [a.get("type", "") for a in anomalies]

    if itype == INCIDENT_TYPE_AUTH or "auth" in " ".join(types):
        return REMEDIATION_RESET_AUTH

    if "high_latency" in types:
        return REMEDIATION_CLEAR_LATENCY

    corr = state.get("correlated_deployment")
    if corr and corr.get("status") in ("failed", "rolled_back"):
        return REMEDIATION_ROLLBACK_DEPLOY

    if "service_down" in types or "service_degraded" in types:
        return REMEDIATION_RESTART_SERVICE

    return REMEDIATION_NONE


def run(state: IncidentState) -> IncidentState:
    """
    LangGraph node.
    Reads:  severity, ai_confidence, anomalies, correlated_deployment, remediation_retries
    Writes: risk_score, remediation_strategy
    """
    log_event(workflow_logger, "info", "agent_start", agent=AGENT_NAME)

    risk_score = _compute_risk(state)
    strategy   = _choose_strategy(state, risk_score)

    state["risk_score"]            = risk_score
    state["remediation_strategy"]  = strategy
    state["lifecycle_stage"]       = "triage"

    detail = (
        f"Risk score: {risk_score:.2f} | "
        f"Strategy: {strategy} | "
        f"Auto-remediate: {strategy not in (REMEDIATION_MANUAL, REMEDIATION_NONE)}"
    )
    state = append_trace(state, AGENT_NAME, "risk_scoring_complete", detail)
    log_event(workflow_logger, "info", "agent_complete",
              agent=AGENT_NAME, risk_score=risk_score, strategy=strategy)
    return state
