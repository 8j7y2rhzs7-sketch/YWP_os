"""Front desk for the signed-in user.

GET /desk reads the ready board and open tickets. It never starts a pull.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, SubscribedUser
from app.schemas import FrontDeskResponse
from app.services.front_desk import front_desk_for_user

router = APIRouter(prefix="/desk", tags=["desk"])


@router.get("", response_model=FrontDeskResponse)
def desk(user: SubscribedUser, db: DB) -> FrontDeskResponse:
    """One next step. Does not spend Odds or kick day prep."""
    return front_desk_for_user(db, user.id)
