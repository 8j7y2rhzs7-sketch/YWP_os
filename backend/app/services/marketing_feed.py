"""Read-only marketing feed — export publication-eligible Decision Cards.

The marketing bot must never recompute picks. This service only serializes
immutable saved tickets the owner marked publication-eligible, after strict
VERIFIED / non-demo / unexpired / complete-evidence checks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import utcnow
from app.models import Recommendation, Ticket, TicketLeg
from app.services.board_metrics import (
    bookmaker_display_name,
    model_win_probability,
    verification_status_from_snapshot,
)

ACTIVE_LEG_ACTIONS = frozenset({"follow", "replace"})
BLOCKED_DECISIONS = frozenset({"SKIP", "REVIEW"})
DEMO_SOURCE_TOKENS = ("demo", "synthetic", "ywp_demo")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    return _aware(value).astimezone(UTC).isoformat().replace("+00:00", "Z")


def _leg_recs(ticket: Ticket) -> list[Recommendation]:
    out: list[Recommendation] = []
    for leg in ticket.legs or []:
        if leg.action not in ACTIVE_LEG_ACTIONS:
            continue
        if leg.recommendation is None:
            continue
        out.append(leg.recommendation)
    return out


def _is_demo_recommendation(rec: Recommendation) -> bool:
    source = f"{rec.data_source or ''} {(rec.snapshot or {}).get('probability_source') or ''}".lower()
    if any(token in source for token in DEMO_SOURCE_TOKENS):
        return True
    if verification_status_from_snapshot(rec.snapshot) == "DEMO":
        return True
    return "DEMO_DATA" in (rec.reason_codes or [])


def _leg_status(rec: Recommendation) -> str:
    if _is_demo_recommendation(rec):
        return "DEMO"
    if rec.decision in BLOCKED_DECISIONS:
        return str(rec.decision)
    readiness = verification_status_from_snapshot(rec.snapshot)
    if readiness != "VERIFIED":
        return readiness
    # Stale evidence: source older than 6h relative to now for pregame cards.
    source_ts = _aware(rec.source_timestamp)
    if source_ts is None:
        return "PARTIAL"
    age = utcnow() - source_ts
    if age > timedelta(hours=6):
        return "EXPIRED"
    return "VERIFIED"


def _card_status(ticket: Ticket, legs: list[Recommendation]) -> str:
    if not ticket.publication_eligible:
        return "REVIEW"
    expires = _aware(ticket.publication_expires_at)
    if expires is None:
        return "PARTIAL"
    if expires <= utcnow():
        return "EXPIRED"
    statuses = [_leg_status(rec) for rec in legs]
    if not statuses:
        return "PARTIAL"
    if any(s == "DEMO" for s in statuses):
        return "DEMO"
    if any(s in BLOCKED_DECISIONS for s in statuses):
        return "SKIP" if "SKIP" in statuses else "REVIEW"
    if any(s == "EXPIRED" for s in statuses):
        return "EXPIRED"
    if any(s != "VERIFIED" for s in statuses):
        return "PARTIAL"
    return "VERIFIED"


def _data_quality_label(legs: list[Recommendation]) -> str | None:
    if not legs:
        return None
    qualities = [float(rec.data_quality or 0) for rec in legs]
    if any(q < 0.85 for q in qualities):
        return "PARTIAL"
    return "COMPLETE"


def _event_start(legs: list[Recommendation]) -> datetime | None:
    starts: list[datetime] = []
    for rec in legs:
        start = rec.start_time
        if isinstance(start, datetime):
            starts.append(_aware(start) or start)
    if not starts:
        return None
    return min(starts)


def _sportsbook(legs: list[Recommendation]) -> str | None:
    labels: list[str] = []
    for rec in legs:
        snap = rec.snapshot or {}
        label = (
            snap.get("bookmaker_label")
            or bookmaker_display_name(str(snap.get("bookmaker") or "") or None)
            or rec.bookmaker_label
        )
        if label:
            labels.append(str(label))
    if not labels:
        return None
    # Prefer Hard Rock when present on any leg; otherwise first label.
    for label in labels:
        if "hard rock" in label.casefold():
            return label
    return labels[0]


def _market_label(rec: Recommendation) -> str:
    market = (rec.market_type or "").replace("_", " ").strip()
    period = (rec.market_period or "").replace("_", " ").strip()
    if period and period.casefold() not in {"full game", "full_game"}:
        return f"{market} ({period})".strip()
    return market or "Market"


def _price(rec: Recommendation) -> str:
    odds = int(rec.american_odds)
    return f"+{odds}" if odds > 0 else str(odds)


def _line(rec: Recommendation) -> str | None:
    if rec.line is None:
        return None
    text = format(rec.line, "f").rstrip("0").rstrip(".")
    return text or None


def serialize_ticket_card(ticket: Ticket) -> dict[str, Any] | None:
    """Map one saved ticket to the marketing contract, or None if unusable."""
    legs = _leg_recs(ticket)
    if not legs:
        return None
    status = _card_status(ticket, legs)
    demo = any(_is_demo_recommendation(rec) for rec in legs)
    event_start = _event_start(legs)
    expires_at = _aware(ticket.publication_expires_at)
    verified_as_of = _aware(ticket.publication_eligible_at) or max(
        (_aware(rec.source_timestamp) for rec in legs if rec.source_timestamp),
        default=None,
    )
    if event_start is None or expires_at is None or verified_as_of is None:
        return None

    qualities = [float(rec.data_quality or 0) for rec in legs]
    # Aggregate model probability only when every leg has an independent model.
    model_probs: list[float] = []
    for rec in legs:
        snap = rec.snapshot or {}
        prob = model_win_probability(
            adjusted_probability=float(rec.adjusted_probability),
            probability_source=str(snap.get("probability_source") or ""),
        )
        if prob is None:
            model_probs = []
            break
        model_probs.append(prob)

    ywp_scores = [int(rec.confidence_score) for rec in legs]
    serialized_legs: list[dict[str, Any]] = []
    for leg in ticket.legs or []:
        if leg.action not in ACTIVE_LEG_ACTIONS or leg.recommendation is None:
            continue
        rec = leg.recommendation
        serialized_legs.append(
            {
                "id": str(leg.id),
                "event": str(rec.event_name),
                "selection": str(rec.selection),
                "market": _market_label(rec),
                "line": _line(rec),
                "price": _price(rec),
            }
        )
    if not serialized_legs:
        return None

    card: dict[str, Any] = {
        "id": str(ticket.id),
        "sport": str(ticket.sport or legs[0].sport or "").upper(),
        "title": str(ticket.label or "YWP Decision Card"),
        "status": status,
        "publicationEligible": bool(ticket.publication_eligible),
        "demo": demo,
        "sportsbook": _sportsbook(legs),
        "eventStart": _iso(event_start),
        "verifiedAsOf": _iso(verified_as_of),
        "expiresAt": _iso(expires_at),
        "ywpScore": min(ywp_scores) if ywp_scores else None,
        "modelProbability": (
            round(sum(model_probs) / len(model_probs), 4) if model_probs else None
        ),
        "dataQuality": _data_quality_label(legs),
        "sourceVersion": settings.app_version,
        "legs": serialized_legs,
    }
    return card


def load_publication_eligible_tickets(db: Session) -> list[Ticket]:
    return list(
        db.scalars(
            select(Ticket)
            .where(Ticket.publication_eligible.is_(True))
            .options(
                joinedload(Ticket.legs).joinedload(TicketLeg.recommendation),
            )
            .order_by(Ticket.publication_eligible_at.desc())
            .limit(40)
        )
        .unique()
        .all()
    )


def build_approved_marketing_feed(db: Session) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    now = utcnow()
    for ticket in load_publication_eligible_tickets(db):
        item = serialize_ticket_card(ticket)
        if item is None:
            continue
        if item.get("status") != "VERIFIED":
            continue
        if item.get("demo") is not False:
            continue
        if item.get("publicationEligible") is not True:
            continue
        if item.get("dataQuality") != "COMPLETE":
            continue
        try:
            expires_at = datetime.fromisoformat(
                str(item["expiresAt"]).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            continue
        if _aware(expires_at) is None or _aware(expires_at) <= now:
            continue
        cards.append(item)
    return {"generatedAt": _iso(now), "cards": cards}


def set_ticket_publication_eligibility(
    db: Session,
    ticket: Ticket,
    *,
    eligible: bool,
    expires_at: datetime | None = None,
) -> Ticket:
    """Owner gate: mark or revoke marketing publication eligibility."""
    if eligible:
        if expires_at is None:
            raise ValueError("expires_at is required when marking a card publication-eligible")
        aware_expires = _aware(expires_at)
        if aware_expires is None or aware_expires <= utcnow():
            raise ValueError("expires_at must be in the future")
        ticket.publication_eligible = True
        ticket.publication_eligible_at = utcnow()
        ticket.publication_expires_at = aware_expires
    else:
        ticket.publication_eligible = False
        ticket.publication_eligible_at = None
        ticket.publication_expires_at = None
    db.add(ticket)
    return ticket
