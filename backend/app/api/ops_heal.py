"""Ops Heal API — product self-heal + full-process evidence + improvement inbox."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import DB, SubscribedUser
from app.services.ops_evidence import (
    collect_all_process_evidence,
    latest_evidence_pack,
    persist_evidence_pack,
)
from app.services.ops_heal import (
    latest_ops_heal_status,
    list_ops_heal_cycles,
    list_ops_heal_proposals,
    review_ops_heal_proposal,
    run_ops_heal_cycle,
)

router = APIRouter(prefix="/ops-heal", tags=["ops-heal"])


class OpsHealProposalReviewIn(BaseModel):
    action: str = Field(description="implemented | dismissed")
    note: str | None = Field(default=None, max_length=500)


@router.get("/status")
def ops_heal_status(user: SubscribedUser, db: DB) -> dict:
    del user
    return latest_ops_heal_status(db=db)


@router.get("/cycles")
def ops_heal_cycles(
    user: SubscribedUser,
    db: DB,
    limit: int = Query(default=12, ge=1, le=40),
) -> dict:
    del user
    return {"bot": "ops_heal", "cycles": list_ops_heal_cycles(db=db, limit=limit)}


@router.get("/evidence")
def ops_heal_evidence(
    user: SubscribedUser,
    db: DB,
    hours: int = Query(default=72, ge=1, le=168),
    refresh: bool = Query(default=False),
) -> dict:
    """Evidence across all app process movements (API, audits, tickets, Hive, …)."""
    if refresh:
        pack = collect_all_process_evidence(db=db, user_id=user.id, hours=hours)
        persist_evidence_pack(db=db, pack=pack)
        db.commit()
        return pack
    latest = latest_evidence_pack(db=db)
    if latest:
        return latest
    pack = collect_all_process_evidence(db=db, user_id=user.id, hours=hours)
    persist_evidence_pack(db=db, pack=pack)
    db.commit()
    return pack


@router.get("/proposals")
def ops_heal_proposals(
    user: SubscribedUser,
    db: DB,
    status: str = Query(default="pending"),
    limit: int = Query(default=20, ge=1, le=60),
) -> dict:
    del user
    return {
        "bot": "ops_heal",
        "status": status,
        "proposals": list_ops_heal_proposals(db=db, status=status, limit=limit),
    }


@router.post("/proposals/{proposal_id}/review")
def ops_heal_proposal_review(
    proposal_id: str,
    payload: OpsHealProposalReviewIn,
    user: SubscribedUser,
    db: DB,
) -> dict:
    """Human check-in: mark a drafted app change as implemented or dismissed."""
    try:
        reviewed = review_ops_heal_proposal(
            db=db,
            proposal_id=proposal_id,
            action=payload.action,
            reviewer_user_id=user.id,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc
    db.commit()
    return reviewed


@router.post("/run")
def ops_heal_run(
    user: SubscribedUser,
    db: DB,
    apply: bool = Query(default=True),
) -> dict:
    """Collect all-process evidence, remediate, and draft improvement proposals."""
    cycle = run_ops_heal_cycle(
        db=db,
        user_id=user.id,
        timezone_name=user.timezone,
        trigger="manual_api",
        apply=apply,
    )
    db.commit()
    return cycle
