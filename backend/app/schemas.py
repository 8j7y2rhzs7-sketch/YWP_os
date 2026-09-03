from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class YWPModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RiskProfile(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    aggressive = "aggressive"


class Decision(StrEnum):
    play = "PLAY"
    lean = "LEAN"
    watch = "WATCH"
    skip = "SKIP"


class LockStatus(StrEnum):
    locked = "LOCKED"
    warning = "WARNING"
    change_required = "CHANGE_REQUIRED"
    skip = "SKIP"


class RegisterRequest(YWPModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="America/New_York", min_length=3, max_length=64)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        groups = [
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        ]
        if sum(groups) < 3:
            raise ValueError("Password must use at least three character groups")
        return value


class LoginRequest(YWPModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(YWPModel):
    refresh_token: str


class LogoutRequest(YWPModel):
    refresh_token: str


class TokenResponse(YWPModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    access_expires_at: datetime
    refresh_expires_at: datetime


class UserOut(YWPModel):
    id: str
    email: EmailStr
    name: str
    timezone: str
    risk_profile: RiskProfile
    role: str
    is_active: bool
    subscription_status: str = "none"
    has_app_access: bool = True
    created_at: datetime


class SubscriptionOut(YWPModel):
    required: bool
    has_access: bool
    status: str
    whop_user_id: str | None = None
    checkout_url: str | None = None


class WhopCheckoutOut(YWPModel):
    checkout_url: str
    product_id: str | None = None
    message: str


class UserUpdate(YWPModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    risk_profile: RiskProfile | None = None


class BankrollOut(YWPModel):
    id: str
    balance: Decimal
    currency: str
    max_stake_pct: Decimal
    max_daily_exposure_pct: Decimal
    max_thesis_exposure_pct: Decimal
    loss_pause_threshold: int
    updated_at: datetime


class BankrollUpdate(YWPModel):
    max_stake_pct: Decimal | None = Field(default=None, ge=Decimal("0.001"), le=Decimal("0.10"))
    max_daily_exposure_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.01"), le=Decimal("0.50")
    )
    max_thesis_exposure_pct: Decimal | None = Field(
        default=None, ge=Decimal("0.001"), le=Decimal("0.10")
    )
    loss_pause_threshold: int | None = Field(default=None, ge=1, le=10)


class BankrollTransactionCreate(YWPModel):
    transaction_type: Literal["deposit", "withdrawal", "adjustment"]
    amount: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    note: str | None = Field(default=None, max_length=255)


class BankrollTransactionOut(YWPModel):
    id: str
    transaction_type: str
    amount: Decimal
    balance_after: Decimal
    reference_id: str | None
    note: str | None
    created_at: datetime


class CandidateInput(YWPModel):
    candidate_id: str = Field(min_length=3, max_length=100)
    event_id: str = Field(min_length=3, max_length=100)
    event_name: str = Field(min_length=3, max_length=180)
    sport: str = Field(min_length=2, max_length=24)
    league: str = Field(min_length=2, max_length=40)
    start_time: datetime
    market_type: str = Field(min_length=2, max_length=50)
    market_period: str = Field(default="full_game", max_length=32)
    selection: str = Field(min_length=2, max_length=180)
    line: Decimal | None = None
    american_odds: int = Field(ge=-10000, le=10000)
    estimated_probability: float = Field(gt=0.01, lt=0.99)
    variance: float = Field(ge=0, le=1)
    data_quality: float = Field(ge=0, le=1)
    factors: dict[str, float] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)

    data_source: str = Field(min_length=2, max_length=64)
    source_timestamp: datetime
    missing_fields: list[str] = Field(default_factory=list)
    source_status: dict[str, Literal["confirmed", "probable", "unknown"]] = Field(
        default_factory=dict
    )
    schedule_verified: bool = False
    universe_scan_complete: bool = False
    current_form_verified: bool = False
    l5_l10_verified: bool = False
    lineup_confirmed: bool = False
    injuries_verified: bool = False
    weather_verified: bool = False
    starter_confirmed: bool = False
    motivation_rotation_verified: bool = False
    home_away_verified: bool = False
    market_movement_verified: bool = False
    sport_specific_sweep_complete: bool = False

    market_is_pitcher_strikeout_over: bool = False
    first_start_back: bool = False
    normal_workload_confirmed: bool = False
    k_duration_verified: bool = True
    bullpen_game: bool = False
    bullpen_verified: bool = True
    previous_game_recency_only: bool = False

    recent_hit_rate: float | None = Field(default=None, ge=0, le=1)
    average_cushion: float | None = None
    cushion_scale: float = Field(default=3.0, gt=0, le=100)
    matchup_score: float = Field(default=0.5, ge=0, le=1)
    script_alignment: float = Field(default=0.5, ge=0, le=1)
    multiple_paths_score: float = Field(default=0.5, ge=0, le=1)
    role_stability: float = Field(default=0.5, ge=0, le=1)
    miss_by_one_count_l10: int = Field(default=0, ge=0, le=10)
    ticket_killer_count: int = Field(default=0, ge=0, le=100)
    ain_checks: dict[str, bool | None] = Field(default_factory=dict)

    base_line: Decimal | None = None
    alt_line_approved: bool = True
    low_alt_over: bool = False
    credible_scoring_paths: int = Field(default=2, ge=0, le=4)
    dominant_scoring_path_verified: bool = False
    heavily_juiced_filler: bool = False
    independent_value_verified: bool = True

    is_knockout: bool = False
    draw_probability: float | None = Field(default=None, ge=0, le=1)
    extra_time_available: bool = False
    to_qualify_market_available: bool = False

    thesis_key: str = Field(min_length=3, max_length=160)
    script_key: str = Field(min_length=3, max_length=160)
    player_key: str | None = Field(default=None, max_length=120)
    safer_alternative: str | None = Field(default=None, max_length=180)
    higher_upside: str | None = Field(default=None, max_length=180)
    invalidation_conditions: list[str] = Field(default_factory=list)
    live_trigger: str | None = Field(default=None, max_length=255)
    hedge: str | None = Field(default=None, max_length=255)
    quick_cash: bool = False
    chain_reaction_key: str | None = Field(default=None, max_length=160)

    @field_validator("american_odds")
    @classmethod
    def odds_cannot_be_zero(cls, value: int) -> int:
        if value == 0 or -100 < value < 100:
            raise ValueError("American odds must be <= -100 or >= +100")
        return value

    @field_validator("factors")
    @classmethod
    def factors_in_range(cls, value: dict[str, float]) -> dict[str, float]:
        if any(score < -1 or score > 1 for score in value.values()):
            raise ValueError("Factor values must be between -1 and 1")
        return value

    @model_validator(mode="after")
    def line_escalation_is_explicit(self) -> CandidateInput:
        if self.base_line is not None and self.line is None:
            raise ValueError("line is required when base_line is supplied")
        return self


class SportsAnalyzeRequest(YWPModel):
    sport: str = Field(min_length=2, max_length=24)
    date: date
    mode: Literal["pregame", "live"] = "pregame"
    user_risk_profile: RiskProfile = RiskProfile.balanced
    bankroll: Decimal | None = Field(default=None, ge=0)
    candidates: list[CandidateInput] = Field(min_length=1, max_length=250)

    @model_validator(mode="after")
    def candidates_match_sport(self) -> SportsAnalyzeRequest:
        expected = self.sport.lower()
        if any(candidate.sport.lower() != expected for candidate in self.candidates):
            raise ValueError("Every candidate must match the requested sport")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique within an analysis")
        return self


class RecommendationOut(YWPModel):
    id: str
    analysis_id: str
    candidate_id: str
    event_id: str
    event_name: str
    sport: str
    league: str
    slate_date: date
    market_type: str
    market_period: str
    selection: str
    line: Decimal | None
    american_odds: int
    estimated_probability: Decimal
    implied_probability: Decimal
    adjusted_probability: Decimal
    edge: Decimal
    expected_value: Decimal
    confidence_score: int
    ywp_rating: Decimal
    vision_score: Decimal
    miss_by_one_risk: Decimal
    reliability: Decimal
    stability: Decimal
    variance: Decimal
    data_quality: Decimal
    risk: str
    risk_tier: str
    variance_rating: str
    edge_class: str
    expected_value_label: str
    suggested_stake_pct: Decimal
    decision: str
    recommendation_tier: str
    rank: int
    reason_codes: list[str]
    reasoning_summary: str
    warnings: list[str]
    safer_alternative: str | None
    higher_upside: str | None
    invalidation_conditions: list[str]
    live_trigger: str | None
    hedge: str | None
    quick_cash: bool
    chain_reaction_key: str | None
    thesis_key: str
    script_key: str
    player_key: str | None
    data_source: str
    source_timestamp: datetime
    model_version: str
    protocol_version: str
    input_hash: str
    outcome: str | None
    created_at: datetime


class AnalyzeResponse(YWPModel):
    engine: Literal["YWP Sports Engine"] = "YWP Sports Engine"
    model_version: str
    analysis_id: str
    status: Literal["success"] = "success"
    date: date
    ranked_picks: list[RecommendationOut]
    stay_away: list[RecommendationOut]
    data_quality_summary: dict[str, Any]


class SlateResponse(YWPModel):
    sport: str
    date: date
    mode: Literal["demo", "live"]
    notice: str
    candidates: list[CandidateInput]


class BuildTicketRequest(YWPModel):
    analysis_id: str | None = None
    recommendation_ids: list[str] = Field(default_factory=list, max_length=100)
    max_legs: int = Field(default=5, ge=1, le=12)
    min_rating: float = Field(default=7.5, ge=0, le=10)
    risk_profile: RiskProfile = RiskProfile.balanced
    exclude_correlated_unless_intentional: bool = True

    @model_validator(mode="after")
    def has_source(self) -> BuildTicketRequest:
        if not self.analysis_id and not self.recommendation_ids:
            raise ValueError("analysis_id or recommendation_ids is required")
        return self


class TicketCardOut(YWPModel):
    key: str
    label: str
    recommendation_ids: list[str]
    legs: list[RecommendationOut]
    risk: str
    confidence_score: int
    weakest_leg_id: str | None
    warnings: list[str]


class BuildTicketResponse(YWPModel):
    analysis_id: str | None
    cards: dict[str, TicketCardOut]
    stay_away: list[RecommendationOut]
    quarantined: list[dict[str, str]]


class TicketCreate(YWPModel):
    ticket_type: str = Field(min_length=2, max_length=32)
    label: str = Field(min_length=2, max_length=120)
    recommendation_ids: list[str] = Field(min_length=1, max_length=12)
    stake: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    intentional_correlation: bool = False
    intentional_thesis_exposure: bool = False
    override_acknowledged: bool = False


class TicketLegOut(YWPModel):
    id: str
    recommendation_id: str
    position: int
    selection: str
    american_odds: int
    thesis_key: str
    script_key: str
    action: str
    skip_reason: str | None
    status: str
    outcome: str | None


class TicketOut(YWPModel):
    id: str
    ticket_type: str
    label: str
    sport: str
    slate_date: date
    status: str
    stake: Decimal
    potential_payout: Decimal
    combined_decimal_odds: Decimal
    risk: str
    confidence_score: int
    intentional_correlation: bool
    intentional_thesis_exposure: bool
    override_acknowledged: bool
    last_lock_status: str | None
    last_lock_expires_at: datetime | None
    legs: list[TicketLegOut]
    created_at: datetime
    updated_at: datetime


class TicketLegAction(YWPModel):
    action: Literal["follow", "skip", "replace"]
    skip_reason: str | None = Field(default=None, max_length=255)
    replacement_recommendation_id: str | None = None

    @model_validator(mode="after")
    def validate_action(self) -> TicketLegAction:
        if self.action == "skip" and not self.skip_reason:
            raise ValueError("skip_reason is required when skipping a leg")
        if self.action == "replace" and not self.replacement_recommendation_id:
            raise ValueError("replacement_recommendation_id is required")
        return self


class CurrentStateUpdate(YWPModel):
    recommendation_id: str
    source_timestamp: datetime
    current_odds: int | None = Field(default=None, ge=-10000, le=10000)
    market_available: bool = True
    starter_changed: bool = False
    lineup_changed: bool = False
    key_injury_change: bool = False
    severe_weather_change: bool = False
    data_quality: float | None = Field(default=None, ge=0, le=1)
    first_start_back: bool | None = None
    normal_workload_confirmed: bool | None = None
    k_duration_verified: bool | None = None
    bullpen_verified: bool | None = None
    notes: list[str] = Field(default_factory=list)


class LockCheckRequest(YWPModel):
    updates: list[CurrentStateUpdate] = Field(default_factory=list)
    acknowledge_correlation: bool = False
    intentional_thesis_exposure: bool = False


class LockCheckOut(YWPModel):
    id: str
    ticket_id: str
    lock_status: str
    ticket_confidence_score: int
    recommended_action: str
    overall_message: str
    checks: dict[str, Any]
    warnings: list[str]
    leg_results: list[dict[str, Any]]
    expires_at: datetime
    created_at: datetime


class ResultCreate(YWPModel):
    recommendation_id: str
    outcome: Literal["WIN", "LOSS", "PUSH", "VOID"]
    final_score: str | None = Field(default=None, max_length=120)
    stake: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    profit_loss: Decimal = Field(default=Decimal("0.00"), max_digits=14, decimal_places=2)
    closing_odds: int | None = Field(default=None, ge=-10000, le=10000)
    closing_line: Decimal | None = None
    actual_value: Decimal | None = None
    bet_line: Decimal | None = None
    killed_ticket: bool = False
    last_losing_leg: bool = False
    process_outcome_class: Literal[
        "GOOD_PROCESS_GOOD_OUTCOME",
        "GOOD_PROCESS_BAD_OUTCOME",
        "BAD_PROCESS_GOOD_OUTCOME",
        "BAD_PROCESS_BAD_OUTCOME",
        "UNCLASSIFIED",
    ] = "UNCLASSIFIED"
    error_category: (
        Literal[
            "BAD_DATA",
            "BAD_WEIGHTING",
            "BAD_SCRIPT",
            "BAD_TIMING",
            "BAD_PRICE",
            "ROLE_WORKLOAD",
            "INJURY_AVAILABILITY",
            "CORRELATION_EXPOSURE",
            "LINE_ESCALATION",
            "VARIANCE",
            "UNKNOWN",
        ]
        | None
    ) = None
    assumptions_review: list[str] = Field(default_factory=list)
    unexpected_events: list[str] = Field(default_factory=list)
    quick_cash_result: Literal["HIT", "MISS", "NOT_APPLICABLE"] | None = None
    chain_reaction_result: Literal["HIT", "MISS", "NOT_TRIGGERED", "NOT_APPLICABLE"] | None = None
    live_trigger_result: Literal["HIT", "MISS", "NOT_TRIGGERED", "NOT_APPLICABLE"] | None = None
    cashout_action: (
        Literal["HOLD", "CASH_OUT", "PARTIAL_HEDGE", "NOT_OFFERED", "NOT_APPLICABLE"] | None
    ) = None
    cashout_offer: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    cashout_reason: str | None = Field(default=None, max_length=2000)
    cashout_time: datetime | None = None
    process_grade: Literal["A", "B", "C", "D", "F"]
    variance_grade: Literal["LOW", "MEDIUM", "HIGH"]
    root_cause_tags: list[str] = Field(default_factory=list)
    lesson: str | None = Field(default=None, max_length=2000)
    result_time: datetime | None = None

    @model_validator(mode="after")
    def validate_cashout_audit(self) -> ResultCreate:
        acted = {"HOLD", "CASH_OUT", "PARTIAL_HEDGE"}
        if self.cashout_action in acted and self.cashout_offer is None:
            raise ValueError("cashout_offer is required for a live cash-out action")
        if self.cashout_action in acted and not self.cashout_reason:
            raise ValueError("cashout_reason is required for a live cash-out action")
        if self.cashout_offer is not None and self.cashout_action is None:
            raise ValueError("cashout_action is required when cashout_offer is supplied")
        return self


class ResultOut(YWPModel):
    id: str
    recommendation_id: str
    outcome: str
    final_score: str | None
    stake: Decimal
    profit_loss: Decimal
    closing_odds: int | None
    closing_line: Decimal | None
    clv_probability: Decimal | None
    line_value: Decimal | None
    actual_value: Decimal | None
    bet_line: Decimal | None
    miss_distance: Decimal | None
    killed_ticket: bool
    last_losing_leg: bool
    process_outcome_class: str
    error_category: str | None
    assumptions_review: list[str]
    unexpected_events: list[str]
    quick_cash_result: str | None
    chain_reaction_result: str | None
    live_trigger_result: str | None
    cashout_action: str | None
    cashout_offer: Decimal | None
    cashout_reason: str | None
    cashout_time: datetime | None
    process_grade: str
    variance_grade: str
    root_cause_tags: list[str]
    lesson: str | None
    result_time: datetime


class PerformanceOut(YWPModel):
    settled: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    profit_loss: Decimal
    roi: float | None
    by_sport: list[dict[str, Any]]
    by_market: list[dict[str, Any]]
    confidence_calibration: list[dict[str, Any]]


class PatternOut(YWPModel):
    root_cause_tags: list[dict[str, Any]]
    duplicate_thesis_losses: list[dict[str, Any]]
    recent_learning_events: list[dict[str, Any]]


class MissByOneOut(YWPModel):
    near_miss_results: int
    tickets_killed_by_near_miss: int
    last_leg_near_misses: int
    by_sport: list[dict[str, Any]]
    by_market: list[dict[str, Any]]
    by_player: list[dict[str, Any]]
    by_line: list[dict[str, Any]]
    by_role: list[dict[str, Any]]
    by_script: list[dict[str, Any]]
    by_card_type: list[dict[str, Any]]
    recurring_theses: list[dict[str, Any]]


class ErrorAnalysisRequest(YWPModel):
    recommendation_id: str
    assumptions_that_held: list[str] = Field(default_factory=list)
    assumptions_that_failed: list[str] = Field(default_factory=list)
    unexpected_events: list[str] = Field(default_factory=list)
    root_cause_tags: list[str] = Field(default_factory=list)
    error_category: Literal[
        "BAD_DATA",
        "BAD_WEIGHTING",
        "BAD_SCRIPT",
        "BAD_TIMING",
        "BAD_PRICE",
        "ROLE_WORKLOAD",
        "INJURY_AVAILABILITY",
        "CORRELATION_EXPOSURE",
        "LINE_ESCALATION",
        "VARIANCE",
        "UNKNOWN",
    ]
    lesson: str = Field(min_length=3, max_length=2000)


class WeightProposalOut(YWPModel):
    id: str
    sport: str
    market_type: str
    feature_name: str
    current_weight: Decimal
    proposed_weight: Decimal
    sample_size: int
    repeated_pattern_count: int
    evidence: dict[str, Any]
    reason: str
    status: str
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    created_at: datetime


class WeightProposalReview(YWPModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)


class ProtocolRunOut(YWPModel):
    id: str
    analysis_id: str
    protocol_version: str
    sport: str
    run_type: str
    status: str
    checks: list[dict[str, Any]]
    warnings: list[str]
    superseded_rules_ignored: list[str]
    created_at: datetime


class MessageOut(YWPModel):
    message: str
