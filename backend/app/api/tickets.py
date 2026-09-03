from __future__ import annotations

from collections import Counter
from datetime import UTC
from decimal import ROUND_HALF_UP, Decimal
from math import prod

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.security import utcnow
from app.deps import DB, CurrentUser
from app.models import (
    AuditLog,
    BankrollAccount,
    Recommendation,
    Ticket,
    TicketLeg,
)
from app.schemas import (
    LockCheckOut,
    LockCheckRequest,
    MessageOut,
    TicketCreate,
    TicketLegAction,
    TicketOut,
)
from app.services.decision_engine import american_to_decimal
from app.services.lock_check import load_ticket_for_lock, run_lock_check

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _load_ticket(db: DB, ticket_id: str, user_id: str) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .options(selectinload(Ticket.legs).selectinload(TicketLeg.recommendation))
        .where(Ticket.id == ticket_id, Ticket.user_id == user_id)
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _active_legs(ticket: Ticket) -> list[TicketLeg]:
    return [leg for leg in ticket.legs if leg.action in {"follow", "replace"}]


def _recalculate(ticket: Ticket) -> None:
    active = _active_legs(ticket)
    if not active:
        ticket.combined_decimal_odds = Decimal("1.0000")
        ticket.potential_payout = Decimal("0.00")
        ticket.confidence_score = 0
        ticket.risk = "none"
        return
    combined = prod(american_to_decimal(leg.american_odds) for leg in active)
    ticket.combined_decimal_odds = Decimal(str(combined)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    ticket.potential_payout = (ticket.stake * ticket.combined_decimal_odds).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    ticket.confidence_score = round(
        sum(leg.recommendation.confidence_score for leg in active) / len(active)
    )
    risk_order = {"low": 0, "medium": 1, "medium_high": 2, "high": 3}
    ticket.risk = max(
        (leg.recommendation.risk for leg in active),
        key=lambda value: risk_order.get(value, 2),
    )


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, user: CurrentUser, db: DB) -> TicketOut:
    if len(payload.recommendation_ids) != len(set(payload.recommendation_ids)):
        raise HTTPException(status_code=422, detail="Duplicate recommendation IDs are not allowed")
    recommendations = list(
        db.scalars(
            select(Recommendation).where(
                Recommendation.id.in_(payload.recommendation_ids),
                Recommendation.created_by_user_id == user.id,
            )
        ).all()
    )
    if len(recommendations) != len(payload.recommendation_ids):
        raise HTTPException(status_code=404, detail="One or more recommendations were not found")
    by_id = {item.id: item for item in recommendations}
    recommendations = [by_id[item_id] for item_id in payload.recommendation_ids]
    if any(item.decision not in {"PLAY", "LEAN"} for item in recommendations):
        raise HTTPException(
            status_code=422, detail="Only PLAY or LEAN recommendations can be saved"
        )
    if len({item.slate_date for item in recommendations}) != 1:
        raise HTTPException(status_code=422, detail="A ticket must use one slate date")

    thesis_counts = Counter(item.thesis_key for item in recommendations)
    if any(count > 1 for count in thesis_counts.values()):
        raise HTTPException(status_code=422, detail="A thesis may appear only once on a ticket")
    script_counts = Counter(item.script_key for item in recommendations)
    if any(count > 1 for count in script_counts.values()) and not payload.intentional_correlation:
        raise HTTPException(
            status_code=422,
            detail="Correlated script exposure requires intentional_correlation=true",
        )

    bankroll = db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == user.id))
    if bankroll and bankroll.balance > 0:
        stake_cap = bankroll.balance * bankroll.max_stake_pct
        if payload.stake > stake_cap and not payload.override_acknowledged:
            raise HTTPException(
                status_code=422,
                detail=f"Stake exceeds the configured cap of {stake_cap:.2f}",
            )

    repeated_theses = set(
        db.scalars(
            select(TicketLeg.thesis_key)
            .join(Ticket, Ticket.id == TicketLeg.ticket_id)
            .where(
                Ticket.user_id == user.id,
                Ticket.status.in_(["draft", "locked", "placed"]),
                TicketLeg.action.in_(["follow", "replace"]),
                TicketLeg.thesis_key.in_(set(thesis_counts)),
            )
        ).all()
    )
    if repeated_theses and not payload.intentional_thesis_exposure:
        raise HTTPException(
            status_code=422,
            detail="Cross-ticket thesis exposure requires explicit intent: "
            + ", ".join(sorted(repeated_theses)),
        )
    if repeated_theses and bankroll and bankroll.balance > 0:
        existing_tickets = list(
            db.scalars(
                select(Ticket)
                .join(TicketLeg, TicketLeg.ticket_id == Ticket.id)
                .where(
                    Ticket.user_id == user.id,
                    Ticket.status.in_(["draft", "locked", "placed"]),
                    TicketLeg.thesis_key.in_(repeated_theses),
                    TicketLeg.action.in_(["follow", "replace"]),
                )
                .distinct()
            ).all()
        )
        thesis_exposure = (
            sum((item.stake for item in existing_tickets), start=Decimal("0.00")) + payload.stake
        )
        thesis_cap = bankroll.balance * bankroll.max_thesis_exposure_pct
        if thesis_exposure > thesis_cap and not payload.override_acknowledged:
            raise HTTPException(
                status_code=422,
                detail=f"Combined thesis exposure exceeds the configured cap of {thesis_cap:.2f}",
            )

    sport_names = {item.sport for item in recommendations}
    ticket = Ticket(
        user_id=user.id,
        ticket_type=payload.ticket_type,
        label=payload.label,
        sport=next(iter(sport_names)) if len(sport_names) == 1 else "multi",
        slate_date=recommendations[0].slate_date,
        stake=payload.stake,
        potential_payout=Decimal("0.00"),
        combined_decimal_odds=Decimal("1.0000"),
        risk="none",
        confidence_score=0,
        intentional_correlation=payload.intentional_correlation,
        intentional_thesis_exposure=payload.intentional_thesis_exposure,
        override_acknowledged=payload.override_acknowledged,
    )
    db.add(ticket)
    db.flush()
    for position, recommendation in enumerate(recommendations, start=1):
        ticket.legs.append(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=recommendation.id,
                position=position,
                selection=recommendation.selection,
                american_odds=recommendation.american_odds,
                thesis_key=recommendation.thesis_key,
                script_key=recommendation.script_key,
                action="follow",
            )
        )
    db.flush()
    _recalculate(ticket)
    db.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_CREATED",
            entity_type="ticket",
            entity_id=ticket.id,
            details={
                "ticket_type": ticket.ticket_type,
                "recommendation_ids": payload.recommendation_ids,
                "stake": str(payload.stake),
            },
        )
    )
    db.commit()
    return TicketOut.model_validate(_load_ticket(db, ticket.id, user.id))


@router.get("", response_model=list[TicketOut])
def list_tickets(user: CurrentUser, db: DB, limit: int = 100) -> list[TicketOut]:
    tickets = db.scalars(
        select(Ticket)
        .options(selectinload(Ticket.legs).selectinload(TicketLeg.recommendation))
        .where(Ticket.user_id == user.id)
        .order_by(Ticket.created_at.desc())
        .limit(min(max(limit, 1), 500))
    ).all()
    return [TicketOut.model_validate(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, user: CurrentUser, db: DB) -> TicketOut:
    return TicketOut.model_validate(_load_ticket(db, ticket_id, user.id))


@router.patch("/{ticket_id}/legs/{leg_id}", response_model=TicketOut)
def change_leg(
    ticket_id: str,
    leg_id: str,
    payload: TicketLegAction,
    user: CurrentUser,
    db: DB,
) -> TicketOut:
    ticket = _load_ticket(db, ticket_id, user.id)
    if ticket.status in {"placed", "settled", "cancelled"}:
        raise HTTPException(status_code=409, detail="This ticket can no longer be edited")
    leg = next((item for item in ticket.legs if item.id == leg_id), None)
    if not leg:
        raise HTTPException(status_code=404, detail="Ticket leg not found")

    if payload.action == "skip":
        leg.action = "skip"
        leg.skip_reason = payload.skip_reason
    elif payload.action == "follow":
        leg.action = "follow"
        leg.skip_reason = None
    else:
        replacement = db.scalar(
            select(Recommendation).where(
                Recommendation.id == payload.replacement_recommendation_id,
                Recommendation.created_by_user_id == user.id,
            )
        )
        if not replacement or replacement.decision not in {"PLAY", "LEAN"}:
            raise HTTPException(status_code=422, detail="Replacement is not a qualified play")
        other_theses = {
            item.thesis_key
            for item in ticket.legs
            if item.id != leg.id and item.action in {"follow", "replace"}
        }
        if replacement.thesis_key in other_theses:
            raise HTTPException(status_code=422, detail="Replacement duplicates a ticket thesis")
        leg.recommendation_id = replacement.id
        leg.recommendation = replacement
        leg.selection = replacement.selection
        leg.american_odds = replacement.american_odds
        leg.thesis_key = replacement.thesis_key
        leg.script_key = replacement.script_key
        leg.action = "replace"
        leg.skip_reason = None

    ticket.status = "draft"
    ticket.last_lock_status = None
    ticket.last_lock_expires_at = None
    _recalculate(ticket)
    db.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_LEG_CHANGED",
            entity_type="ticket_leg",
            entity_id=leg.id,
            details={
                "action": payload.action,
                "replacement_recommendation_id": payload.replacement_recommendation_id,
                "skip_reason": payload.skip_reason,
            },
        )
    )
    db.commit()
    return TicketOut.model_validate(_load_ticket(db, ticket.id, user.id))


@router.post("/{ticket_id}/lock-check", response_model=LockCheckOut)
def lock_check(
    ticket_id: str,
    payload: LockCheckRequest,
    user: CurrentUser,
    db: DB,
) -> LockCheckOut:
    ticket = load_ticket_for_lock(db, ticket_id, user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status in {"placed", "settled", "cancelled"}:
        raise HTTPException(status_code=409, detail="This ticket cannot be lock-checked")
    if not _active_legs(ticket):
        raise HTTPException(status_code=422, detail="No active legs remain")
    return LockCheckOut.model_validate(run_lock_check(db, ticket, user.id, payload))


@router.post("/{ticket_id}/place", response_model=TicketOut)
def place_ticket(ticket_id: str, user: CurrentUser, db: DB) -> TicketOut:
    ticket = _load_ticket(db, ticket_id, user.id)
    if ticket.last_lock_status != "LOCKED" or ticket.last_lock_expires_at is None:
        raise HTTPException(status_code=409, detail="A current LOCKED Lock Check is required")
    if _aware(ticket.last_lock_expires_at) <= utcnow():
        raise HTTPException(status_code=409, detail="Lock Check expired; run it again")
    ticket.status = "placed"
    for leg in _active_legs(ticket):
        leg.status = "placed"
    db.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_PLACED",
            entity_type="ticket",
            entity_id=ticket.id,
            details={"stake": str(ticket.stake), "lock_status": ticket.last_lock_status},
        )
    )
    db.commit()
    return TicketOut.model_validate(_load_ticket(db, ticket.id, user.id))


@router.post("/{ticket_id}/cancel", response_model=MessageOut)
def cancel_ticket(ticket_id: str, user: CurrentUser, db: DB) -> MessageOut:
    ticket = _load_ticket(db, ticket_id, user.id)
    if ticket.status == "settled":
        raise HTTPException(status_code=409, detail="A settled ticket cannot be cancelled")
    ticket.status = "cancelled"
    db.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_CANCELLED",
            entity_type="ticket",
            entity_id=ticket.id,
        )
    )
    db.commit()
    return MessageOut(message="Ticket cancelled")
