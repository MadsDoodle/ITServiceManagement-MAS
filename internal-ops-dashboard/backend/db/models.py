from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from backend.db.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)       # critical | high | medium | low
    status = Column(String(50), default="open")         # open | investigating | resolved
    affected_service = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    commit_ref = Column(String(100), nullable=True)     # correlate with deployment


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(String(50), unique=True, nullable=False)
    version = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")     # pending | success | failed | rolled_back
    commit_ref = Column(String(100), nullable=False)
    deployed_by = Column(String(100), default="ci-bot")
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class ServiceStatus(Base):
    __tablename__ = "service_status"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), default="healthy")     # healthy | degraded | down
    uptime_pct = Column(Float, default=100.0)
    last_checked = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    service_name = Column(String(100), nullable=False)
    request_latency_ms = Column(Float, nullable=True)
    error_rate_pct = Column(Float, nullable=True)
    requests_per_min = Column(Float, nullable=True)
    active_incidents = Column(Integer, default=0)