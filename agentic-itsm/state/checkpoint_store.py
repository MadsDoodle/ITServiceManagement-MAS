"""
Durable LangGraph checkpoint store using SqliteSaver.

Provides graph-level execution persistence so a crash doesn't lose
the current node position or in-flight transition state.
Falls back to MemorySaver gracefully if SqliteSaver is unavailable.
"""
from __future__ import annotations

import sqlite3

from utils.config import config
from utils.logger import log_event, workflow_logger

_checkpointer = None


def get_checkpointer():
    """
    Return a singleton LangGraph checkpointer.
    SqliteSaver (durable) when available, MemorySaver as fallback.
    The connection is kept open for the lifetime of the process.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # langgraph ≥ 0.2.x
        conn = sqlite3.connect(
            config.CHECKPOINT_DB_PATH,
            check_same_thread=False,
        )
        _checkpointer = SqliteSaver(conn)
        log_event(
            workflow_logger, "info", "checkpointer_initialized",
            type="SqliteSaver", path=config.CHECKPOINT_DB_PATH,
        )
    except Exception as exc:
        log_event(
            workflow_logger, "warning", "checkpointer_fallback",
            reason=str(exc), fallback="MemorySaver",
        )
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()

    return _checkpointer


def reset():
    """Force re-initialisation (e.g. in tests)."""
    global _checkpointer
    _checkpointer = None
