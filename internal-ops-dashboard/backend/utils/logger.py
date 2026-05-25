import json
import logging
import os
from datetime import datetime
from pathlib import Path

from backend.utils.config import config

Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)


def get_logger(name: str, log_file: str = "app.log") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    fh = logging.FileHandler(os.path.join(config.LOG_DIR, log_file))
    fh.setFormatter(fmt)

    logger.addHandler(console)
    logger.addHandler(fh)
    return logger


def log_structured(logger: logging.Logger, level: str, event: str, **kwargs):
    """Emit a structured JSON log entry — readable by future AI analysis."""
    payload = {"timestamp": datetime.utcnow().isoformat(), "event": event, **kwargs}
    getattr(logger, level.lower())(json.dumps(payload))


app_logger = get_logger("app", "app.log")
incident_logger = get_logger("incident", "incidents.log")
deployment_logger = get_logger("deployment", "deployment.log")