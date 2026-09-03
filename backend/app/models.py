from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.security import utcnow


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    risk_profile: Mapped[str] = mapped_column(String(24), default="balanced")
    role: Mapped[str] = mapped_column(String(24), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    whop_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    whop_membership_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(24), default="none")

    bankroll: Mapped[BankrollAccount | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    refresh_sessions: Mapped[list[RefreshSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[Ticket]] = relationship(back_populates="user")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="refresh_sessions")


class BankrollAccount(Base, TimestampMixin):
    __tablename__ = "bankroll_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    max_stake_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0200"))
    max_daily_exposure_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.1000")
    )
    max_thesis_exposure_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), default=Decimal("0.0300")
    )
    loss_pause_threshold: Mapped[int] = mapped_column(default=3)

    user: Mapped[User] = relationship(back_populates="bankroll")
    transactions: Mapped[list[BankrollTransaction]] = relationship(
        back_populates="bankroll", cascade="all, delete-orphan"
    )


class BankrollTransaction(Base):
    __tablename__ = "bankroll_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    bankroll_id: Mapped[str] = mapped_column(
        ForeignKey("bankroll_accounts.id", ondelete="CASCADE"), index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    bankroll: Mapped[BankrollAccount] = relationship(back_populates="transactions")


class GameSnapshot(Base):
    __tablename__ = "game_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(String(36), index=True)
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    sport: Mapped[str] = mapped_column(String(24), index=True)
    slate_date: Mapped[date] = mapped_column(Date, index=True)
    data_source: Mapped[str] = mapped_column(String(64))
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_slate", "sport", "slate_date", "decision"),
        Index("ix_recommendations_analysis", "analysis_id", "rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(String(36), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(100), index=True)
    event_name: Mapped[str] = mapped_column(String(180))
    sport: Mapped[str] = mapped_column(String(24), index=True)
    league: Mapped[str] = mapped_column(String(40))
    slate_date: Mapped[date] = mapped_column(Date, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="pregame")
    market_type: Mapped[str] = mapped_column(String(50), index=True)
    market_period: Mapped[str] = mapped_column(String(32), default="full_game")
    selection: Mapped[str] = mapped_column(String(180))
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    american_odds: Mapped[int] = mapped_column()
    estimated_probability: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    implied_probability: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    adjusted_probability: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    edge: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    expected_value: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    confidence_score: Mapped[int] = mapped_column()
    ywp_rating: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    vision_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0.00"))
    miss_by_one_risk: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    reliability: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    stability: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.0000"))
    variance: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    data_quality: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    risk: Mapped[str] = mapped_column(String(20))
    risk_tier: Mapped[str] = mapped_column(String(20), default="Moderate")
    variance_rating: Mapped[str] = mapped_column(String(20), default="Medium")
    edge_class: Mapped[str] = mapped_column(String(20), default="No Edge")
    expected_value_label: Mapped[str] = mapped_column(String(16), default="Neutral")
    suggested_stake_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.0000"))
    decision: Mapped[str] = mapped_column(String(20), index=True)
    recommendation_tier: Mapped[str] = mapped_column(String(32), index=True)
    rank: Mapped[int] = mapped_column(default=0)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    reasoning_summary: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    safer_alternative: Mapped[str | None] = mapped_column(String(180), nullable=True)
    higher_upside: Mapped[str | None] = mapped_column(String(180), nullable=True)
    invalidation_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    live_trigger: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hedge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quick_cash: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    chain_reaction_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    thesis_key: Mapped[str] = mapped_column(String(160), index=True)
    script_key: Mapped[str] = mapped_column(String(160), index=True)
    player_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    data_source: Mapped[str] = mapped_column(String(64))
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_version: Mapped[str] = mapped_column(String(64))
    protocol_version: Mapped[str] = mapped_column(String(32), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket_legs: Mapped[list[TicketLeg]] = relationship(back_populates="recommendation")
    result: Mapped[Result | None] = relationship(
        back_populates="recommendation", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def image_url(self) -> str | None:
        snap = self.snapshot or {}
        return snap.get("image_url") or snap.get("player_image_url")

    @property
    def team_image_url(self) -> str | None:
        return (self.snapshot or {}).get("team_image_url")

    @property
    def source_urls(self) -> list[str]:
        value = self.snapshot.get("source_urls", []) if self.snapshot else []
        return [str(item) for item in value if item]


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticket_type: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(120))
    sport: Mapped[str] = mapped_column(String(24), default="multi")
    slate_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    stake: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    potential_payout: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    combined_decimal_odds: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("1.0000")
    )
    risk: Mapped[str] = mapped_column(String(20))
    confidence_score: Mapped[int] = mapped_column()
    intentional_correlation: Mapped[bool] = mapped_column(Boolean, default=False)
    intentional_thesis_exposure: Mapped[bool] = mapped_column(Boolean, default=False)
    override_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    last_lock_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_lock_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="tickets")
    legs: Mapped[list[TicketLeg]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketLeg.position"
    )
    lock_checks: Mapped[list[LockCheck]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketLeg(Base):
    __tablename__ = "ticket_legs"
    __table_args__ = (UniqueConstraint("ticket_id", "position", name="uq_ticket_leg_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column()
    selection: Mapped[str] = mapped_column(String(180))
    american_odds: Mapped[int] = mapped_column()
    thesis_key: Mapped[str] = mapped_column(String(160), index=True)
    script_key: Mapped[str] = mapped_column(String(160), index=True)
    action: Mapped[str] = mapped_column(String(16), default="follow")
    skip_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    replacement_for_leg_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")

    ticket: Mapped[Ticket] = relationship(back_populates="legs")
    recommendation: Mapped[Recommendation] = relationship(back_populates="ticket_legs")

    @property
    def outcome(self) -> str | None:
        return self.recommendation.outcome if self.recommendation else None

    @property
    def image_url(self) -> str | None:
        return self.recommendation.image_url if self.recommendation else None

    @property
    def team_image_url(self) -> str | None:
        return self.recommendation.team_image_url if self.recommendation else None


class LockCheck(Base):
    __tablename__ = "lock_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lock_status: Mapped[str] = mapped_column(String(24), index=True)
    ticket_confidence_score: Mapped[int] = mapped_column()
    recommended_action: Mapped[str] = mapped_column(String(40))
    overall_message: Mapped[str] = mapped_column(Text)
    checks: Mapped[dict[str, Any]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    leg_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="lock_checks")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recommendation_id: Mapped[str] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), unique=True, index=True
    )
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    final_score: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stake: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    profit_loss: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    closing_odds: Mapped[int | None] = mapped_column(nullable=True)
    closing_line: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    clv_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    line_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    bet_line: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    miss_distance: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    killed_ticket: Mapped[bool] = mapped_column(Boolean, default=False)
    last_losing_leg: Mapped[bool] = mapped_column(Boolean, default=False)
    process_outcome_class: Mapped[str] = mapped_column(String(40), default="UNCLASSIFIED")
    error_category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    assumptions_review: Mapped[list[str]] = mapped_column(JSON, default=list)
    unexpected_events: Mapped[list[str]] = mapped_column(JSON, default=list)
    quick_cash_result: Mapped[str | None] = mapped_column(String(24), nullable=True)
    chain_reaction_result: Mapped[str | None] = mapped_column(String(24), nullable=True)
    live_trigger_result: Mapped[str | None] = mapped_column(String(24), nullable=True)
    cashout_action: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    cashout_offer: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cashout_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cashout_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    process_grade: Mapped[str] = mapped_column(String(8))
    variance_grade: Mapped[str] = mapped_column(String(8))
    root_cause_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    lesson: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recommendation: Mapped[Recommendation] = relationship(back_populates="result")


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    sport: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    market_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelWeight(Base, TimestampMixin):
    __tablename__ = "model_weights"
    __table_args__ = (
        UniqueConstraint(
            "sport", "market_type", "feature_name", "version", name="uq_model_weight_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sport: Mapped[str] = mapped_column(String(24), index=True)
    market_type: Mapped[str] = mapped_column(String(50), index=True)
    feature_name: Mapped[str] = mapped_column(String(80), index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    version: Mapped[int] = mapped_column(default=1)
    sample_size: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    source_proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class WeightChangeProposal(Base):
    __tablename__ = "weight_change_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sport: Mapped[str] = mapped_column(String(24), index=True)
    market_type: Mapped[str] = mapped_column(String(50), index=True)
    feature_name: Mapped[str] = mapped_column(String(80), index=True)
    current_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    proposed_weight: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    sample_size: Mapped[int] = mapped_column()
    repeated_pattern_count: Mapped[int] = mapped_column()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_by: Mapped[str] = mapped_column(String(36), default="system")
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_weight_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rollback_of_proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProtocolRun(Base):
    __tablename__ = "protocol_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    protocol_version: Mapped[str] = mapped_column(String(32), index=True)
    sport: Mapped[str] = mapped_column(String(24), index=True)
    run_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    superseded_rules_ignored: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PendingWhopAccess(Base, TimestampMixin):
    """Access granted via Whop before the user registers in YWP OS."""

    __tablename__ = "pending_whop_access"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), index=True)
    whop_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    whop_membership_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active")


class WhopWebhookDelivery(Base):
    __tablename__ = "whop_webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    webhook_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
