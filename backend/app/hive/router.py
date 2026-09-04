from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .schemas import HiveActionIn, HiveOutcomeIn, HivePredictionIn, HiveSignalOut
from .service import (
    capture_hive_prediction,
    get_hive_signal,
    record_hive_action,
    resolve_hive_outcome,
)

from app.deps import CurrentUser, DB

router = APIRouter(prefix="/hive", tags=["hive-learning"])


@router.post("/prediction")
def create_prediction(
    payload: HivePredictionIn,
    db: DB,
    current_user: CurrentUser,
):
    try:
        event = capture_hive_prediction(
            db=db,
            contributor_user_id=current_user.id,
            consent_to_hive=payload.consent_to_hive,
            source_recommendation_id=payload.source_recommendation_id,
            sport=payload.sport,
            league=payload.league,
            event_id=payload.event_id,
            event_start_at=payload.event_start_at,
            market=payload.market,
            market_scope=payload.market_scope,
            selection=payload.selection,
            line=payload.line,
            odds_american=payload.odds_american,
            model_probability=payload.model_probability,
            quality_score=payload.quality_score,
            model_version=payload.model_version,
            protocol_version=payload.protocol_version,
            evidence_version=payload.evidence_version,
            data_quality=payload.data_quality,
            feature_flags=payload.feature_flags,
        )
        db.commit()
        return {
            "stored": event is not None,
            "id": getattr(event, "id", None),
            "training_eligible": getattr(event, "training_eligible", False),
        }
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/action")
def action(
    payload: HiveActionIn,
    db: DB,
    current_user: CurrentUser,
):
    # User auth is required so a public caller cannot alter event metadata.
    event = record_hive_action(
        db=db,
        source_recommendation_id=payload.source_recommendation_id,
        action=payload.action,
    )
    db.commit()
    return {"updated": event is not None}


@router.post("/outcome")
def outcome(
    payload: HiveOutcomeIn,
    db: DB,
    current_user: CurrentUser,
):
    # Production integration should normally resolve outcomes from trusted
    # server-side result sync, not directly from the mobile client.
    event = resolve_hive_outcome(
        db=db,
        source_recommendation_id=payload.source_recommendation_id,
        outcome=payload.outcome,
        verified=payload.verified,
        result_source=payload.result_source,
        resolved_at=payload.resolved_at,
    )
    db.commit()
    return {
        "updated": event is not None,
        "training_eligible": getattr(event, "training_eligible", False),
        "ineligibility_reason": getattr(
            event, "training_ineligibility_reason", None
        ),
    }


@router.get("/signal", response_model=HiveSignalOut)
def signal(
    sport: str,
    market: str,
    market_scope: str,
    model_version: str,
    league: str | None = None,
    db: DB,
    current_user: CurrentUser,
):
    s = get_hive_signal(
        db=db,
        sport=sport,
        league=league,
        market=market,
        market_scope=market_scope,
        model_version=model_version,
    )
    return HiveSignalOut(
        sport=s.sport,
        league=s.league,
        market=s.market,
        market_scope=s.market_scope,
        model_version=s.model_version,
        eligible_samples=s.eligible_samples,
        wins=s.wins,
        losses=s.losses,
        pushes=s.pushes,
        voids=s.voids,
        posterior_rate=s.posterior_rate,
        raw_rate=s.raw_rate,
        release_version=s.release_version,
    )
