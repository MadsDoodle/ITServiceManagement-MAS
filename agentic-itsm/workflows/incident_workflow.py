"""
LangGraph incident response workflow.

Graph topology:
  monitor → classify → rca → escalate → github_ops → notify → [end]

Conditional routing:
  After `monitor`: if no anomalies detected → short-circuit to END
  After `notify`:  always → END

The graph uses MemorySaver as a checkpointer so each workflow run
is independently traceable by its workflow_run_id thread.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from agents import (
    classification_agent,
    escalation_agent,
    github_agent,
    monitoring_agent,
    notification_agent,
    rca_agent,
)
from state.incident_state import IncidentState, new_state, append_trace
from utils.logger import log_event, workflow_logger


# ── Graph node wrappers ───────────────────────────────────────────────────────
# Each wrapper is a thin adapter so agents stay decoupled from LangGraph API.

def _monitor(state: IncidentState) -> IncidentState:
    return monitoring_agent.run(state)


def _classify(state: IncidentState) -> IncidentState:
    return classification_agent.run(state)


def _rca(state: IncidentState) -> IncidentState:
    return rca_agent.run(state)


def _escalate(state: IncidentState) -> IncidentState:
    return escalation_agent.run(state)


def _github_ops(state: IncidentState) -> IncidentState:
    return github_agent.run(state)


def _notify(state: IncidentState) -> IncidentState:
    return notification_agent.run(state)


def _mark_complete(state: IncidentState) -> IncidentState:
    state["completed"] = True
    state = append_trace(state, "Workflow", "workflow_complete", "Incident lifecycle completed")
    return state


# ── Routing conditions ────────────────────────────────────────────────────────

def _should_continue_after_monitor(state: IncidentState) -> str:
    """Skip the rest of the pipeline if nothing was detected."""
    if not state.get("anomalies"):
        log_event(workflow_logger, "info", "workflow_short_circuit", reason="no_anomalies")
        return "no_anomalies"
    return "anomalies_found"


# ── Graph construction ────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    builder = StateGraph(IncidentState)

    builder.add_node("monitor",    _monitor)
    builder.add_node("classify",   _classify)
    builder.add_node("rca",        _rca)
    builder.add_node("escalate",   _escalate)
    builder.add_node("github_ops", _github_ops)
    builder.add_node("notify",     _notify)
    builder.add_node("complete",   _mark_complete)

    # Entry
    builder.add_edge(START, "monitor")

    # Conditional branch after monitoring
    builder.add_conditional_edges(
        "monitor",
        _should_continue_after_monitor,
        {
            "anomalies_found": "classify",
            "no_anomalies":    "complete",
        },
    )

    # Linear pipeline
    builder.add_edge("classify",   "rca")
    builder.add_edge("rca",        "escalate")
    builder.add_edge("escalate",   "github_ops")
    builder.add_edge("github_ops", "notify")
    builder.add_edge("notify",     "complete")
    builder.add_edge("complete",   END)

    return builder


# ── Public API ────────────────────────────────────────────────────────────────

_checkpointer = MemorySaver()
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_workflow().compile(checkpointer=_checkpointer)
    return _compiled_graph


def run_incident_workflow(initial_state: IncidentState | None = None) -> IncidentState:
    """
    Execute the full incident workflow synchronously.
    Returns the final IncidentState after all agents have run.
    """
    incident_id     = f"INC-{uuid.uuid4().hex[:8].upper()}"
    workflow_run_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    created_at      = datetime.now(timezone.utc).isoformat()

    state = initial_state or new_state(incident_id, workflow_run_id, created_at)
    # Ensure identity fields are set even if caller provided partial state
    state.setdefault("incident_id",     incident_id)
    state.setdefault("workflow_run_id", workflow_run_id)
    state.setdefault("created_at",      created_at)

    config = {"configurable": {"thread_id": workflow_run_id}}

    log_event(
        workflow_logger, "info", "workflow_start",
        incident_id=incident_id, workflow_run_id=workflow_run_id,
    )

    graph  = _get_graph()
    result = graph.invoke(state, config=config)

    log_event(
        workflow_logger, "info", "workflow_end",
        incident_id=incident_id,
        severity=result.get("severity"),
        escalated=result.get("escalation_required"),
        github_issue=result.get("github_issue_number"),
        completed=result.get("completed"),
    )
    return result
