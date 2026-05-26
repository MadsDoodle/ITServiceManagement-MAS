"""
Structured logger for the Agentic ITSM platform.

Terminal (stdout) → ColourTerminalFormatter: human-readable, coloured banners
Log files         → JsonFormatter: machine-readable JSON for the dashboard viewer

The two formatters sit on separate handlers of the same logger so both get
every record independently.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from utils.config import config

# ── ANSI colour codes ─────────────────────────────────────────────────────────
_R  = "\033[0m"       # reset
_B  = "\033[1m"       # bold
_DM = "\033[2m"       # dim

_GREY   = "\033[38;5;244m"
_WHITE  = "\033[97m"
_CYAN   = "\033[96m"
_BLUE   = "\033[94m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_ORANGE = "\033[38;5;208m"
_RED    = "\033[91m"
_PURPLE = "\033[95m"
_TEAL   = "\033[38;5;37m"
_PINK   = "\033[38;5;205m"

# Level → colour
_LEVEL_COLOUR = {
    "DEBUG":    _GREY,
    "INFO":     _BLUE,
    "WARNING":  _YELLOW,
    "ERROR":    _RED,
    "CRITICAL": _RED + _B,
}

# Agent → colour
_AGENT_COLOUR = {
    "MonitoringAgent":         _TEAL,
    "ClassificationAgent":     _PURPLE,
    "RCAAgent":                _YELLOW,
    "RiskScoringAgent":        _BLUE,
    "EscalationAgent":         _ORANGE,
    "GitHubAgent":             _GREEN,
    "HumanReviewAgent":        _RED,
    "RemediationAgent":        _PURPLE,
    "RecoveryValidationAgent": _TEAL,
    "ResolutionAgent":         _GREEN,
    "NotificationAgent":       _CYAN,
}

# Landmark events → (banner_colour, icon, label)
_BANNERS: dict[str, tuple[str, str, str]] = {
    "workflow_start":           (_BLUE,   "🚀", "WORKFLOW START"),
    "workflow_end":             (_GREEN,  "✅", "WORKFLOW COMPLETE"),
    "workflow_cycle_start":     (_TEAL,   "🔄", "CYCLE START"),
    "workflow_resume":          (_CYAN,   "▶️ ", "WORKFLOW RESUME"),
    "new_incident_triggered":   (_PURPLE, "⚡", "INCIDENT TRIGGERED"),
    "monitoring_loop_started":  (_TEAL,   "▶️ ", "MONITORING LOOP STARTED"),
    "monitoring_loop_stopped":  (_GREY,   "⏹️ ", "MONITORING LOOP STOPPED"),
    "detection_tick_failed":    (_RED,    "💥", "DETECTION FAILED"),
    "github_issue_created":     (_GREEN,  "🐙", "GITHUB ISSUE CREATED"),
    "incident_resolved":        (_GREEN,  "🏁", "INCIDENT RESOLVED"),
    "escalation_evaluated":     (_ORANGE, "⚠️ ", "ESCALATION EVALUATED"),
    "human_review_required":    (_RED,    "👤", "HUMAN REVIEW REQUIRED"),
    "remediation_start":        (_PURPLE, "🔧", "REMEDIATION START"),
    "remediation_success":      (_GREEN,  "🔧", "REMEDIATION SUCCESS"),
    "remediation_failed":       (_RED,    "🔧", "REMEDIATION FAILED"),
    "failure_injected":         (_ORANGE, "💉", "FAILURE INJECTED"),
    "watchdog_started":         (_TEAL,   "🐕", "WATCHDOG STARTED"),
    "watchdog_loop_stalled":    (_RED,    "🐕", "WATCHDOG: LOOP STALLED"),
    "guardrail_budget_exhausted": (_RED,  "🛑", "GUARDRAIL: BUDGET EXHAUSTED"),
}

# Fields that are standard logging internals — skip from extras display
_STD_FIELDS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})
# Fields that are redundant in the human output
_SKIP_FIELDS = _STD_FIELDS | {"event", "logger", "timestamp", "level"}

_WIDTH = 72   # banner width


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _extras(record: logging.LogRecord, also_skip: set = frozenset()) -> str:
    """Collect extra fields from the record into a readable string."""
    parts = []
    for k, v in record.__dict__.items():
        if k in _SKIP_FIELDS or k in also_skip:
            continue
        if isinstance(v, str) and len(v) > 100:
            v = v[:97] + "…"
        if isinstance(v, list):
            v = str(v[:4]) + ("…" if len(v) > 4 else "")
        parts.append(f"{_DM}{k}{_R}={_WHITE}{v}{_R}")
    return "  ".join(parts)


def _banner(colour: str, icon: str, label: str, extra_line: str = "") -> str:
    bar = colour + "─" * _WIDTH + _R
    pad = " " * 2
    title = f"{colour}{_B}{pad}{icon}  {label}{_R}"
    lines = [bar, title]
    if extra_line:
        lines.append(f"{_DM}{pad}{extra_line}{_R}")
    lines.append(bar)
    return "\n".join(lines)


class ColourTerminalFormatter(logging.Formatter):
    """Human-readable, coloured terminal formatter for stdout."""

    def format(self, record: logging.LogRecord) -> str:
        event  = getattr(record, "event", record.getMessage())
        level  = record.levelname.upper()
        agent  = getattr(record, "agent", "")
        ts     = _ts()

        # ── Landmark banners ──────────────────────────────────────────────────
        if event in _BANNERS:
            colour, icon, label = _BANNERS[event]
            # Build the extra detail line for the banner
            extra_parts: list[str] = []
            for field in ("incident_id", "workflow_run_id", "agent",
                          "severity", "github_issue", "stage",
                          "error", "strategy", "type", "ms"):
                val = getattr(record, field, None)
                if val is not None:
                    extra_parts.append(f"{field}={val}")
            extra_line = "  ".join(extra_parts) + f"   {ts}"
            return _banner(colour, icon, label, extra_line)

        # ── Agent start / complete ─────────────────────────────────────────────
        if event in ("agent_start", "agent_complete") and agent:
            ac     = _AGENT_COLOUR.get(agent, _CYAN)
            action = "▸ starting" if event == "agent_start" else "✓ done"
            ex     = _extras(record, also_skip={"agent"})
            icon   = "▸" if event == "agent_start" else "✓"
            bullet_colour = _GREY if event == "agent_start" else ac
            return (
                f"{bullet_colour}{icon} {_B}{ac}{agent}{_R}"
                f"{_DM}  {action}{_R}"
                f"  {_GREY}{ts}{_R}"
                + (f"\n    {ex}" if ex else "")
            )

        # ── LLM fallback warning — make it obvious ────────────────────────────
        if "fallback" in event or "llm_" in event:
            error_val = getattr(record, "error", "")
            # Trim the long error message down to what matters
            if "invalid_api_key" in str(error_val) or "Incorrect API key" in str(error_val):
                return (
                    f"{_YELLOW}⚠  LLM FALLBACK{_R}  {_DM}(invalid API key — using deterministic fallback){_R}"
                    f"  {_GREY}{ts}{_R}"
                )
            short_err = str(error_val)[:80] if error_val else event
            return (
                f"{_YELLOW}⚠  {event}{_R}  {_DM}{short_err}{_R}"
                f"  {_GREY}{ts}{_R}"
            )

        # ── Standard rows ─────────────────────────────────────────────────────
        lc  = _LEVEL_COLOUR.get(level, _BLUE)
        ex  = _extras(record)
        lvl = f"{lc}{level:<8}{_R}"

        prefix = ""
        if agent:
            ac     = _AGENT_COLOUR.get(agent, _CYAN)
            prefix = f"{ac}{agent}{_R}  "

        msg = f"{_WHITE}{event}{_R}"

        line = f"  {_GREY}{ts}{_R}  {lvl}  {prefix}{msg}"
        if ex:
            line += f"\n    {ex}"
        return line


# ── JSON formatter (for log files — unchanged) ────────────────────────────────

_STD_SKIP_JSON = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _STD_SKIP_JSON:
                payload[k] = v
        return json.dumps(payload)


# ── Logger factory ─────────────────────────────────────────────────────────────

def _ensure_log_dir():
    os.makedirs(config.LOG_DIR, exist_ok=True)


def _build_logger(name: str, log_file: str) -> logging.Logger:
    _ensure_log_dir()
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        # stdout → colour
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(ColourTerminalFormatter())
        logger.addHandler(sh)

        # file → JSON
        fh = RotatingFileHandler(
            os.path.join(config.LOG_DIR, log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)

    return logger


# ── Named loggers ─────────────────────────────────────────────────────────────
workflow_logger     = _build_logger("workflow",      "workflow.log")
incident_logger     = _build_logger("incidents",     "incidents.log")
notification_logger = _build_logger("notifications", "notifications.log")
agent_logger        = _build_logger("agent",         "workflow.log")


def log_event(logger: logging.Logger, level: str, event: str, **kwargs):
    """Convenience wrapper — attaches an `event` key to every log record.

    Filters out any kwargs that clash with Python's reserved LogRecord
    attributes so they never raise 'Attempt to overwrite X in LogRecord'.
    """
    # These are attributes Python sets on every LogRecord internally.
    # Passing them as `extra` kwargs causes a ValueError.
    _RESERVED = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "taskName",
    })
    safe_kwargs = {k: v for k, v in kwargs.items() if k not in _RESERVED}
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(event, extra={"event": event, **safe_kwargs})
