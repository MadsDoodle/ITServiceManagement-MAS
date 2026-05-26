"""
Structured logger for the Internal Ops Dashboard backend.

Terminal (stdout) → ColourTerminalFormatter: coloured, human-readable HTTP logs
Log files         → pipe-delimited JSON: machine-readable for the dashboard reader
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from backend.utils.config import config

Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)

# ── ANSI codes ────────────────────────────────────────────────────────────────
_R      = "\033[0m"
_B      = "\033[1m"
_DM     = "\033[2m"
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

_LEVEL_COLOUR = {
    "DEBUG":    _GREY,
    "INFO":     _BLUE,
    "WARNING":  _YELLOW,
    "ERROR":    _RED,
    "CRITICAL": _RED + _B,
}

# HTTP status code → colour
def _status_colour(code: int) -> str:
    if code < 300:  return _GREEN
    if code < 400:  return _CYAN
    if code < 500:  return _YELLOW
    return _RED

# Method → colour
_METHOD_COLOUR = {
    "GET":    _BLUE,
    "POST":   _GREEN,
    "PATCH":  _YELLOW,
    "PUT":    _ORANGE,
    "DELETE": _RED,
}

# Special event banners
_BANNERS: dict[str, tuple[str, str, str]] = {
    "app_startup":                  (_TEAL,   "🟢", "OPS DASHBOARD STARTED"),
    "app_shutdown":                 (_GREY,   "⏹️ ", "OPS DASHBOARD SHUTTING DOWN"),
    "simulated_crash_triggered":    (_RED,    "💥", "CRASH SIMULATED"),
    "incident_created":             (_ORANGE, "🚨", "INCIDENT CREATED"),
    "incident_updated":             (_YELLOW, "📝", "INCIDENT UPDATED"),
    "deployment_started":           (_CYAN,   "📦", "DEPLOYMENT STARTED"),
    "deployment_status_updated":    (_BLUE,   "📦", "DEPLOYMENT UPDATED"),
    "auth_failed":                  (_RED,    "🔐", "AUTH FAILURE"),
    "auth_failure_injected":        (_RED,    "💉", "AUTH FAILURE INJECTED"),
}

_WIDTH = 68


def _banner(colour: str, icon: str, label: str, detail: str = "") -> str:
    bar = colour + "─" * _WIDTH + _R
    pad = "  "
    title = f"{colour}{_B}{pad}{icon}  {label}{_R}"
    lines = [bar, title]
    if detail:
        lines.append(f"{_DM}{pad}{detail}{_R}")
    lines.append(bar)
    return "\n".join(lines)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


class ColourTerminalFormatter(logging.Formatter):
    """Human-readable coloured formatter for the ops dashboard terminal."""

    def format(self, record: logging.LogRecord) -> str:
        ts  = _ts()
        msg = record.getMessage()

        # Try to parse the JSON payload inside the message
        payload: dict = {}
        try:
            payload = json.loads(msg)
        except Exception:
            pass

        event = payload.get("event", "")
        level = record.levelname.upper()
        lc    = _LEVEL_COLOUR.get(level, _BLUE)

        # ── Landmark banners ──────────────────────────────────────────────────
        if event in _BANNERS:
            colour, icon, label = _BANNERS[event]
            detail_parts = [
                f"{k}={v}" for k, v in payload.items()
                if k not in ("event", "timestamp") and v is not None
            ]
            detail = "  ".join(detail_parts[:5]) + f"   {ts}"
            return _banner(colour, icon, label, detail)

        # ── HTTP request lines ────────────────────────────────────────────────
        if event == "http_request":
            method   = payload.get("method", "?")
            path     = payload.get("path", "?")
            status   = payload.get("status_code", 0)
            duration = payload.get("duration_ms", 0)
            mc = _METHOD_COLOUR.get(method, _WHITE)
            sc = _status_colour(int(status))
            # Dim polling / health paths slightly
            dim = _DM if path in ("/health/", "/metrics/") else ""
            return (
                f"{dim}  {_GREY}{ts}{_R}  "
                f"{mc}{_B}{method:<6}{_R}  "
                f"{_WHITE}{path:<40}{_R}  "
                f"{sc}{_B}{status}{_R}  "
                f"{_DM}{duration:.1f}ms{_R}"
            )

        # ── Failure simulation events ─────────────────────────────────────────
        if "simulat" in event or "inject" in event:
            detail = "  ".join(
                f"{k}={v}" for k, v in payload.items()
                if k not in ("event", "timestamp")
            )
            return _banner(_ORANGE, "💉", f"SIMULATE: {event.upper()}", f"{detail}  {ts}")

        # ── CRITICAL level always gets a banner ───────────────────────────────
        if level == "CRITICAL":
            short = str(payload or msg)[:80]
            return _banner(_RED, "🔴", f"CRITICAL — {event or msg}", f"{short}  {ts}")

        # ── Standard rows ─────────────────────────────────────────────────────
        # For JSON payloads, show key fields inline
        if payload:
            parts = [
                f"{_DM}{k}{_R}={_WHITE}{str(v)[:60]}{_R}"
                for k, v in payload.items()
                if k not in ("event", "timestamp") and v is not None
            ]
            detail_str = "  ".join(parts[:5])
            event_str  = f"{_WHITE}{event or msg}{_R}"
        else:
            detail_str = ""
            event_str  = f"{_WHITE}{msg[:100]}{_R}"

        lvl_badge = f"{lc}{level:<8}{_R}"
        name_dim  = f"{_DM}[{record.name}]{_R}"
        line      = f"  {_GREY}{ts}{_R}  {lvl_badge}  {name_dim}  {event_str}"
        if detail_str:
            line += f"\n    {detail_str}"
        return line


# ── Pipe-delimited file formatter (unchanged — dashboard reads this) ───────────

class PipeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        return f"{ts} | {record.name} | {record.levelname} | {record.getMessage()}"


# ── Logger factory ─────────────────────────────────────────────────────────────

def get_logger(name: str, log_file: str = "app.log") -> logging.Logger:
    logger = logging.getLogger(f"ops.{name}")
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    if logger.handlers:
        return logger

    # stdout → colour
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(ColourTerminalFormatter())

    # file → pipe-delimited (unchanged format for ops dashboard log reader)
    fh = logging.FileHandler(os.path.join(config.LOG_DIR, log_file))
    fh.setFormatter(PipeFormatter())

    logger.addHandler(sh)
    logger.addHandler(fh)
    logger.propagate = False
    return logger


def log_structured(logger: logging.Logger, level: str, event: str, **kwargs):
    """Emit a structured JSON log entry (file) + coloured terminal output."""
    payload = {"timestamp": datetime.utcnow().isoformat(), "event": event, **kwargs}
    getattr(logger, level.lower())(json.dumps(payload))


# ── Named loggers ─────────────────────────────────────────────────────────────
app_logger        = get_logger("app",        "app.log")
incident_logger   = get_logger("incident",   "incidents.log")
deployment_logger = get_logger("deployment", "deployment.log")
