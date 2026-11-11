"""Front-desk log and the error handoff into the back office.

Every distinct step is an audit row. A missed window or a price stall is also
an error report plus one ops-heal proposal. The desk still does not spend
Odds, kick a pull, or edit source code. A person implements the brief.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditLog, ErrorReport
from app.schemas import FrontDeskResponse

logger = logging.getLogger(__name__)

HANDOFF = "Logged for the back office to fix."
STEP_WINDOW = timedelta(minutes=30)
ERROR_WINDOW = timedelta(hours=12)

BRIEFS: dict[str, dict[str, str]] = {
    "missed": {
        "title": "Price the slate before the front desk misses the window",
        "message": "Front desk: the priced window closed before a list landed.",
        "change": (
            "Review the learned lead and the day-prep wake. "
            "The priced pull has to land before the first start."
        ),
        "category": "data",
        "priority": "medium",
    },
    "waiting_for_prices": {
        "title": "Let the front desk show prices after matchups are in",
        "message": "Front desk: matchups are in but prices never landed.",
        "change": (
            "Confirm the odds feed is configured and a later tick can still "
            "price this Eastern day. The desk must not spend a credit to retry."
        ),
        "category": "api",
        "priority": "high",
    },
    "load_failed": {
        "title": "Keep the front desk readable when its load fails",
        "message": "Front desk failed to load.",
        "change": (
            "Reproduce the Front desk load failure, fix the failing read, "
            "and keep Home usable while it is down."
        ),
        "category": "api",
        "priority": "high",
    },
}


def _kind(desk: FrontDeskResponse) -> str | None:
    if desk.ready_status == "missed":
        return "missed"
    if desk.ready_status == "waiting_for_prices":
        return "waiting_for_prices"
    return None


def _fingerprint(desk: FrontDeskResponse) -> str:
    route = desk.primary.route
    return f"{desk.ready_status}|{route}|{desk.approved_plays}|{desk.open_tickets}"


def _recent_step(db: Session, user_id: str, fingerprint: str, now: datetime) -> bool:
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.user_id == user_id,
            AuditLog.action == "FRONT_DESK_STEP",
            AuditLog.created_at >= now - STEP_WINDOW,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    ).all()
    return any((row.details or {}).get("fingerprint") == fingerprint for row in rows)


def _recent_error(db: Session, user_id: str, kind: str, now: datetime) -> bool:
    rows = db.scalars(
        select(ErrorReport)
        .where(
            ErrorReport.user_id == user_id,
            ErrorReport.screen == "Front desk",
            ErrorReport.created_at >= now - ERROR_WINDOW,
        )
        .order_by(ErrorReport.created_at.desc())
        .limit(12)
    ).all()
    return any((row.context or {}).get("kind") == kind for row in rows)


def _proposal(kind: str, desk: FrontDeskResponse) -> dict[str, object]:
    brief = BRIEFS[kind]
    return {
        "fingerprint": f"front_desk:{kind}",
        "area": "front_desk",
        "priority": brief["priority"],
        "title": brief["title"],
        "summary": brief["message"],
        "recommended_change": brief["change"],
        "source_contracts": [],
        "auto_remediations_tried": [],
        "evidence": {
            "kind": kind,
            "ready_status": desk.ready_status,
            "route": desk.primary.route,
            "approved_plays": desk.approved_plays,
            "screen": "Front desk",
        },
    }


def attach_front_desk_log(
    db: Session,
    *,
    user_id: str,
    desk: FrontDeskResponse,
    now: datetime,
) -> str | None:
    """Write the step log and, for a rough board, one back-office brief.

    Returns the customer handoff line when an error is on file. Failures here
    never change the step the customer sees.
    """
    wrote = False
    handoff: str | None = None
    try:
        fingerprint = _fingerprint(desk)
        if not _recent_step(db, user_id, fingerprint, now):
            db.add(
                AuditLog(
                    user_id=user_id,
                    action="FRONT_DESK_STEP",
                    entity_type="front_desk",
                    entity_id=desk.ready_status[:64],
                    details={
                        "fingerprint": fingerprint,
                        "ready_status": desk.ready_status,
                        "route": desk.primary.route,
                        "headline": desk.headline[:160],
                        "approved_plays": desk.approved_plays,
                        "open_tickets": desk.open_tickets,
                    },
                )
            )
            wrote = True

        kind = _kind(desk)
        if kind is not None:
            handoff = HANDOFF
            brief = BRIEFS[kind]
            if not _recent_error(db, user_id, kind, now):
                db.add(
                    ErrorReport(
                        user_id=user_id,
                        category=brief["category"],
                        message=brief["message"],
                        screen="Front desk",
                        app_version=settings.app_version,
                        platform="api",
                        context={
                            "source": "front_desk",
                            "kind": kind,
                            "ready_status": desk.ready_status,
                            "route": desk.primary.route,
                        },
                        status="open",
                    )
                )
                db.add(
                    AuditLog(
                        user_id=user_id,
                        action="FRONT_DESK_ERROR",
                        entity_type="error_report",
                        entity_id=kind,
                        details={"kind": kind, "source": "front_desk"},
                    )
                )
                from app.services.ops_heal import upsert_improvement_proposals

                upsert_improvement_proposals(db=db, drafts=[_proposal(kind, desk)])
                wrote = True
        if wrote:
            db.commit()
    except Exception:
        logger.exception("front desk log failed")
        db.rollback()
        return None
    return handoff
