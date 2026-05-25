import os
from datetime import datetime, timedelta
from pathlib import Path

from backend.utils.config import config

LOG_FILES = {
    "app": os.path.join(config.LOG_DIR, "app.log"),
    "incidents": os.path.join(config.LOG_DIR, "incidents.log"),
    "deployment": os.path.join(config.LOG_DIR, "deployment.log"),
}


def read_log_lines(log_type: str = "app", lines: int = 100, since_minutes: int = None) -> list[dict]:
    log_path = LOG_FILES.get(log_type)
    if not log_path or not Path(log_path).exists():
        return []

    with open(log_path, "r") as f:
        raw_lines = f.readlines()

    cutoff = datetime.utcnow() - timedelta(minutes=since_minutes) if since_minutes else None
    result = []

    for line in reversed(raw_lines):
        line = line.strip()
        if not line:
            continue
        parsed = _parse_line(line)
        if cutoff and parsed.get("timestamp"):
            try:
                if datetime.fromisoformat(parsed["timestamp"]) < cutoff:
                    break
            except ValueError:
                pass
        result.append(parsed)
        if len(result) >= lines:
            break

    return result


def _parse_line(line: str) -> dict:
    parts = line.split(" | ", 3)
    if len(parts) == 4:
        return {
            "timestamp": parts[0].strip(),
            "logger": parts[1].strip(),
            "level": parts[2].strip(),
            "message": parts[3].strip(),
        }
    return {"raw": line}