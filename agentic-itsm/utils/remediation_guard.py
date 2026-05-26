"""
Remediation Guardrails — prevents runaway auto-remediation.

Enforces three independent limits:
  1. Cooldown — N seconds must pass between actions on the same service
  2. Retry budget — max retries per incident before forcing escalation
  3. Hourly rate limit — max actions per service per rolling hour

If any limit is breached, check() returns (False, reason).
The remediation_agent treats a False result as a forced escalation.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from utils.logger import log_event, workflow_logger

_guard_lock = threading.Lock()

# service_name → monotonic timestamp of last successful remediation start
_last_action: dict[str, float] = {}

# service_name → deque of wall-clock timestamps (for hourly rate window)
_action_history: dict[str, deque] = defaultdict(lambda: deque())

_RATE_WINDOW_SECONDS = 3600   # rolling 1-hour window


def check(service_name: str, strategy: str, state: dict) -> tuple[bool, str]:
    """
    Decide whether remediation is permitted right now.
    Returns: (allowed: bool, reason: str)

    Callers should force escalation when allowed is False.
    """
    from utils.config import config

    with _guard_lock:
        retries      = state.get("remediation_retries", 0)
        max_retries  = config.MAX_REMEDIATION_RETRIES
        cooldown     = config.REMEDIATION_COOLDOWN_SECONDS
        max_per_hour = config.MAX_ACTIONS_PER_HOUR_PER_SERVICE
        now_mono     = time.monotonic()
        now_wall     = time.time()

        # 1. Hard retry budget
        if retries >= max_retries:
            reason = (
                f"Retry budget exhausted ({retries}/{max_retries}) for "
                f"'{service_name}' — forcing escalation"
            )
            log_event(workflow_logger, "warning", "guardrail_budget_exhausted",
                      service=service_name, retries=retries)
            return False, reason

        # 2. Per-service cooldown window
        last    = _last_action.get(service_name, 0.0)
        elapsed = now_mono - last
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            reason = (
                f"Cooldown active for '{service_name}': "
                f"{elapsed:.0f}s elapsed, {remaining:.0f}s remaining"
            )
            log_event(workflow_logger, "info", "guardrail_cooldown_active",
                      service=service_name, remaining_s=remaining)
            return False, reason

        # 3. Hourly rate limit
        history = _action_history[service_name]
        cutoff  = now_wall - _RATE_WINDOW_SECONDS
        while history and history[0] < cutoff:
            history.popleft()
        if len(history) >= max_per_hour:
            reason = (
                f"Hourly rate limit reached for '{service_name}': "
                f"{len(history)}/{max_per_hour} actions in the last hour"
            )
            log_event(workflow_logger, "warning", "guardrail_rate_limit",
                      service=service_name, count=len(history))
            return False, reason

    return True, "allowed"


def record_action(service_name: str) -> None:
    """Record that a remediation action was dispatched. Call after _execute()."""
    with _guard_lock:
        _last_action[service_name] = time.monotonic()
        _action_history[service_name].append(time.time())
    log_event(workflow_logger, "debug", "guardrail_action_recorded", service=service_name)


def reset_service(service_name: str) -> None:
    """Clear all cooldown and rate-limit state for a service (manual reset)."""
    with _guard_lock:
        _last_action.pop(service_name, None)
        _action_history[service_name].clear()
    log_event(workflow_logger, "info", "guardrail_service_reset", service=service_name)
