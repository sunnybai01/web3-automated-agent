import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float,
    ForeignKey, UniqueConstraint, Index, JSON, Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class RawSignal(Base):
    """Original fetch records before dedup — every scraped item lands here."""
    __tablename__ = "raw_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False, index=True)  # rss|github_api|twitter|discord|web_scraper|rsshub
    source_name = Column(String(128), nullable=False, index=True)
    raw_content = Column(Text, nullable=False)
    raw_url = Column(Text, nullable=True)
    canonical_url = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_raw_signals_canonical_url"),
        Index("ix_raw_signals_fetched", "source_name", "fetched_at"),
    )


class Event(Base):
    """Deduped, verified, structured event — the master entity (Event-Centric design)."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32), nullable=False, index=True)  # grant|hackathon|bounty|other
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    amount = Column(String(256), nullable=True)
    track = Column(String(128), nullable=True)
    ecosystem = Column(String(64), nullable=True, index=True)
    application_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    source_platform = Column(String(128), nullable=True)

    # Zero-trust verification
    is_verified = Column(Boolean, default=False)
    verification_log = Column(JSON, nullable=True)

    # Scoring (4D matrix)
    score_roi = Column(Float, nullable=True)
    score_reputation = Column(Float, nullable=True)
    score_timeliness = Column(Float, nullable=True)
    score_strategy = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True, index=True)

    # Heat tracking — each new source adds weight
    heat_count = Column(Integer, default=1)

    # Slack dispatch tracking
    status = Column(String(32), default="new")  # new|pushed|archived|expired|fraud
    slack_ts = Column(String(64), nullable=True)
    slack_channel_id = Column(String(32), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    sources = relationship("EventSource", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_events_type_score", "event_type", "final_score"),
        Index("ix_events_status", "status", "created_at"),
        Index("ix_events_window", "created_at", "ecosystem"),
    )


class EventSource(Base):
    """Multi-source evidence chain — one event may have many source traces."""
    __tablename__ = "event_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False)
    source_name = Column(String(128), nullable=False)
    source_url = Column(Text, nullable=True)
    raw_signal_id = Column(Integer, ForeignKey("raw_signals.id", ondelete="SET NULL"), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="sources")

    __table_args__ = (
        UniqueConstraint("event_id", "source_url", name="uq_event_source_url"),
    )


class SourceHealth(Base):
    """Per-source health monitoring."""
    __tablename__ = "source_health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(128), unique=True, nullable=False, index=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_fetch_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    status = Column(String(16), default="healthy")  # healthy|degraded|down
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ScheduleLog(Base):
    """Job execution audit log."""
    __tablename__ = "schedule_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(128), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    items_fetched = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_deduped = Column(Integer, default=0)
    items_classified = Column(Integer, default=0)
    items_verified = Column(Integer, default=0)
    status = Column(String(16), default="running")  # running|success|failed
    error_message = Column(Text, nullable=True)


class PushLog(Base):
    """Slack push audit log."""
    __tablename__ = "push_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    pushed_at = Column(DateTime(timezone=True), server_default=func.now())
    channel = Column(String(32), default="slack")  # slack|telegram
    action = Column(String(16), default="create")   # create|update|thread_append
    slack_ts = Column(String(64), nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
