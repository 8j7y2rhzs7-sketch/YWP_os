from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import uuid4

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.security import utcnow
from app.deps import DB, SubscribedUser
from app.models import (
    GameSnapshot,
    LearningEvent,
    Recommendation,
    Result,
    Ticket,
    TicketLeg,
)
from app.schemas import (
    AnalyzeResponse,
    BuildTicketRequest,
    BuildTicketResponse,
    RecommendationOut,
    ResultCreate,
    ResultOut,
    SlateResponse,
    SportsAnalyzeRequest,
)
from app.services.decision_engine import decision_engine, implied_probability, money
from app.services.learning import apply_micro_learning, load_feature_weights, record_usage_event
from app.services.protocols import run_protocol_health_check
from app.services.providers import demo_slate
from app.services.live_generic_slate import SPORT_KEYS, live_generic_slate
from app.services.live_mlb_slate import live_mlb_slate
from app.services.live_wnba_slate import live_wnba_slate
from app.services.odds_provider import get_last_fetch_status, odds_api_configured
from app.services.readiness import slate_readiness, verification_summary
from app.services.ticket_builder import build_cards

router = APIRouter(prefix="/sports", tags=["sports"])


def _slate_response(
    *,
    sport: str,
    slate_date: date,
    mode: str,
    notice: str,
    candidates: list,
) -> SlateResponse:
    return SlateResponse(
        sport=sport,
        date=slate_date,
        mode=mode,
        readiness=slate_readiness(candidates),
        notice=notice,
        verification_summary=verification_summary(candidates),
        candidates=candidates,
    )


def _owned_recommendation(db: DB, recommendation_id: str, user_id: str) -> Recommendation:
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.created_by_user_id == user_id,
        )
    )
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.get("/slate", response_model=SlateResponse)
def slate(
    _: SubscribedUser,
    sport_name: str = Query(alias="sport", min_length=2, max_length=24),
    slate_date: date = Query(alias="date"),
) -> SlateResponse:
    sport_lower = sport_name.lower()

    if not settings.demo_mode and sport_lower == "mlb":
        try:
            candidates = live_mlb_slate(slate_date)
            if candidates:
                has_book_markets = any(
                    item.market_type
                    in {"moneyline", "run_line", "game_total_over", "game_total_under"}
                    for item in candidates
                )
                odds_status = get_last_fetch_status()
                if has_book_markets:
                    notice = (
                        "Live MLB: independent YWP model from official MLB Stats API facts, "
                        "filled by the trusted-source research searchers, compared against "
                        "real sportsbook prices from The Odds API."
                    )
                elif not odds_api_configured():
                    notice = (
                        "Live MLB schedule and model inputs loaded, but ODDS_API_KEY is missing. "
                        "No actionable candidates without a real sportsbook price. "
                        "Set ODDS_API_KEY on Render, redeploy, then refresh."
                    )
                else:
                    detail = odds_status.get("error") or "book_odds_unavailable"
                    fingerprint = odds_status.get("fingerprint") or "unknown"
                    key_len = odds_status.get("length") or 0
                    hex_note = (
                        "key looks like hex"
                        if odds_status.get("looks_like_hex")
                        else "key is not hex — Odds API keys are 0-9 and a-f only"
                    )
                    notice = (
                        "Live MLB model inputs loaded, but book odds were unavailable "
                        f"({detail}). Server key fingerprint {fingerprint} "
                        f"({key_len} chars, {hex_note}). "
                        "After changing ODDS_API_KEY on Render, use Manual Deploy, "
                        "wait for version 3.2.1+, then refresh."
                    )
                return _slate_response(
                    sport=sport_lower,
                    slate_date=slate_date,
                    mode="live",
                    notice=notice,
                    candidates=candidates,
                )
        except Exception:
            logger.exception("Live MLB slate failed")

    if not settings.demo_mode and sport_lower in ("wnba", "basketball") and settings.odds_api_key:
        try:
            candidates = live_wnba_slate(slate_date)
            if candidates:
                return _slate_response(
                    sport=sport_lower,
                    slate_date=slate_date,
                    mode="live",
                    notice=(
                        "Live WNBA data from The Odds API. "
                        "Player props and L5/L10 stats require manual verification."
                    ),
                    candidates=candidates,
                )
        except Exception:
            logger.exception("Live WNBA slate failed")

    if not settings.demo_mode and sport_lower in SPORT_KEYS and settings.odds_api_key:
        try:
            candidates = live_generic_slate(sport_lower, slate_date)
            if candidates:
                return _slate_response(
                    sport=sport_lower,
                    slate_date=slate_date,
                    mode="live",
                    notice=(
                        f"Live {sport_lower.upper()} data from The Odds API. "
                        "Verify all inputs before wagering."
                    ),
                    candidates=candidates,
                )
        except Exception:
            logger.exception("Live %s slate failed", sport_lower)

    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No verified live slate is available. The server will not silently substitute "
                "demo data in production. Check provider configuration or submit verified "
                "candidate data through POST /sports/analyze."
            ),
        )

    candidates = demo_slate(sport_name, slate_date)
    return _slate_response(
        sport=sport_lower,
        slate_date=slate_date,
        mode="demo",
        notice=(
            "Synthetic demonstration data only. It is intentionally not a live slate and must "
            "not be used for wagering."
        ),
        candidates=candidates,
    )


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_201_CREATED)
def analyze(payload: SportsAnalyzeRequest, user: SubscribedUser, db: DB) -> AnalyzeResponse:
    analysis_id = str(uuid4())
    protocol_run = run_protocol_health_check(
        db,
        analysis_id=analysis_id,
        user_id=user.id,
        sport=payload.sport,
        candidates=payload.candidates,
    )
    weight_cache: dict[tuple[str, str], dict[str, float]] = {}
    evaluations = decision_engine.rank(
        [
            decision_engine.evaluate(
                candidate,
                payload.user_risk_profile,
                learned_weights=weight_cache.setdefault(
                    (candidate.sport.lower(), candidate.market_type),
                    load_feature_weights(db, candidate.sport.lower(), candidate.market_type),
                ),
            )
            for candidate in payload.candidates
        ]
    )
    record_usage_event(
        db,
        event_type="PROTOCOL_RUN",
        sport=payload.sport.lower(),
        analysis={
            "analysis_id": analysis_id,
            "user_id": user.id,
            "candidate_count": len(payload.candidates),
            "official_pass": not any(
                item.decision in {"PLAY", "LEAN"} for item in evaluations
            ),
        },
    )

    records: list[Recommendation] = []
    for rank, evaluation in enumerate(evaluations, start=1):
        candidate = evaluation.candidate
        db.add(
            GameSnapshot(
                analysis_id=analysis_id,
                event_id=candidate.event_id,
                sport=candidate.sport.lower(),
                slate_date=payload.date,
                data_source=candidate.data_source,
                source_timestamp=candidate.source_timestamp,
                input_hash=evaluation.input_hash,
                payload=evaluation.payload,
            )
        )
        record = Recommendation(
            analysis_id=analysis_id,
            created_by_user_id=user.id,
            candidate_id=candidate.candidate_id,
            event_id=candidate.event_id,
            event_name=candidate.event_name,
            sport=candidate.sport.lower(),
            league=candidate.league,
            slate_date=payload.date,
            mode=payload.mode,
            market_type=candidate.market_type,
            market_period=candidate.market_period,
            selection=candidate.selection,
            line=candidate.line,
            american_odds=candidate.american_odds,
            estimated_probability=money(candidate.estimated_probability),
            implied_probability=money(evaluation.implied_probability),
            adjusted_probability=money(evaluation.adjusted_probability),
            edge=money(evaluation.edge),
            expected_value=money(evaluation.expected_value),
            confidence_score=evaluation.confidence_score,
            ywp_rating=money(evaluation.ywp_intelligence_score, "0.01"),
            vision_score=money(evaluation.vision_score, "0.01"),
            miss_by_one_risk=money(evaluation.miss_by_one_risk, "0.0001"),
            reliability=money(evaluation.reliability, "0.0001"),
            stability=money(evaluation.stability, "0.0001"),
            variance=money(candidate.variance, "0.0001"),
            data_quality=money(candidate.data_quality, "0.0001"),
            risk=evaluation.risk,
            risk_tier=evaluation.risk_tier,
            variance_rating=evaluation.variance_rating,
            edge_class=evaluation.edge_class,
            expected_value_label=evaluation.expected_value_label,
            suggested_stake_pct=money(evaluation.suggested_stake_pct, "0.0001"),
            decision=evaluation.decision,
            recommendation_tier=evaluation.recommendation_tier,
            rank=rank,
            reason_codes=evaluation.reason_codes,
            reasoning_summary=evaluation.reasoning_summary,
            warnings=evaluation.warnings,
            safer_alternative=candidate.safer_alternative,
            higher_upside=candidate.higher_upside,
            invalidation_conditions=candidate.invalidation_conditions,
            live_trigger=candidate.live_trigger,
            hedge=candidate.hedge,
            quick_cash=candidate.quick_cash,
            chain_reaction_key=candidate.chain_reaction_key,
            thesis_key=candidate.thesis_key,
            script_key=candidate.script_key,
            player_key=candidate.player_key,
            data_source=candidate.data_source,
            source_timestamp=candidate.source_timestamp,
            model_version=settings.model_version,
            protocol_version=settings.protocol_version,
            input_hash=evaluation.input_hash,
            snapshot=evaluation.payload,
        )
        db.add(record)
        records.append(record)

    db.commit()
    for record in records:
        db.refresh(record)

    ranked = [
        RecommendationOut.model_validate(record)
        for record in records
        if record.decision in {"PLAY", "LEAN", "WATCH"}
    ]
    stay_away = [
        RecommendationOut.model_validate(record)
        for record in records
        if record.decision in {"SKIP", "REVIEW"}
    ]
    qualities = [candidate.data_quality for candidate in payload.candidates]
    unknowns = sum(
        value == "unknown"
        for candidate in payload.candidates
        for value in candidate.source_status.values()
    )
    readiness = slate_readiness(payload.candidates)
    return AnalyzeResponse(
        model_version=settings.model_version,
        analysis_id=analysis_id,
        date=payload.date,
        ranked_picks=ranked,
        stay_away=stay_away,
        readiness=readiness,
        data_quality_summary={
            "protocol_status": protocol_run.status,
            "protocol_run_id": protocol_run.id,
            "average_data_quality": round(sum(qualities) / len(qualities), 4),
            "missing_field_count": sum(
                len(candidate.missing_fields) for candidate in payload.candidates
            ),
            "unknown_source_labels": unknowns,
            "candidate_count": len(payload.candidates),
            "official_pass_count": len(ranked),
            "official_skip_count": len(stay_away),
            "official_pass": len(ranked) == 0,
            "verified_candidate_count": sum(
                1 for candidate in payload.candidates if slate_readiness([candidate]) == "VERIFIED"
            ),
            "readiness": readiness,
        },
    )


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationOut)
def recommendation(recommendation_id: str, user: SubscribedUser, db: DB) -> RecommendationOut:
    return RecommendationOut.model_validate(_owned_recommendation(db, recommendation_id, user.id))


@router.post("/build-ticket", response_model=BuildTicketResponse)
def build_ticket(payload: BuildTicketRequest, user: SubscribedUser, db: DB) -> BuildTicketResponse:
    conditions = [Recommendation.created_by_user_id == user.id]
    source_conditions = []
    if payload.analysis_id:
        source_conditions.append(Recommendation.analysis_id == payload.analysis_id)
    if payload.recommendation_ids:
        source_conditions.append(Recommendation.id.in_(payload.recommendation_ids))
    recommendations = list(
        db.scalars(
            select(Recommendation)
            .where(*conditions, or_(*source_conditions))
            .order_by(Recommendation.rank)
        ).all()
    )
    if not recommendations:
        raise HTTPException(status_code=404, detail="No recommendations found")

    exposed_theses = set(
        db.scalars(
            select(TicketLeg.thesis_key)
            .join(Ticket, Ticket.id == TicketLeg.ticket_id)
            .where(
                Ticket.user_id == user.id,
                Ticket.status.in_(["draft", "locked", "placed"]),
                TicketLeg.action.in_(["follow", "replace"]),
            )
        ).all()
    )
    cards, quarantined = build_cards(
        recommendations,
        max_legs=payload.max_legs,
        min_rating=payload.min_rating,
        exposed_thesis_keys=exposed_theses,
    )
    # Official PASS means no PLAY/LEAN survived analysis — not "card templates underfilled".
    # Eligible picks must remain custom-buildable even when diversity/min-leg gates omit cards.
    has_play_lean = any(item.decision in {"PLAY", "LEAN"} for item in recommendations)
    official_pass = not has_play_lean
    return BuildTicketResponse(
        analysis_id=payload.analysis_id,
        official_pass=official_pass,
        cards={} if official_pass else cards,
        stay_away=[
            RecommendationOut.model_validate(item)
            for item in recommendations
            if item.decision in {"SKIP", "REVIEW"}
        ],
        quarantined=quarantined,
    )


def _signed_margin(
    recommendation: Recommendation, actual_value: Decimal | None, bet_line: Decimal | None
) -> Decimal | None:
    if actual_value is None or bet_line is None:
        return None
    descriptor = f"{recommendation.market_type} {recommendation.selection}".lower()
    if "under" in descriptor:
        return bet_line - actual_value
    return actual_value - bet_line


def _line_value(
    recommendation: Recommendation, bet_line: Decimal | None, closing_line: Decimal | None
) -> Decimal | None:
    if bet_line is None or closing_line is None:
        return None
    descriptor = f"{recommendation.market_type} {recommendation.selection}".lower()
    if "under" in descriptor:
        return bet_line - closing_line
    return closing_line - bet_line


@router.post("/result", response_model=ResultOut, status_code=status.HTTP_201_CREATED)
def grade_result(payload: ResultCreate, user: SubscribedUser, db: DB) -> ResultOut:
    recommendation = _owned_recommendation(db, payload.recommendation_id, user.id)
    if recommendation.result:
        raise HTTPException(status_code=409, detail="Recommendation is already graded")

    bet_line = payload.bet_line if payload.bet_line is not None else recommendation.line
    miss_distance = _signed_margin(recommendation, payload.actual_value, bet_line)
    clv_probability = (
        Decimal(
            str(
                implied_probability(payload.closing_odds)
                - implied_probability(recommendation.american_odds)
            )
        ).quantize(Decimal("0.000001"))
        if payload.closing_odds is not None
        else None
    )
    result = Result(
        recommendation_id=recommendation.id,
        outcome=payload.outcome,
        final_score=payload.final_score,
        stake=payload.stake,
        profit_loss=payload.profit_loss,
        closing_odds=payload.closing_odds,
        closing_line=payload.closing_line,
        clv_probability=clv_probability,
        line_value=_line_value(recommendation, bet_line, payload.closing_line),
        actual_value=payload.actual_value,
        bet_line=bet_line,
        miss_distance=miss_distance,
        killed_ticket=payload.killed_ticket,
        last_losing_leg=payload.last_losing_leg,
        process_outcome_class=payload.process_outcome_class,
        error_category=payload.error_category,
        assumptions_review=payload.assumptions_review,
        unexpected_events=payload.unexpected_events,
        quick_cash_result=payload.quick_cash_result,
        chain_reaction_result=payload.chain_reaction_result,
        live_trigger_result=payload.live_trigger_result,
        cashout_action=payload.cashout_action,
        cashout_offer=payload.cashout_offer,
        cashout_reason=payload.cashout_reason,
        cashout_time=payload.cashout_time,
        process_grade=payload.process_grade,
        variance_grade=payload.variance_grade,
        root_cause_tags=payload.root_cause_tags,
        lesson=payload.lesson,
        result_time=payload.result_time or utcnow(),
    )
    recommendation.outcome = payload.outcome
    db.add(result)
    db.add(
        LearningEvent(
            recommendation_id=recommendation.id,
            event_type="RESULT_GRADED",
            sport=recommendation.sport,
            market_type=recommendation.market_type,
            analysis={
                "outcome": payload.outcome,
                "stake": str(payload.stake),
                "profit_loss": str(payload.profit_loss),
                "closing_odds": payload.closing_odds,
                "closing_line": str(payload.closing_line)
                if payload.closing_line is not None
                else None,
                "clv_probability": str(clv_probability) if clv_probability is not None else None,
                "actual_value": str(payload.actual_value)
                if payload.actual_value is not None
                else None,
                "bet_line": str(bet_line) if bet_line is not None else None,
                "miss_distance": str(miss_distance) if miss_distance is not None else None,
                "process_outcome_class": payload.process_outcome_class,
                "error_category": payload.error_category,
                "quick_cash_result": payload.quick_cash_result,
                "chain_reaction_result": payload.chain_reaction_result,
                "live_trigger_result": payload.live_trigger_result,
                "cashout_action": payload.cashout_action,
                "cashout_offer": str(payload.cashout_offer)
                if payload.cashout_offer is not None
                else None,
                "cashout_reason": payload.cashout_reason,
                "cashout_time": payload.cashout_time.isoformat()
                if payload.cashout_time is not None
                else None,
                "process_grade": payload.process_grade,
                "variance_grade": payload.variance_grade,
                "root_cause_tags": payload.root_cause_tags,
                "lesson": payload.lesson,
            },
        )
    )
    if (
        payload.outcome == "LOSS"
        and miss_distance is not None
        and abs(miss_distance) <= Decimal("1")
    ):
        db.add(
            LearningEvent(
                recommendation_id=recommendation.id,
                event_type="MISS_BY_ONE",
                sport=recommendation.sport,
                market_type=recommendation.market_type,
                analysis={
                    "signed_miss_distance": str(miss_distance),
                    "killed_ticket": payload.killed_ticket,
                    "last_losing_leg": payload.last_losing_leg,
                    "thesis_key": recommendation.thesis_key,
                    "script_key": recommendation.script_key,
                    "player_key": recommendation.player_key,
                },
            )
        )
    apply_micro_learning(db, result, recommendation)
    db.commit()
    db.refresh(result)
    return ResultOut.model_validate(result)
