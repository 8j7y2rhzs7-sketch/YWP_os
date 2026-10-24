"""Front desk: one next step from the board and the user's open tickets.

The back office already pulls the schedule and the priced slate. This desk
only reads that state. It does not invent plays, spend Odds credits, kick a
priced pull, or promise an outcome. Rough steps are logged for the back office.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DayPrepDay, DayPrepPlay, Ticket
from app.schemas import FrontDeskAction, FrontDeskBeat, FrontDeskResponse
from app.services.day_prep import ET, slate_date_for
from app.services.front_desk_log import attach_front_desk_log

DESK_NOTICE = "No outcome is assured. Lock Check still runs before any wager."
_BOARD_ROUTE = "/ready"
_SLATE_ROUTE = "/(tabs)/slate"
_WAITING = {"scheduled", "pricing", "idle", "waiting_for_prices"}


@dataclass(frozen=True)
class DeskTicket:
    id: str
    status: str
    last_lock_status: str | None
    last_lock_expires_at: datetime | None


def _clock(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    local = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    local = local.astimezone(ET)
    hour = local.hour % 12 or 12
    suffix = "AM" if local.hour < 12 else "PM"
    return f"{hour}:{local.minute:02d} {suffix} ET"


def _lock_fresh(ticket: DeskTicket, now: datetime) -> bool:
    if ticket.last_lock_status != "LOCKED" or ticket.last_lock_expires_at is None:
        return False
    expires = ticket.last_lock_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires > now


def _beats(done: str, now: str, later: str) -> list[FrontDeskBeat]:
    return [
        FrontDeskBeat(phase="done", text=done),
        FrontDeskBeat(phase="now", text=now),
        FrontDeskBeat(phase="later", text=later),
    ]


def _response(
    *,
    headline: str,
    detail: str,
    label: str,
    route: str,
    beats: list[FrontDeskBeat],
    ready_status: str,
    approved_plays: int,
    open_tickets: int,
    secondary: FrontDeskAction | None = None,
) -> FrontDeskResponse:
    return FrontDeskResponse(
        bot="front_desk",
        headline=headline,
        detail=detail,
        primary=FrontDeskAction(label=label, route=route),
        secondary=secondary,
        beats=beats,
        ready_status=ready_status,
        approved_plays=approved_plays,
        open_tickets=open_tickets,
        notice=DESK_NOTICE,
    )


def _ticket_route(ticket: DeskTicket) -> str:
    return f"/ticket/{ticket.id}"


def _extra_open(detail: str, open_tickets: int) -> str:
    if open_tickets <= 1:
        return detail
    return f"{detail} This is the newest of {open_tickets} open tickets."


def _from_ticket(
    ticket: DeskTicket,
    *,
    now: datetime,
    ready_status: str,
    approved_plays: int,
    open_tickets: int,
) -> FrontDeskResponse:
    route = _ticket_route(ticket)
    ready = (
        FrontDeskAction(label="OPEN READY PLAYS", route=_BOARD_ROUTE) if approved_plays else None
    )
    if ticket.status == "placed":
        return _response(
            headline="Your ticket is in. Grading waits on the games.",
            detail=_extra_open(
                "Placement is done. The next step is the result, not another pick.",
                open_tickets,
            ),
            label="OPEN TICKET",
            route=route,
            secondary=ready,
            beats=_beats(
                "Ticket placed",
                "Follow the ticket",
                "Grade after the games",
            ),
            ready_status=ready_status,
            approved_plays=approved_plays,
            open_tickets=open_tickets,
        )
    if ticket.last_lock_status in {"WARNING", "CHANGE_REQUIRED"}:
        return _response(
            headline="Lock Check wants another look before this ticket moves.",
            detail=_extra_open(
                "Open the ticket and clear the check. Nothing is placed until you do.",
                open_tickets,
            ),
            label="OPEN TICKET",
            route=route,
            beats=_beats(
                "The ticket is saved",
                "Clear Lock Check",
                "You place it",
            ),
            ready_status=ready_status,
            approved_plays=approved_plays,
            open_tickets=open_tickets,
        )
    if _lock_fresh(ticket, now):
        return _response(
            headline="Lock Check is fresh. Placement stays with you.",
            detail=_extra_open(
                "The lock is still good. Open the ticket when you are ready to place it.",
                open_tickets,
            ),
            label="OPEN TICKET",
            route=route,
            beats=_beats(
                "Lock Check is fresh",
                "Place it when you are ready",
                "Grading waits on the games",
            ),
            ready_status=ready_status,
            approved_plays=approved_plays,
            open_tickets=open_tickets,
        )
    expired = ticket.last_lock_status == "LOCKED"
    if expired:
        headline = "The lock on your ticket has expired."
        detail = "Open it and run Lock Check again. Nothing is placed until that clears."
        now_beat = "Run Lock Check again"
    else:
        headline = "A ticket is open. Finish it before starting another."
        detail = "Open the ticket and take the next step there."
        now_beat = "Finish the open ticket"
    return _response(
        headline=headline,
        detail=_extra_open(detail, open_tickets),
        label="OPEN TICKET",
        route=route,
        beats=_beats("The ticket is saved", now_beat, "Lock Check, then you place it"),
        ready_status=ready_status,
        approved_plays=approved_plays,
        open_tickets=open_tickets,
    )


def _pull_detail(pull2_at: datetime | None, binding_sport: str | None) -> str:
    when = _clock(pull2_at)
    sport = (binding_sport or "").upper()
    if when and sport:
        return f"The priced pull is set for {when}, before the first {sport} start."
    if when:
        return f"The priced pull is set for {when}, before the first start."
    return "Matchups are in. The priced pull is timed off the first start and has not landed."


def _from_board(
    *,
    ready_status: str,
    approved_plays: int,
    pull2_at: datetime | None,
    binding_sport: str | None,
    open_tickets: int,
) -> FrontDeskResponse:
    common = {
        "ready_status": ready_status,
        "approved_plays": approved_plays,
        "open_tickets": open_tickets,
    }
    if ready_status in {"priced", "pass"} and approved_plays > 0:
        noun = "play" if approved_plays == 1 else "plays"
        return _response(
            headline=f"{approved_plays} approved {noun} already waiting.",
            detail="Open Ready plays, build the card you want, then run Lock Check.",
            label="OPEN READY PLAYS",
            route=_BOARD_ROUTE,
            beats=_beats(
                "The priced pull is in",
                "Open the ready list",
                "Lock Check before any wager",
            ),
            **common,
        )
    if ready_status in {"priced", "pass"}:
        return _response(
            headline="The priced pull came back as a pass.",
            detail="No PLAY or LEAN cleared. That is a result. Run only if you want another look.",
            label="RUN FOR ANOTHER LOOK",
            route=_SLATE_ROUTE,
            secondary=FrontDeskAction(label="SEE THE BOARD", route=_BOARD_ROUTE),
            beats=_beats(
                "The priced pull is in",
                "Pass is the result",
                "Run only if you want another look",
            ),
            **common,
        )
    if ready_status == "pricing":
        return _response(
            headline="Prices are being pulled now.",
            detail="This is the one priced look for the day. The ready list fills when it lands.",
            label="SEE THE BOARD",
            route=_BOARD_ROUTE,
            beats=_beats(
                "Matchups are in",
                "Prices are pulling",
                "Ready plays land when it finishes",
            ),
            **common,
        )
    if ready_status == "waiting_for_prices":
        return _response(
            headline="Matchups are in. Prices are not.",
            detail=(
                "The priced pull is waiting on the odds feed. The list fills when that pull lands."
            ),
            label="SEE THE BOARD",
            route=_BOARD_ROUTE,
            beats=_beats(
                "Matchups are in",
                "Waiting on prices",
                "Ready plays show up after that pull",
            ),
            **common,
        )
    if ready_status == "scheduled":
        return _response(
            headline="Matchups are in. Prices are timed.",
            detail=_pull_detail(pull2_at, binding_sport),
            label="SEE THE BOARD",
            route=_BOARD_ROUTE,
            beats=_beats(
                "Matchups are in",
                "Waiting on the priced pull",
                "Ready plays land before tip",
            ),
            **common,
        )
    if ready_status == "missed":
        return _response(
            headline="The priced window closed before a list landed.",
            detail="Nothing was forced in late. Run the slate if you still want a look.",
            label="RUN TODAY'S SLATE",
            route=_SLATE_ROUTE,
            beats=_beats(
                "The window was checked",
                "Run if you still want a look",
                "Tomorrow starts with the schedule",
            ),
            **common,
        )
    if ready_status == "no_games":
        return _response(
            headline="No matchups on today's board.",
            detail=(
                "The schedule pull came back empty. Run the slate if you want to check it yourself."
            ),
            label="RUN TODAY'S SLATE",
            route=_SLATE_ROUTE,
            beats=_beats(
                "The schedule pull is in",
                "Nothing is on the board",
                "Run only if you want a look",
            ),
            **common,
        )
    if ready_status not in _WAITING and approved_plays > 0:
        noun = "play" if approved_plays == 1 else "plays"
        return _response(
            headline=f"{approved_plays} approved {noun} already waiting.",
            detail="Open Ready plays, build the card you want, then run Lock Check.",
            label="OPEN READY PLAYS",
            route=_BOARD_ROUTE,
            beats=_beats(
                "Plays are on the board",
                "Open the ready list",
                "Lock Check before any wager",
            ),
            **common,
        )
    return _response(
        headline="The day has not started on the board yet.",
        detail="Matchups come in on the free pull. Prices follow before the first game.",
        label="SEE THE BOARD",
        route=_BOARD_ROUTE,
        beats=_beats(
            "The day is open",
            "Waiting on matchups",
            "Ready plays show up before tip",
        ),
        **common,
    )


def compose_front_desk(
    *,
    ready_status: str,
    approved_plays: int,
    pull2_at: datetime | None,
    binding_sport: str | None,
    ticket: DeskTicket | None,
    open_tickets: int,
    now: datetime,
) -> FrontDeskResponse:
    """Pick one next step. An open ticket always beats the board."""
    if ticket is not None:
        return _from_ticket(
            ticket,
            now=now,
            ready_status=ready_status,
            approved_plays=approved_plays,
            open_tickets=open_tickets,
        )
    return _from_board(
        ready_status=ready_status,
        approved_plays=approved_plays,
        pull2_at=pull2_at,
        binding_sport=binding_sport,
        open_tickets=open_tickets,
    )


def front_desk_for_user(
    db: Session,
    user_id: str,
    *,
    now: datetime | None = None,
) -> FrontDeskResponse:
    """Read today's board and this user's unsettled tickets. No provider calls."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    slate_date = slate_date_for(moment)
    day = db.get(DayPrepDay, slate_date)
    approved = (
        db.scalar(
            select(func.count())
            .select_from(DayPrepPlay)
            .where(
                DayPrepPlay.slate_date == slate_date,
                DayPrepPlay.decision.in_(("PLAY", "LEAN")),
            )
        )
        or 0
    )
    tickets = list(
        db.scalars(
            select(Ticket)
            .where(Ticket.user_id == user_id, Ticket.settled_at.is_(None))
            .order_by(Ticket.updated_at.desc(), Ticket.created_at.desc())
        ).all()
    )
    newest = tickets[0] if tickets else None
    desk_ticket = (
        None
        if newest is None
        else DeskTicket(
            id=newest.id,
            status=newest.status,
            last_lock_status=newest.last_lock_status,
            last_lock_expires_at=newest.last_lock_expires_at,
        )
    )
    desk = compose_front_desk(
        ready_status=day.status if day is not None else "idle",
        approved_plays=int(approved),
        pull2_at=day.pull2_at if day is not None else None,
        binding_sport=day.binding_sport if day is not None else None,
        ticket=desk_ticket,
        open_tickets=len(tickets),
        now=moment,
    )
    handoff = attach_front_desk_log(db, user_id=user_id, desk=desk, now=moment)
    if handoff:
        desk.handoff = handoff
    return desk
