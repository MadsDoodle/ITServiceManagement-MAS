"""
GitHub REST + GraphQL integration layer.
Handles: issue creation, label management, project card operations,
column transitions, and custom field updates.
All GitHub I/O is isolated here — agents call these functions, never raw HTTP.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx

from utils.config import config
from utils.constants import LABEL_COLOURS, WORKFLOW_COLUMNS
from utils.logger import log_event, workflow_logger

# ── HTTP clients ──────────────────────────────────────────────────────────────
_REST_BASE  = "https://api.github.com"
_GRAPHQL_URL = "https://api.github.com/graphql"

_headers_rest = {
    "Authorization": f"Bearer {config.GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_headers_gql = {
    "Authorization": f"Bearer {config.GITHUB_TOKEN}",
    "Content-Type":  "application/json",
}


def _rest(method: str, path: str, **kwargs) -> dict:
    url = f"{_REST_BASE}{path}"
    resp = httpx.request(method, url, headers=_headers_rest, timeout=15, **kwargs)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


def _gql(query: str, variables: dict | None = None) -> dict:
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = httpx.post(_GRAPHQL_URL, headers=_headers_gql, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data.get("data", {})


# ── Label helpers ─────────────────────────────────────────────────────────────

def ensure_labels(labels: list[str]):
    """Create labels that don't exist yet."""
    owner = config.GITHUB_REPO_OWNER
    repo  = config.GITHUB_REPO_NAME
    existing = {l["name"] for l in _rest("GET", f"/repos/{owner}/{repo}/labels")}
    for label in labels:
        if label not in existing:
            _rest("POST", f"/repos/{owner}/{repo}/labels", json={
                "name":  label,
                "color": LABEL_COLOURS.get(label, "ededed"),
            })
            log_event(workflow_logger, "info", "github_label_created", label=label)


# ── Issue operations ──────────────────────────────────────────────────────────

def create_issue(
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> dict:
    """Create a GitHub issue and return the response dict."""
    owner = config.GITHUB_REPO_OWNER
    repo  = config.GITHUB_REPO_NAME
    if labels:
        try:
            ensure_labels(labels)
        except Exception:
            pass  # best-effort; issue creation proceeds regardless
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    result = _rest("POST", f"/repos/{owner}/{repo}/issues", json=payload)
    log_event(
        workflow_logger, "info", "github_issue_created",
        number=result.get("number"), url=result.get("html_url"),
    )
    return result


def add_issue_comment(issue_number: int, body: str) -> dict:
    owner = config.GITHUB_REPO_OWNER
    repo  = config.GITHUB_REPO_NAME
    return _rest("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json={"body": body})


# ── Project v2 helpers ────────────────────────────────────────────────────────

def get_project_node_id() -> str:
    """Resolve the node ID of the configured project number."""
    query = """
    query($owner: String!, $number: Int!) {
      repositoryOwner(login: $owner) {
        ... on Organization { projectV2(number: $number) { id } }
        ... on User         { projectV2(number: $number) { id } }
      }
    }
    """
    data = _gql(query, {"owner": config.GITHUB_REPO_OWNER, "number": config.GITHUB_PROJECT_NUMBER})
    owner_data = data.get("repositoryOwner", {})
    project = owner_data.get("projectV2", {})
    node_id = project.get("id", "")
    if not node_id:
        raise RuntimeError("Could not resolve GitHub Project node ID. Check GITHUB_REPO_OWNER and GITHUB_PROJECT_NUMBER.")
    return node_id


def add_issue_to_project(issue_node_id: str, project_node_id: str) -> str:
    """Add an issue to a project and return the project item node ID."""
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = _gql(mutation, {"projectId": project_node_id, "contentId": issue_node_id})
    return data["addProjectV2ItemById"]["item"]["id"]


def get_project_fields(project_node_id: str) -> dict[str, dict]:
    """
    Return a map of field_name → {id, type, options: {option_name: option_id}}.
    """
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 30) {
            nodes {
              ... on ProjectV2Field           { id name dataType }
              ... on ProjectV2SingleSelectField {
                id name dataType
                options { id name }
              }
              ... on ProjectV2IterationField  { id name dataType }
            }
          }
        }
      }
    }
    """
    data = _gql(query, {"projectId": project_node_id})
    fields: dict[str, dict] = {}
    for node in data["node"]["fields"]["nodes"]:
        name = node.get("name", "")
        options = {o["name"]: o["id"] for o in node.get("options", [])}
        fields[name] = {
            "id":      node.get("id", ""),
            "type":    node.get("dataType", ""),
            "options": options,
        }
    return fields


def update_project_item_field(
    project_node_id: str,
    item_id: str,
    field_id: str,
    value: Any,
    field_type: str = "SINGLE_SELECT",
) -> None:
    """Update a single field on a project item."""
    if field_type in ("SINGLE_SELECT",):
        val_payload = {"singleSelectOptionId": value}
    elif field_type == "NUMBER":
        val_payload = {"number": value}
    elif field_type == "TEXT":
        val_payload = {"text": str(value)}
    else:
        val_payload = {"text": str(value)}

    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: $value
      }) {
        projectV2Item { id }
      }
    }
    """
    _gql(mutation, {
        "projectId": project_node_id,
        "itemId":    item_id,
        "fieldId":   field_id,
        "value":     val_payload,
    })


def set_project_status(
    project_node_id: str,
    item_id: str,
    fields: dict[str, dict],
    column_name: str,
) -> None:
    """Move a project item to the given Status column."""
    status_field = fields.get("Status", {})
    field_id = status_field.get("id")
    option_id = status_field.get("options", {}).get(column_name)
    if not field_id or not option_id:
        log_event(workflow_logger, "warning", "github_status_column_not_found", column=column_name)
        return
    update_project_item_field(project_node_id, item_id, field_id, option_id, "SINGLE_SELECT")
    log_event(workflow_logger, "info", "github_project_status_set", column=column_name, item_id=item_id)


def update_incident_fields(
    project_node_id: str,
    item_id: str,
    fields: dict[str, dict],
    severity: str,
    incident_type: str,
    escalation_required: bool,
    ai_confidence: float,
) -> None:
    """Bulk-update all custom incident fields on a project item."""
    updates = [
        ("Severity",            severity,
         "SINGLE_SELECT"),
        ("Incident Type",       incident_type,
         "SINGLE_SELECT"),
        ("Escalation Required", "Yes" if escalation_required else "No",
         "SINGLE_SELECT"),
        ("AI Confidence",       round(ai_confidence, 4),
         "NUMBER"),
    ]
    for field_name, raw_value, ftype in updates:
        field_meta = fields.get(field_name, {})
        fid = field_meta.get("id")
        if not fid:
            log_event(workflow_logger, "warning", "github_field_not_found", field=field_name)
            continue
        if ftype == "SINGLE_SELECT":
            option_id = field_meta.get("options", {}).get(str(raw_value))
            if not option_id:
                log_event(workflow_logger, "warning", "github_option_not_found", field=field_name, option=raw_value)
                continue
            update_project_item_field(project_node_id, item_id, fid, option_id, "SINGLE_SELECT")
        else:
            update_project_item_field(project_node_id, item_id, fid, raw_value, ftype)
        log_event(workflow_logger, "info", "github_field_updated", field=field_name, value=raw_value)


# ── Full incident orchestration ───────────────────────────────────────────────

def create_incident_ticket(
    title: str,
    body: str,
    severity: str,
    incident_type: str,
    escalation_required: bool,
    ai_confidence: float,
    column: str = "New",
) -> dict[str, Any]:
    """
    End-to-end GitHub operation:
    1. Create issue
    2. Add to project
    3. Set Status column
    4. Update custom fields
    Returns: {issue_number, issue_url, item_id}
    """
    if not config.GITHUB_TOKEN:
        log_event(workflow_logger, "warning", "github_token_missing", note="Skipping GitHub operations")
        return {"issue_number": None, "issue_url": None, "item_id": None}

    labels = [severity, "ai-managed"]
    if escalation_required:
        labels.append("escalated")

    issue = create_issue(title, body, labels)
    issue_number   = issue["number"]
    issue_url      = issue["html_url"]
    issue_node_id  = issue["node_id"]

    project_node_id = get_project_node_id()
    item_id         = add_issue_to_project(issue_node_id, project_node_id)

    fields = get_project_fields(project_node_id)
    set_project_status(project_node_id, item_id, fields, column)
    update_incident_fields(
        project_node_id, item_id, fields,
        severity, incident_type, escalation_required, ai_confidence,
    )

    return {
        "issue_number": issue_number,
        "issue_url":    issue_url,
        "item_id":      item_id,
    }


def transition_project_column(item_id: str, new_column: str) -> None:
    """Move an existing project item to a different column."""
    if not config.GITHUB_TOKEN:
        return
    project_node_id = get_project_node_id()
    fields          = get_project_fields(project_node_id)
    set_project_status(project_node_id, item_id, fields, new_column)
