"""Markets-mode tables. Additive only: nothing here alters an existing table.

Paper accounts and exchange credentials are Phase 2 and Phase 3.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.security import utcnow


def new_id() -> str:
    return str(uuid4())


class MarketInstrument(Base):
    __tablename__ = "market_instruments"
    __table_args__ = (
        UniqueConstraint("venue", "instrument_id", name="uq_market_instrument"),
        Index("ix_market_instruments_kind", "kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    instrument_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(256), default="")
    sport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    league: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_rules: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_market_snapshots_instrument_time", "venue", "instrument_id", "fetched_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    instrument_id: Mapped[str] = mapped_column(String(128))
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    last: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint(
            "venue",
            "instrument_id",
            "granularity",
            "ts",
            name="uq_market_candle",
        ),
        Index("ix_market_candles_lookup", "venue", "instrument_id", "granularity", "ts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    venue: Mapped[str] = mapped_column(String(32))
    instrument_id: Mapped[str] = mapped_column(String(128))
    granularity: Mapped[str] = mapped_column(String(32))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)


class MarketCall(Base):
    __tablename__ = "market_calls"
    __table_args__ = (
        Index("ix_market_calls_board", "venue_group", "created_at"),
        Index("ix_market_calls_verdict", "verdict"),
        Index("ix_market_calls_model", "model_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    venue: Mapped[str] = mapped_column(String(32), index=True)
    venue_group: Mapped[str] = mapped_column(String(32), index=True)
    instrument_id: Mapped[str] = mapped_column(String(128), index=True)
    call_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256), default="")
    selection: Mapped[str] = mapped_column(String(256), default="")
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    horizon_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    horizon_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(16))
    tier: Mapped[str] = mapped_column(String(32), default="")
    edge_class: Mapped[str] = mapped_column(String(20), default="")
    stake_pct: Mapped[float] = mapped_column(Float, default=0.0)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    price_gap: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class MarketOutcome(Base):
    __tablename__ = "market_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    call_id: Mapped[str] = mapped_column(
        ForeignKey("market_calls.id", ondelete="CASCADE"), unique=True, index=True
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    realized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier: Mapped[float | None] = mapped_column(Float, nullable=True)
    grading_method: Mapped[str] = mapped_column(String(32))
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class MarketJobRun(Base):
    __tablename__ = "market_job_runs"
    __table_args__ = (Index("ix_market_job_runs_name_started", "job_name", "started_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_name: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running")
    errors: Mapped[list] = mapped_column(JSON, default=list)


class MarketModelVersion(Base):
    __tablename__ = "market_model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
