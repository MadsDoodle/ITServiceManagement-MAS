"""
Gmail notification service via SMTP with TLS.
Uses an App Password — no OAuth flow required for local operation.
Gracefully skips sending if credentials are not configured.
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.config import config
from utils.logger import log_event, notification_logger


def send_notification(
    subject: str,
    body: str,
    to_address: str | None = None,
    html_body: str | None = None,
) -> bool:
    """
    Send an email via Gmail SMTP.
    Returns True on success, False if credentials missing or send fails.
    """
    recipient = to_address or config.ESCALATION_EMAIL
    if not all([config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD, recipient]):
        log_event(
            notification_logger, "warning", "gmail_skipped",
            reason="GMAIL_SENDER / GMAIL_APP_PASSWORD / ESCALATION_EMAIL not configured",
        )
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
        log_event(
            notification_logger, "info", "gmail_sent",
            to=recipient, subject=subject,
        )
        return True
    except Exception as exc:
        log_event(
            notification_logger, "error", "gmail_failed",
            error=str(exc), to=recipient,
        )
        return False


def send_escalation_email(state: dict, email_body: str) -> bool:
    """Convenience wrapper for escalation notifications."""
    sev     = state.get("severity", "Unknown")
    itype   = state.get("incident_type", "Unknown")
    subject = f"[ESCALATION] {sev} Incident — {itype} | {state.get('incident_id', 'N/A')}"
    html = _build_html_email(state, email_body)
    return send_notification(subject=subject, body=email_body, html_body=html)


def send_resolution_email(state: dict) -> bool:
    """Notify when an incident has been resolved."""
    sev    = state.get("severity", "Unknown")
    iid    = state.get("incident_id", "N/A")
    url    = state.get("github_issue_url", "N/A")
    body   = (
        f"Incident {iid} ({sev}) has been resolved.\n"
        f"GitHub Issue: {url}\n"
        f"Root Cause: {state.get('root_cause_summary', 'N/A')}\n"
    )
    subject = f"[RESOLVED] {sev} Incident {iid}"
    return send_notification(subject=subject, body=body)


def _build_html_email(state: dict, plain_body: str) -> str:
    sev    = state.get("severity", "Unknown")
    itype  = state.get("incident_type", "Unknown")
    iid    = state.get("incident_id", "N/A")
    url    = state.get("github_issue_url", "#")
    esc    = "Yes" if state.get("escalation_required") else "No"
    colour = {"P1": "#d73a4a", "P2": "#e4e669", "P3": "#0075ca", "Low": "#cfd3d7"}.get(sev, "#888")
    reasons_html = "".join(
        f"<li>{r}</li>" for r in state.get("escalation_reasons", [])
    )
    return f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;">
<h2 style="color:{colour};">🚨 ITSM Incident Alert — {sev}</h2>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:6px;font-weight:bold;">Incident ID</td><td style="padding:6px;">{iid}</td></tr>
  <tr><td style="padding:6px;font-weight:bold;">Type</td><td style="padding:6px;">{itype}</td></tr>
  <tr><td style="padding:6px;font-weight:bold;">Escalation</td><td style="padding:6px;">{esc}</td></tr>
  <tr><td style="padding:6px;font-weight:bold;">Confidence</td><td style="padding:6px;">{state.get('ai_confidence',0):.0%}</td></tr>
  <tr><td style="padding:6px;font-weight:bold;">GitHub Issue</td><td style="padding:6px;"><a href="{url}">{url}</a></td></tr>
</table>
<h3>Escalation Reasons</h3><ul>{reasons_html or "<li>N/A</li>"}</ul>
<h3>Root Cause Summary</h3>
<p>{state.get('root_cause_summary','Not available')}</p>
<hr/>
<pre style="font-size:12px;color:#555;">{plain_body}</pre>
</body></html>
"""
