"""
Thin wrapper around the OpenAI chat completion API.
Used only where genuine reasoning is required (classification, RCA, summaries).
Gracefully falls back to deterministic defaults when the key is absent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from utils.config import config
from utils.logger import log_event, workflow_logger

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise EnvironmentError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def _load_prompt(filename: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / filename
    if path.exists():
        return path.read_text()
    return ""


def chat_completion(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    """
    Single-turn chat completion. Returns the assistant content string.
    Raises on API errors so callers can handle gracefully.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    content = response.choices[0].message.content or ""
    log_event(
        workflow_logger, "info", "llm_call_complete",
        model=config.OPENAI_MODEL,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
    )
    return content


def classify_incident(anomalies: list[dict], metrics: dict, services: list[dict]) -> dict:
    """
    Ask the LLM to classify severity and incident type.
    Returns: {severity, incident_type, confidence, reasoning}
    Falls back to deterministic default if OpenAI is unavailable.
    """
    try:
        system = _load_prompt("classification_prompt.txt")
        user_data = json.dumps({
            "anomalies": anomalies,
            "metrics":   metrics,
            "services":  [{"service_name": s.get("service_name"), "status": s.get("status")} for s in services],
        }, indent=2)
        raw = chat_completion(system, user_data)
        # Expect JSON back
        result = _parse_json_response(raw)
        return {
            "severity":       result.get("severity", "P3"),
            "incident_type":  result.get("incident_type", "Monitoring Alert"),
            "confidence":     float(result.get("confidence", 0.75)),
            "reasoning":      result.get("reasoning", ""),
        }
    except Exception as exc:
        log_event(workflow_logger, "warning", "llm_classify_fallback", error=str(exc))
        return _deterministic_classification(anomalies)


def perform_rca(
    anomalies: list[dict],
    logs: list[dict],
    deployments: list[dict],
    metrics: dict,
) -> dict:
    """
    Ask the LLM to reason about root cause.
    Returns: {root_cause_summary, correlated_deployment, reasoning}
    """
    try:
        system = _load_prompt("rca_prompt.txt")
        # Trim logs to last 50 to keep context manageable
        trimmed_logs = logs[-50:] if len(logs) > 50 else logs
        user_data = json.dumps({
            "anomalies":        anomalies,
            "recent_logs":      trimmed_logs,
            "recent_deployments": deployments[:5],
            "metrics":          metrics,
        }, indent=2)
        raw = chat_completion(system, user_data, temperature=0.3)
        result = _parse_json_response(raw)
        # Find correlated deployment if commit_ref mentioned
        correlated = None
        commit = result.get("correlated_commit_ref")
        if commit:
            correlated = next(
                (d for d in deployments if d.get("commit_ref") == commit), None
            )
        return {
            "root_cause_summary":   result.get("root_cause_summary", "Root cause could not be determined."),
            "correlated_deployment": correlated,
            "reasoning":            result.get("reasoning", ""),
        }
    except Exception as exc:
        log_event(workflow_logger, "warning", "llm_rca_fallback", error=str(exc))
        return _deterministic_rca(anomalies, deployments)


def summarize_for_email(state: dict) -> str:
    """
    Generate a human-readable incident summary for email notifications.
    Falls back to a templated summary.
    """
    try:
        system = _load_prompt("summarization_prompt.txt")
        user_data = json.dumps({
            "incident_id":        state.get("incident_id"),
            "severity":           state.get("severity"),
            "incident_type":      state.get("incident_type"),
            "anomalies":          state.get("anomalies", []),
            "root_cause_summary": state.get("root_cause_summary"),
            "escalation_required": state.get("escalation_required"),
            "escalation_reasons": state.get("escalation_reasons", []),
            "github_issue_url":   state.get("github_issue_url"),
        }, indent=2)
        return chat_completion(system, user_data, temperature=0.4)
    except Exception as exc:
        log_event(workflow_logger, "warning", "llm_summarize_fallback", error=str(exc))
        return _templated_email_summary(state)


# ── Deterministic fallbacks ───────────────────────────────────────────────────

def _deterministic_classification(anomalies: list[dict]) -> dict:
    """Simple rule-based fallback classification when OpenAI is unavailable."""
    if not anomalies:
        return {
            "severity": "Low",
            "incident_type": "Monitoring Alert",
            "confidence": 0.5,
            "reasoning": "No anomalies detected; defaulting to Low severity.",
        }
    # Use the highest severity_hint among anomalies
    priority = {"P1": 4, "P2": 3, "P3": 2, "Low": 1}
    best = max(anomalies, key=lambda a: priority.get(a.get("severity_hint", "Low"), 0))
    sev = best.get("severity_hint", "P3")

    type_map = {
        "deployment_failure": "Deployment Failure",
        "service_down":       "Service Outage",
        "service_degraded":   "Performance",
        "high_latency":       "Performance",
        "high_error_rate":    "API Failure",
        "health_check_failure": "Service Outage",
        "log_error_spike":    "Monitoring Alert",
    }
    inc_type = type_map.get(best.get("type", ""), "Monitoring Alert")

    return {
        "severity":      sev,
        "incident_type": inc_type,
        "confidence":    0.55,
        "reasoning":     f"Rule-based fallback: highest anomaly type is '{best.get('type')}' with hint '{sev}'.",
    }


def _deterministic_rca(anomalies: list[dict], deployments: list[dict]) -> dict:
    """Rule-based RCA fallback."""
    summary = "Root cause analysis unavailable (LLM offline). "
    if anomalies:
        summary += f"Detected anomalies: {', '.join(a.get('type', '') for a in anomalies)}. "
    correlated = None
    for dep in deployments[:3]:
        if dep.get("status") in ("failed", "rolled_back"):
            correlated = dep
            summary += f"Likely correlated with deployment {dep.get('deployment_id')} ({dep.get('version')}) — status: {dep.get('status')}."
            break
    return {
        "root_cause_summary":    summary,
        "correlated_deployment": correlated,
        "reasoning":             "Deterministic fallback — LLM unavailable.",
    }


def _templated_email_summary(state: dict) -> str:
    sev   = state.get("severity", "Unknown")
    itype = state.get("incident_type", "Unknown")
    iid   = state.get("incident_id", "N/A")
    esc   = "YES" if state.get("escalation_required") else "NO"
    url   = state.get("github_issue_url", "N/A")
    rca   = state.get("root_cause_summary", "Not available")
    return (
        f"ITSM Incident Alert\n"
        f"{'='*50}\n"
        f"Incident ID   : {iid}\n"
        f"Severity      : {sev}\n"
        f"Type          : {itype}\n"
        f"Escalation    : {esc}\n"
        f"GitHub Issue  : {url}\n\n"
        f"Root Cause Summary:\n{rca}\n"
    )


def _parse_json_response(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response string."""
    # strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return json.loads(raw)
