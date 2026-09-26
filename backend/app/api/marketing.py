"""Marketing bot feed — read-only Decision Card export + owner eligibility gate."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import AdminUser, DB
from app.models import AuditLog, Ticket
from app.services.marketing_auth import (
    marketing_token_configured,
    rotate_marketing_service_token,
    verify_marketing_service_token,
)
from app.services.marketing_feed import (
    build_approved_marketing_feed,
    set_ticket_publication_eligibility,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])


class MarketingEligibilityIn(BaseModel):
    eligible: bool
    expires_at: datetime | None = Field(
        default=None,
        description="Required when eligible=true. Must be a future UTC timestamp.",
    )


def _extract_provided_token(
    authorization: str | None,
    x_ywp_marketing_token: str | None,
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_ywp_marketing_token:
        return x_ywp_marketing_token.strip()
    return ""


def _require_marketing_token(
    db: DB,
    authorization: str | None,
    x_ywp_marketing_token: str | None,
) -> None:
    if not marketing_token_configured(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Marketing service token is not configured. "
                "Admin: POST /api/v1/marketing/rotate-token"
            ),
        )
    provided = _extract_provided_token(authorization, x_ywp_marketing_token)
    if not verify_marketing_service_token(db, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid marketing service token",
        )


@router.get("/approved-cards")
def approved_cards(
    db: DB,
    authorization: str | None = Header(default=None),
    x_ywp_marketing_token: str | None = Header(default=None),
) -> dict:
    """Read-only feed for the Instagram marketing bot."""
    _require_marketing_token(db, authorization, x_ywp_marketing_token)
    payload = build_approved_marketing_feed(db)
    db.add(
        AuditLog(
            user_id=None,
            action="MARKETING_FEED_READ",
            entity_type="marketing_feed",
            entity_id="approved-cards",
            details={
                "card_count": len(payload.get("cards") or []),
                "source": "marketing_service_token",
            },
        )
    )
    db.commit()
    return payload


@router.post("/rotate-token")
def rotate_token(admin: AdminUser, db: DB) -> dict:
    """Admin-only: mint a new scoped marketing token (plaintext returned once)."""
    result = rotate_marketing_service_token(db, admin_user_id=admin.id)
    db.add(
        AuditLog(
            user_id=admin.id,
            action="MARKETING_TOKEN_ROTATED",
            entity_type="service_credential",
            entity_id="marketing_feed",
            details={"rotated_by": admin.email},
        )
    )
    db.commit()
    return result


@router.post("/tickets/{ticket_id}/publication-eligibility")
def set_publication_eligibility(
    ticket_id: str,
    payload: MarketingEligibilityIn,
    admin: AdminUser,
    db: DB,
) -> dict:
    """Owner/admin gate: mark or revoke a saved ticket for marketing export."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        set_ticket_publication_eligibility(
            db,
            ticket,
            eligible=payload.eligible,
            expires_at=payload.expires_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.add(
        AuditLog(
            user_id=admin.id,
            action=(
                "MARKETING_PUBLICATION_ELIGIBLE"
                if payload.eligible
                else "MARKETING_PUBLICATION_REVOKED"
            ),
            entity_type="ticket",
            entity_id=ticket.id,
            details={
                "eligible": payload.eligible,
                "expires_at": (
                    payload.expires_at.isoformat() if payload.expires_at else None
                ),
            },
        )
    )
    db.commit()
    db.refresh(ticket)
    return {
        "ticket_id": ticket.id,
        "publication_eligible": ticket.publication_eligible,
        "publication_eligible_at": (
            ticket.publication_eligible_at.isoformat()
            if ticket.publication_eligible_at
            else None
        ),
        "publication_expires_at": (
            ticket.publication_expires_at.isoformat()
            if ticket.publication_expires_at
            else None
        ),
    }
