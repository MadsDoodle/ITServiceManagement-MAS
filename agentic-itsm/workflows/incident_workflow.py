"""
LangGraph incident lifecycle workflow.

Graph topology (no shared nodes — each node has exactly one outgoing path):

  START → monitor → [no_anomalies → complete]
                  → classify → rca → score_risk → escalate
                  → github_ops  (creates in New, pauses, moves to Triage)
                  → notify_triage
                  → human_review → [paused → complete]
                                 → [approved/continue → remediate]
  remediate → [success → notify_monitoring → recovery_validate]
            → [needs_human → complete]
            → [failed → recovery_validate]
  recovery_validate → [validated → resolve → notify_resolved → complete]
                    → [still_monitoring → complete]
                    → [regressed → remediate]  # retry, not re-investigate (avoids new GH issues)
  complete → END

Column transitions fire with STAGE_TRANSITION_DELAY_SECONDS delay so each
GitHub board column is visibly occupied before moving on.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from agents import (
    classification_agent,
    escalation_agent,
    github_agent,
    human_review_agent,
    monitoring_agent,
    notification_agent,
    recovery_validation_agent,
    remediation_agent,
    resolution_agent,
    risk_scoring_agent,
    rca_agent,
)
from state.incident_state import IncidentState, new_state, append_trace
from state.persistent_store import upsert_incident, save_workflow_run
from state.checkpoint_store import get_checkpointer
from agents.github_agent import move_to_column, post_lifecycle_comment
from utils.constants import (
    COLUMN_INVESTIGATING,
    COLUMN_FIX_IN_PROGRESS,
    COLUMN_MONITORING,
    COLUMN_RESOLVED,
)
from utils.logger import log_event, workflow_logger


# ── Persist helper ────────────────────────────────────────────────────────────

def _persist(state: IncidentState) -> IncidentState:
    try:
        upsert_incident(dict(state))
    except Exception as exc:
        log_event(workflow_logger, "warning", "persist_failed", error=str(exc))
    return state


def _node(fn):
    def wrapper(state: IncidentState) -> IncidentState:
        state = fn(state)
        return _persist(state)
    return wrapper


def _node_with_column(fn, column: str, stage_name: str, comment_key: str = ""):
    """Run agent → move GitHub column (with delay) → persist."""
    def wrapper(state: IncidentState) -> IncidentState:
        state = fn(state)
        state = move_to_column(state, column)
        if state.get("github_issue_number"):
            detail = str(state.get(comment_key, "")) if comment_key else ""
            post_lifecycle_comment(state, stage_name, detail)
        return _persist(state)
    return wrapper


# ── Node functions ────────────────────────────────────────────────────────────

_monitor           = _node(monitoring_agent.run)
_classify          = _node(classification_agent.run)
_rca               = _node_with_column(rca_agent.run,
                         COLUMN_INVESTIGATING, "investigating", "root_cause_summary")
_score_risk        = _node(risk_scoring_agent.run)
_escalate          = _node(escalation_agent.run)
_github_ops        = _node(github_agent.run)           # New → pause → Triage internally
_human_review      = _node(human_review_agent.run)
_remediate         = _node_with_column(remediation_agent.run,
                         COLUMN_FIX_IN_PROGRESS, "fix_in_progress", "remediation_detail")
_recovery_validate = _node_with_column(recovery_validation_agent.run,
                         COLUMN_MONITORING, "monitoring")
_resolve           = _node_with_column(resolution_agent.run,
                         COLUMN_RESOLVED, "resolved", "root_cause_summary")


# ── Dedicated notification nodes (no shared node — avoids parallel edge conflict) ──

def _notify_triage(state: IncidentState) -> IncidentState:
    """Notification after issue is created and in Triage."""
    state = notification_agent.run(state)
    return _persist(state)


def _notify_monitoring(state: IncidentState) -> IncidentState:
    """Notification when remediation succeeded and system moves to Monitoring."""
    state = notification_agent.run(state)
    return _persist(state)


def _notify_resolved(state: IncidentState) -> IncidentState:
    """Final resolution notification."""
    state = notification_agent.run(state)
    return _persist(state)


def _mark_complete(state: IncidentState) -> IncidentState:
    state["completed"] = True
    state = append_trace(state, "Workflow", "workflow_complete",
                         "Incident lifecycle completed")
    return _persist(state)


# ── Routing conditions ────────────────────────────────────────────────────────

def _after_monitor(state: IncidentState) -> str:
    if not state.get("anomalies"):
        log_event(workflow_logger, "info", "workflow_short_circuit", reason="no_anomalies")
        return "no_anomalies"
    return "anomalies_found"


def _after_human_review(state: IncidentState) -> str:
    stage = state.get("lifecycle_stage", "")
    if stage == "awaiting_review":
        return "paused"
    if stage == "fix_in_progress":
        return "approved"
    return "continue"


def _after_remediation(state: IncidentState) -> str:
    if state.get("remediation_succeeded"):
        return "success"
    stage = state.get("lifecycle_stage", "")
    if stage == "awaiting_review" and not state.get("human_approved"):
        return "needs_human"
    return "failed"


def _after_recovery(state: IncidentState) -> str:
    if state.get("recovery_validated"):
        return "validated"
    stage = state.get("lifecycle_stage", "")
    # monitoring = still waiting for stability window → yield
    if stage == "monitoring":
        return "still_monitoring"
    # investigating = service regressed after remediation
    # For fast_recovery incidents yield rather than immediately retrying
    # (cooldown guard would block retry anyway and causes oscillation)
    if state.get("fast_recovery"):
        return "still_monitoring"
    return "regressed"


# ── Graph construction ────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    builder = StateGraph(IncidentState)

    # Nodes
    builder.add_node("monitor",           _monitor)
    builder.add_node("classify",          _classify)
    builder.add_node("rca",               _rca)
    builder.add_node("score_risk",        _score_risk)
    builder.add_node("escalate",          _escalate)
    builder.add_node("github_ops",        _github_ops)
    builder.add_node("notify_triage",     _notify_triage)
    builder.add_node("human_review",      _human_review)
    builder.add_node("remediate",         _remediate)
    builder.add_node("notify_monitoring", _notify_monitoring)
    builder.add_node("recovery_validate", _recovery_validate)
    builder.add_node("resolve",           _resolve)
    builder.add_node("notify_resolved",   _notify_resolved)
    builder.add_node("complete",          _mark_complete)

    # Entry
    builder.add_edge(START, "monitor")

    # Monitor → classify or short-circuit
    builder.add_conditional_edges(
        "monitor",
        _after_monitor,
        {"anomalies_found": "classify", "no_anomalies": "complete"},
    )

    # Linear investigation pipeline
    builder.add_edge("classify",       "rca")
    builder.add_edge("rca",            "score_risk")
    builder.add_edge("score_risk",     "escalate")
    builder.add_edge("escalate",       "github_ops")
    builder.add_edge("github_ops",     "notify_triage")
    builder.add_edge("notify_triage",  "human_review")

    # Human review gate
    builder.add_conditional_edges(
        "human_review",
        _after_human_review,
        {
            "paused":   "complete",
            "approved": "remediate",
            "continue": "remediate",
        },
    )

    # Remediation
    builder.add_conditional_edges(
        "remediate",
        _after_remediation,
        {
            "success":     "notify_monitoring",
            "needs_human": "complete",
            "failed":      "recovery_validate",
        },
    )

    # Monitoring notification → recovery validation
    builder.add_edge("notify_monitoring", "recovery_validate")

    # Recovery validation loop
    builder.add_conditional_edges(
        "recovery_validate",
        _after_recovery,
        {
            "validated":        "resolve",
            "still_monitoring": "complete",
            "regressed":        "remediate",  # retry remediation — do NOT re-create GitHub issue
        },
    )

    # Resolution → final notification → done
    builder.add_edge("resolve",         "notify_resolved")
    builder.add_edge("notify_resolved", "complete")
    builder.add_edge("complete",        END)

    return builder


# ── Compiled graph singleton ──────────────────────────────────────────────────

_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_workflow().compile(checkpointer=get_checkpointer())
    return _compiled_graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_incident_workflow(initial_state: IncidentState | None = None) -> IncidentState:
    incident_id     = f"INC-{uuid.uuid4().hex[:8].upper()}"
    workflow_run_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    created_at      = datetime.now(timezone.utc).isoformat()

    state = initial_state or new_state(incident_id, workflow_run_id, created_at)
    state.setdefault("incident_id",     incident_id)
    state.setdefault("workflow_run_id", workflow_run_id)
    state.setdefault("created_at",      created_at)

    cfg = {"configurable": {"thread_id": workflow_run_id}}

    log_event(workflow_logger, "info", "workflow_start",
              incident_id=incident_id, workflow_run_id=workflow_run_id)

    result = _get_graph().invoke(state, config=cfg)

    try:
        save_workflow_run(dict(result))
    except Exception:
        pass

    log_event(workflow_logger, "info", "workflow_end",
              incident_id=incident_id,
              severity=result.get("severity"),
              stage=result.get("lifecycle_stage"),
              escalated=result.get("escalation_required"),
              github_issue=result.get("github_issue_number"),
              completed=result.get("completed"))
    return result


def resume_incident_workflow(stored_state: dict) -> IncidentState:
    incident_id     = stored_state.get("incident_id", f"INC-{uuid.uuid4().hex[:8].upper()}")
    workflow_run_id = stored_state.get("workflow_run_id", f"WF-{uuid.uuid4().hex[:8].upper()}")

    state = IncidentState(**{k: v for k, v in stored_state.items()
                             if k in IncidentState.__annotations__})

    cfg = {"configurable": {"thread_id": workflow_run_id}}

    log_event(workflow_logger, "info", "workflow_resume",
              incident_id=incident_id, stage=stored_state.get("lifecycle_stage"))

    result = _get_graph().invoke(state, config=cfg)

    try:
        upsert_incident(dict(result))
        save_workflow_run(dict(result))
    except Exception:
        pass

    log_event(workflow_logger, "info", "workflow_resume_end",
              incident_id=incident_id, stage=result.get("lifecycle_stage"))
    return result
