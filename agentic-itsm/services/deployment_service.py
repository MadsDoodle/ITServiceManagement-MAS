"""
Deployment correlation helper — thin wrapper around the monitored system's
deployment API with local caching to reduce redundant calls.
"""
from __future__ import annotations

import time
from typing import Optional

from services.monitoring_service import fetch_deployments
from utils.logger import log_event, workflow_logger

_cache: list[dict] = []
_cache_ts: float = 0.0
_CACHE_TTL: int = 60  # seconds


def get_recent_deployments(limit: int = 10, force_refresh: bool = False) -> list[dict]:
    """Return cached deployment list, refreshing after TTL."""
    global _cache, _cache_ts
    now = time.monotonic()
    if force_refresh or (now - _cache_ts > _CACHE_TTL):
        _cache = fetch_deployments(limit=limit)
        _cache_ts = now
        log_event(workflow_logger, "info", "deployments_refreshed", count=len(_cache))
    return _cache


def find_correlated_deployment(commit_ref: str) -> Optional[dict]:
    """Look up a deployment by commit_ref."""
    deps = get_recent_deployments()
    return next((d for d in deps if d.get("commit_ref") == commit_ref), None)


def get_failed_deployments() -> list[dict]:
    """Return only failed or rolled-back deployments from recent list."""
    return [d for d in get_recent_deployments() if d.get("status") in ("failed", "rolled_back")]


def get_latest_deployment() -> Optional[dict]:
    deps = get_recent_deployments()
    return deps[0] if deps else None
