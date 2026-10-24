"""Live scores and play tracking for the signed-in user.

GET /live reads ESPN and the MLB Stats API. It does not call The Odds API.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, SubscribedUser
from app.schemas import LiveBoardResponse
from app.services.live_board import build_live_board

router = APIRouter(prefix="/live", tags=["live"])


@router.get("", response_model=LiveBoardResponse)
def live_board(user: SubscribedUser, db: DB) -> LiveBoardResponse:
    """Major games and how open plays are tracking right now."""
    return build_live_board(db, user.id)
