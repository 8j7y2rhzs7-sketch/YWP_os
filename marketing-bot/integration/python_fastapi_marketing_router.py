"""Cursor integration template for the existing YWP OS FastAPI backend.

Do not paste this in unchanged. Cursor must map the marked adapter functions to
the repository's current authenticated user, card, evidence, and leg models.
The route intentionally refuses records whose verification state is ambiguous.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/marketing", tags=["marketing"])


def require_marketing_service_account() -> Any:
    """Replace with the repository's existing service-token dependency."""
    raise NotImplementedError("Map this to existing YWP OS authentication.")


def load_current_cards_for_marketing() -> list[Any]:
    """Query saved cards; never rebuild or synthesize picks inside this route."""
    raise NotImplementedError("Map this to the repository's current card service.")


def serialize_verified_card(card: Any) -> dict[str, Any]:
    """Map one immutable verified card to YWP_OS_MARKETING_CONTRACT.md."""
    raise NotImplementedError("Map exact model fields without inventing fallbacks.")


@router.get("/approved-cards")
def approved_cards(_: Any = Depends(require_marketing_service_account)) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for source in load_current_cards_for_marketing():
        item = serialize_verified_card(source)
        if item.get("status") != "VERIFIED":
            continue
        if item.get("demo") is not False:
            continue
        if item.get("publicationEligible") is not True:
            continue
        if not item.get("verifiedAsOf") or not item.get("expiresAt"):
            continue
        try:
            expires_at = datetime.fromisoformat(item["expiresAt"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(500, "Invalid marketing card expiry") from exc
        if expires_at <= datetime.now(timezone.utc):
            continue
        cards.append(item)
    return {"generatedAt": datetime.now(timezone.utc).isoformat(), "cards": cards}
