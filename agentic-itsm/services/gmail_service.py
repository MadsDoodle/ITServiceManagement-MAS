"""
Gmail notification service — stage-based HTML emails with coloured banners.
Uses SMTP/SSL with an App Password. Gracefully skips if not configured.
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.config import config
from utils.constants import (
    NOTIF_BANNER_COLOURS,
    NOTIF_INCIDENT_DETECTED,
    NOTIF_TRIAGE_STARTED,
    NOTIF_INVESTIGATION_START,
    NOTIF_REMEDIATION_START,
    NOTIF_ESCALATED,
    NOTIF_MONITORING_START,
    NOTIF_RESOLVED,
)
from utils.logger import log_event, notification_logger

# ── Stage display labels ──────────────────────────────────────────────────────
_STAGE_LABELS = {
    NOTIF_INCIDENT_DETECTED:   "🔵 Incident Detected",
    NOTIF_TRIAGE_STARTED:      "🟡 Triage Started",
    NOTIF_INVESTIGATION_START: "🟠 Investigation Started",
    NOTIF_REMEDIATION_START:   "🟣 Fix In Progress",
    NOTIF_ESCALATED:           "🔴 Escalated to Human",
    NOTIF_MONITORING_START:    "🩵 Monitoring Recovery",
    NOTIF_RESOLVED:            "🟢 Incident Resolved",
}


def send_notification(
    subject: str,
    body: str,
    to_address: str | None = None,
    html_body: str | None = None,
) -> bool:
    recipient = to_address or config.ESCALATION_EMAIL
    if not all([config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD, recipient]):
        log_event(notification_logger, "warning", "gmail_skipped",
                  reason="credentials not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.GMAIL_SENDER
    msg["To"]      = recipient

    msg.attach(MIMEText(body, "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
            server.sendmail(config.GMAIL_SENDER, recipient, msg.as_string())
        log_event(notification_logger, "info", "gmail_sent",
                  to=recipient, subject=subject)
        return True
    except Exception as exc:
        log_event(notification_logger, "error", "gmail_failed",
                  error=str(exc), to=recipient)
        return False


def send_stage_notification(stage: str, state: dict, email_body: str) -> bool:
    """Send a stage-specific lifecycle notification email."""
    sev      = state.get("severity", "Unknown")
    iid      = state.get("incident_id", "N/A")
    itype    = state.get("incident_type", "Unknown")
    label    = _STAGE_LABELS.get(stage, stage.replace("_", " ").title())
    subject  = f"[ITSM] {label} — {sev} {itype} | {iid}"
    html     = _build_stage_html(stage, state, email_body)
    return send_notification(subject=subject, body=email_body, html_body=html)


# Legacy wrappers kept for backward compat
def send_escalation_email(state: dict, email_body: str) -> bool:
    return send_stage_notification(NOTIF_ESCALATED, state, email_body)


def send_resolution_email(state: dict) -> bool:
    sev  = state.get("severity", "Unknown")
    iid  = state.get("incident_id", "N/A")
    url  = state.get("github_issue_url", "N/A")
    body = (
        f"Incident {iid} ({sev}) has been resolved.\n"
        f"GitHub Issue: {url}\n"
        f"Root Cause: {state.get('root_cause_summary', 'N/A')}\n"
    )
    return send_stage_notification(NOTIF_RESOLVED, state, body)


def _build_stage_html(stage: str, state: dict, plain_body: str) -> str:
    """Build a full HTML email with coloured stage banner."""
    colour       = NOTIF_BANNER_COLOURS.get(stage, "#888")
    stage_label  = _STAGE_LABELS.get(stage, stage)
    sev          = state.get("severity", "Unknown")
    itype        = state.get("incident_type", "Unknown")
    iid          = state.get("incident_id", "N/A")
    affected     = (state.get("anomalies") or [{}])[0].get("affected_service", "Unknown")
    url          = state.get("github_issue_url") or "#"
    issue_num    = state.get("github_issue_number")
    issue_link   = f"<a href='{url}'>#{issue_num}</a>" if issue_num else "Not yet created"
    esc          = "⚠️ YES — Human review required" if state.get("escalation_required") else "✅ No"
    rca          = state.get("root_cause_summary") or "Pending investigation"
    remediation  = state.get("remediation_detail") or "Not yet attempted"
    lifecycle    = state.get("lifecycle_stage", "unknown").replace("_", " ").title()
    ts           = state.get("created_at", "")[:19].replace("T", " ")
    esc_reasons  = "".join(f"<li>{r}</li>" for r in state.get("escalation_reasons", []))
    risk         = state.get("risk_score", 0.0)
    confidence   = state.get("ai_confidence", 0.0)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;background:#f5f5f5;padding:20px;">
  <!-- Banner -->
  <div style="background:{colour};color:white;padding:18px 20px;border-radius:8px 8px 0 0;">
    <h2 style="margin:0;font-size:1.3em;">{stage_label}</h2>
    <p style="margin:4px 0 0;opacity:0.9;font-size:0.9em;">Agentic ITSM Platform · {ts}</p>
  </div>
  <!-- Content -->
  <div style="background:white;padding:20px;border-radius:0 0 8px 8px;border:1px solid #ddd;">
    <table style="border-collapse:collapse;width:100%;font-size:0.95em;">
      <tr style="background:#f9f9f9;">
        <td style="padding:8px 12px;font-weight:bold;color:#333;width:40%;">Incident ID</td>
        <td style="padding:8px 12px;font-family:monospace;">{iid}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Severity</td>
        <td style="padding:8px 12px;font-weight:bold;color:{colour};">{sev}</td>
      </tr>
      <tr style="background:#f9f9f9;">
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Incident Type</td>
        <td style="padding:8px 12px;">{itype}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Affected Service</td>
        <td style="padding:8px 12px;">{affected}</td>
      </tr>
      <tr style="background:#f9f9f9;">
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Lifecycle Stage</td>
        <td style="padding:8px 12px;">{lifecycle}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Escalation</td>
        <td style="padding:8px 12px;">{esc}</td>
      </tr>
      <tr style="background:#f9f9f9;">
        <td style="padding:8px 12px;font-weight:bold;color:#333;">AI Confidence</td>
        <td style="padding:8px 12px;">{confidence:.0%}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;font-weight:bold;color:#333;">Risk Score</td>
        <td style="padding:8px 12px;">{risk:.2f} / 1.00</td>
      </tr>
      <tr style="background:#f9f9f9;">
        <td style="padding:8px 12px;font-weight:bold;color:#333;">GitHub Issue</td>
        <td style="padding:8px 12px;">{issue_link}</td>
      </tr>
    </table>

    <h3 style="color:#333;margin-top:20px;">Root Cause Analysis</h3>
    <p style="background:#f5f5f5;padding:12px;border-left:4px solid {colour};border-radius:4px;">{rca}</p>

    {'<h3 style="color:#333;">Escalation Reasons</h3><ul>' + esc_reasons + '</ul>' if esc_reasons else ''}

    <h3 style="color:#333;">Remediation</h3>
    <p style="background:#f5f5f5;padding:12px;border-left:4px solid #555;border-radius:4px;">{remediation}</p>

    <h3 style="color:#333;">AI Summary</h3>
    <pre style="background:#f5f5f5;padding:12px;font-size:0.85em;white-space:pre-wrap;border-radius:4px;">{plain_body[:600]}</pre>

    <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
    <p style="color:#888;font-size:0.8em;">Generated by the Agentic ITSM Platform · Do not reply to this email.</p>
  </div>
</body>
</html>"""
