from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HiveLearningEvent(Base):
    __tablename__ = "hive_learning_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idempotency_key = Column(String(64), nullable=False, unique=True, index=True)

    # Pseudonymous stable contributor token. Never store raw user id here.
    contributor_key = Column(String(64), nullable=False, index=True)

    # Link to internal recommendation by opaque id only.
    source_recommendation_id = Column(String(128), nullable=False, index=True)

    sport = Column(String(32), nullable=False, index=True)
    league = Column(String(64), nullable=True, index=True)
    event_id = Column(String(128), nullable=False, index=True)
    event_start_at = Column(DateTime(timezone=True), nullable=True)

    market = Column(String(64), nullable=False, index=True)
    market_scope = Column(String(96), nullable=False, index=True)
    selection = Column(String(256), nullable=False)
    line = Column(Float, nullable=True)
    odds_american = Column(Integer, nullable=True)

    # Must be prediction captured BEFORE outcome.
    model_probability = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    model_version = Column(String(64), nullable=False, index=True)
    protocol_version = Column(String(64), nullable=True)
    evidence_version = Column(String(128), nullable=True)
    data_quality = Column(Float, nullable=True)

    # Small machine-readable aggregate-safe flags only.
    feature_flags = Column(JSON, nullable=False, default=dict)

    action = Column(String(16), nullable=True)
    outcome = Column(String(8), nullable=True, index=True)
    outcome_verified = Column(Boolean, nullable=False, default=False)
    result_source = Column(String(64), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    consent_to_hive = Column(Boolean, nullable=False, default=False)
    training_eligible = Column(Boolean, nullable=False, default=False, index=True)
    training_ineligibility_reason = Column(String(96), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index(
            "ix_hive_event_bucket",
            "sport",
            "league",
            "market",
            "market_scope",
            "model_version",
            "training_eligible",
        ),
    )


class HiveAggregate(Base):
    __tablename__ = "hive_aggregates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    bucket_key = Column(String(64), nullable=False, unique=True, index=True)

    sport = Column(String(32), nullable=False, index=True)
    league = Column(String(64), nullable=True, index=True)
    market = Column(String(64), nullable=False, index=True)
    market_scope = Column(String(96), nullable=False, index=True)
    model_version = Column(String(64), nullable=False, index=True)

    eligible_samples = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    pushes = Column(Integer, nullable=False, default=0)
    voids = Column(Integer, nullable=False, default=0)

    sum_predicted_probability = Column(Float, nullable=False, default=0.0)
    predicted_probability_count = Column(Integer, nullable=False, default=0)

    raw_rate = Column(Float, nullable=True)
    posterior_rate = Column(Float, nullable=True)
    mean_predicted_probability = Column(Float, nullable=True)
    calibration_delta = Column(Float, nullable=True)

    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class HiveModelSnapshot(Base):
    __tablename__ = "hive_model_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    release_version = Column(String(64), nullable=False, index=True)
    snapshot_type = Column(String(32), nullable=False, default="aggregate_release")
    parameters = Column(JSON, nullable=False, default=dict)
    sample_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("release_version", "snapshot_type", name="uq_hive_snapshot_release_type"),
    )
