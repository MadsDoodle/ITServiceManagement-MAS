from datetime import datetime

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
STATUS_ICON = {
    "healthy": "🟢", "degraded": "🟡", "down": "🔴",
    "open": "🔴", "investigating": "🟡", "resolved": "🟢",
    "success": "🟢", "failed": "🔴", "rolled_back": "🟠", "pending": "⚪",
}


def format_severity(severity: str) -> str:
    icon = SEVERITY_ICON.get(severity.lower(), "⚫")
    return f"{icon} {severity.upper()}"


def format_status(status: str) -> str:
    icon = STATUS_ICON.get(status.lower(), "⚫")
    return f"{icon} {status.replace('_', ' ').title()}"


def format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts


def time_since(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        seconds = int((datetime.utcnow() - dt).total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except Exception:
        return ts