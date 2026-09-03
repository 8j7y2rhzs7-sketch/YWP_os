from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, AdminUser, SubscribedUser
from app.models import AuditLog, LearningEvent, Recommendation, WeightChangeProposal
from app.schemas import (
    ErrorAnalysisRequest,
    LearningPulseOut,
    MessageOut,
    MissByOneOut,
    PatternOut,
    PerformanceOut,
    WeightProposalOut,
    WeightProposalReview,
)
from app.services.learning import (
    learning_pulse,
    miss_by_one_report,
    patterns,
    performance,
    propose_weight_changes,
    review_weight_proposal,
    rollback_weight_proposal,
)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/pulse", response_model=LearningPulseOut)
def pulse(user: SubscribedUser, db: DB) -> LearningPulseOut:
    return LearningPulseOut.model_validate(learning_pulse(db, user.id))


@router.get("/performance", response_model=PerformanceOut)
def performance_report(user: SubscribedUser, db: DB) -> PerformanceOut:
    return performance(db, user.id)


@router.get("/patterns", response_model=PatternOut)
def pattern_report(user: SubscribedUser, db: DB) -> PatternOut:
    return patterns(db, user.id)


@router.get("/miss-by-one", response_model=MissByOneOut)
def miss_by_one(user: SubscribedUser, db: DB) -> MissByOneOut:
    return miss_by_one_report(db, user.id)


@router.post("/error-analysis", response_model=MessageOut)
def error_analysis(payload: ErrorAnalysisRequest, user: SubscribedUser, db: DB) -> MessageOut:
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.id == payload.recommendation_id,
            Recommendation.created_by_user_id == user.id,
        )
    )
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    review = [
        *(f"HELD: {item}" for item in payload.assumptions_that_held),
        *(f"FAILED: {item}" for item in payload.assumptions_that_failed),
    ]
    if recommendation.result:
        recommendation.result.assumptions_review = review
        recommendation.result.unexpected_events = payload.unexpected_events
        recommendation.result.root_cause_tags = payload.root_cause_tags
        recommendation.result.error_category = payload.error_category
        recommendation.result.lesson = payload.lesson
    db.add(
        LearningEvent(
            recommendation_id=recommendation.id,
            event_type="ERROR_ANALYSIS",
            sport=recommendation.sport,
            market_type=recommendation.market_type,
            analysis={
                "assumptions_that_held": payload.assumptions_that_held,
                "assumptions_that_failed": payload.assumptions_that_failed,
                "unexpected_events": payload.unexpected_events,
                "root_cause_tags": payload.root_cause_tags,
                "error_category": payload.error_category,
                "lesson": payload.lesson,
                "process_vs_outcome_kept_separate": True,
            },
        )
    )
    db.commit()
    return MessageOut(message="Error analysis recorded without changing model weights")


@router.get("/weights/proposals", response_model=list[WeightProposalOut])
def list_weight_proposals(_: AdminUser, db: DB) -> list[WeightProposalOut]:
    rows = db.scalars(
        select(WeightChangeProposal).order_by(WeightChangeProposal.created_at.desc())
    ).all()
    return [WeightProposalOut.model_validate(item) for item in rows]


@router.post("/weights/propose", response_model=list[WeightProposalOut])
def propose_weights(_: AdminUser, db: DB) -> list[WeightProposalOut]:
    return [WeightProposalOut.model_validate(item) for item in propose_weight_changes(db)]


@router.post("/weights/proposals/{proposal_id}/review", response_model=WeightProposalOut)
def review_proposal(
    proposal_id: str,
    payload: WeightProposalReview,
    admin: AdminUser,
    db: DB,
) -> WeightProposalOut:
    proposal = db.get(WeightChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Weight proposal not found")
    try:
        reviewed = review_weight_proposal(
            db,
            proposal,
            approve=payload.decision == "approve",
            reviewer_user_id=admin.id,
            note=payload.note,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    db.add(
        AuditLog(
            user_id=admin.id,
            action="WEIGHT_PROPOSAL_REVIEWED",
            entity_type="weight_change_proposal",
            entity_id=proposal.id,
            details={"decision": payload.decision, "note": payload.note},
        )
    )
    db.commit()
    db.refresh(reviewed)
    return WeightProposalOut.model_validate(reviewed)


@router.post("/weights/proposals/{proposal_id}/rollback", response_model=WeightProposalOut)
def rollback_proposal(proposal_id: str, admin: AdminUser, db: DB) -> WeightProposalOut:
    proposal = db.get(WeightChangeProposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Weight proposal not found")
    try:
        rolled_back = rollback_weight_proposal(db, proposal, admin.id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    db.add(
        AuditLog(
            user_id=admin.id,
            action="WEIGHT_PROPOSAL_ROLLED_BACK",
            entity_type="weight_change_proposal",
            entity_id=proposal.id,
        )
    )
    db.commit()
    db.refresh(rolled_back)
    return WeightProposalOut.model_validate(rolled_back)
