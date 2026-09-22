"""Ops Heal API — product self-heal bot (separate from Hive pick learning)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import DB, SubscribedUser
from app.services.ops_heal import (
    latest_ops_heal_status,
    list_ops_heal_cycles,
    run_ops_heal_cycle,
)

router = APIRouter(prefix="/ops-heal", tags=["ops-heal"])


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


@router.post("/run")
def ops_heal_run(
    user: SubscribedUser,
    db: DB,
    apply: bool = Query(default=True),
) -> dict:
    """Run health contracts + allowlisted remediations for this user."""
    cycle = run_ops_heal_cycle(
        db=db,
        user_id=user.id,
        timezone_name=user.timezone,
        trigger="manual_api",
        apply=apply,
    )
    db.commit()
    return cycle
