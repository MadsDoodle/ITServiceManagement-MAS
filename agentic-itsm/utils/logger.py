"""
Structured JSON logger used across all agents and services.
Writes to rotating log files under logs/ and to stdout.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from utils.config import config


def _ensure_log_dir():
    os.makedirs(config.LOG_DIR, exist_ok=True)


def _json_formatter(record: logging.LogRecord) -> str:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    # merge any extra fields passed via the `extra` kwarg
    for key, val in record.__dict__.items():
        if key not in (
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
        ):
            payload[key] = val
    return json.dumps(payload)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return _json_formatter(record)


def _build_logger(name: str, log_file: str) -> logging.Logger:
    _ensure_log_dir()
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        fmt = JsonFormatter()

        # stdout handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        # rotating file handler
        fh = RotatingFileHandler(
            os.path.join(config.LOG_DIR, log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ── Named loggers ─────────────────────────────────────────────────────────────
workflow_logger      = _build_logger("workflow",      "workflow.log")
incident_logger      = _build_logger("incidents",     "incidents.log")
notification_logger  = _build_logger("notifications", "notifications.log")
agent_logger         = _build_logger("agent",         "workflow.log")


def log_event(logger: logging.Logger, level: str, event: str, **kwargs):
    """Convenience wrapper that attaches an `event` key to every log record."""
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(event, extra={"event": event, **kwargs})
