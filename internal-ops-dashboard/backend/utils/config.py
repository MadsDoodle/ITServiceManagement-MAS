import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # App
    APP_NAME: str = "Internal Ops Dashboard"
    ENV: str = field(default_factory=lambda: os.getenv("ENV", "development"))
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true")

    # API
    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    API_PORT: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))

    # Database
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "ops_dashboard.db"))

    # Failure simulation — flip these via env vars to test ITSM workflows
    SIMULATE_LATENCY: bool = field(default_factory=lambda: os.getenv("SIMULATE_LATENCY", "false").lower() == "true")
    SIMULATE_FAILURES: bool = field(default_factory=lambda: os.getenv("SIMULATE_FAILURES", "false").lower() == "true")
    LATENCY_MS: int = field(default_factory=lambda: int(os.getenv("LATENCY_MS", "2000")))
    FAILURE_RATE: float = field(default_factory=lambda: float(os.getenv("FAILURE_RATE", "0.3")))

    # Auth
    API_KEY: str = field(default_factory=lambda: os.getenv("API_KEY", "dev-secret-key-123"))

    # Logging
    LOG_DIR: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))


config = Config()