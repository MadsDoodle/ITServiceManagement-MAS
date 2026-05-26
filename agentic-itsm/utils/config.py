"""
Centralised configuration — loaded once from environment / .env file.
All secrets and external endpoints live here; never hardcoded elsewhere.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgenticITSMConfig:
    # ── Monitored system ──────────────────────────────────────────────────────
    OPS_DASHBOARD_URL: str = field(
        default_factory=lambda: os.getenv("OPS_DASHBOARD_URL", "http://localhost:8000")
    )
    OPS_API_KEY: str = field(
        default_factory=lambda: os.getenv("OPS_API_KEY", "dev-secret-key-123")
    )

    # ── Monitoring behaviour ─────────────────────────────────────────────────
    POLL_INTERVAL_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    )
    LATENCY_THRESHOLD_MS: float = field(
        default_factory=lambda: float(os.getenv("LATENCY_THRESHOLD_MS", "500"))
    )
    ERROR_RATE_THRESHOLD_PCT: float = field(
        default_factory=lambda: float(os.getenv("ERROR_RATE_THRESHOLD_PCT", "5.0"))
    )

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    # ── GitHub ───────────────────────────────────────────────────────────────
    GITHUB_TOKEN: str = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN", "")
    )
    GITHUB_REPO_OWNER: str = field(
        default_factory=lambda: os.getenv("GITHUB_REPO_OWNER", "")
    )
    GITHUB_REPO_NAME: str = field(
        default_factory=lambda: os.getenv("GITHUB_REPO_NAME", "")
    )
    GITHUB_PROJECT_NUMBER: int = field(
        default_factory=lambda: int(os.getenv("GITHUB_PROJECT_NUMBER", "1"))
    )

    # ── Gmail / SMTP ─────────────────────────────────────────────────────────
    GMAIL_SENDER: str = field(
        default_factory=lambda: os.getenv("GMAIL_SENDER", "")
    )
    GMAIL_APP_PASSWORD: str = field(
        default_factory=lambda: os.getenv("GMAIL_APP_PASSWORD", "")
    )
    ESCALATION_EMAIL: str = field(
        default_factory=lambda: os.getenv("ESCALATION_EMAIL", "")
    )

    # ── Escalation thresholds ────────────────────────────────────────────────
    LOW_CONFIDENCE_THRESHOLD: float = field(
        default_factory=lambda: float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.6"))
    )
    LARGE_CHANGE_LINE_THRESHOLD: int = field(
        default_factory=lambda: int(os.getenv("LARGE_CHANGE_LINE_THRESHOLD", "50"))
    )

    # ── SQLite state DB ──────────────────────────────────────────────────────
    STATE_DB_PATH: str = field(
        default_factory=lambda: os.getenv("STATE_DB_PATH", "agentic_itsm.db")
    )
    CHECKPOINT_DB_PATH: str = field(
        default_factory=lambda: os.getenv("CHECKPOINT_DB_PATH", "agentic_itsm_checkpoints.db")
    )

    # ── Logging ──────────────────────────────────────────────────────────────
    LOG_DIR: str = field(
        default_factory=lambda: os.getenv("LOG_DIR", "logs")
    )
    LOG_LEVEL: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    # ── Continuous monitoring ────────────────────────────────────────────────
    MONITORING_STABILITY_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("MONITORING_STABILITY_SECONDS", "60"))
    )
    MONITORING_CHECK_INTERVAL: int = field(
        default_factory=lambda: int(os.getenv("MONITORING_CHECK_INTERVAL", "30"))
    )
    MAX_REMEDIATION_RETRIES: int = field(
        default_factory=lambda: int(os.getenv("MAX_REMEDIATION_RETRIES", "3"))
    )

    # ── Remediation guardrails ───────────────────────────────────────────────
    REMEDIATION_COOLDOWN_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("REMEDIATION_COOLDOWN_SECONDS", "20"))
    )
    MAX_ACTIONS_PER_HOUR_PER_SERVICE: int = field(
        default_factory=lambda: int(os.getenv("MAX_ACTIONS_PER_HOUR_PER_SERVICE", "10"))
    )

    # ── Watchdog (self-monitoring) ───────────────────────────────────────────
    WATCHDOG_STALE_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("WATCHDOG_STALE_SECONDS", "120"))
    )

    # ── Demo / observability ─────────────────────────────────────────────────
    # When True, escalated incidents are auto-approved so the full lifecycle
    # runs without waiting for a human. Set False for real operational use.
    AUTO_APPROVE_ESCALATIONS: bool = field(
        default_factory=lambda: os.getenv("AUTO_APPROVE_ESCALATIONS", "true").lower() == "true"
    )
    # Seconds to pause between lifecycle stage transitions so GitHub board
    # column changes are visibly observable.
    STAGE_TRANSITION_DELAY_SECONDS: int = field(
        default_factory=lambda: int(os.getenv("STAGE_TRANSITION_DELAY_SECONDS", "10"))
    )

    # ── FastAPI sidecar ──────────────────────────────────────────────────────
    API_PORT: int = field(
        default_factory=lambda: int(os.getenv("API_PORT", "8503"))
    )

    # ── Dashboard ────────────────────────────────────────────────────────────
    DASHBOARD_PORT: int = field(
        default_factory=lambda: int(os.getenv("DASHBOARD_PORT", "8502"))
    )


config = AgenticITSMConfig()
