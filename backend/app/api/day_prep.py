"""Ready board and the token-protected day-prep tick.

GET /sports/ready-board is what the phone reads. It never spends Odds credits
itself; if a pull is due it starts one in the background.

POST /sports/day-prep/tick is the wake-up for a scheduler. It rejects calls
unless X-YWP-Day-Prep-Token matches YWP_DAY_PREP_TOKEN.
"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query

from app.core.config import settings
from app.core.database import SessionLocal
from app.deps import DB, SubscribedUser
from app.schemas import ReadyBoardResponse
from app.services.day_prep import advance_day_prep, ready_board_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sports", tags=["sports"])


def _token_ok(provided: str | None) -> bool:
    expected = settings.day_prep_token or ""
    token = provided or ""
    if not expected or not token or len(expected) != len(token):
        return False
    return hmac.compare_digest(token, expected)


def _run_advance() -> None:
    db = SessionLocal()
    try:
        advance_day_prep(db)
    except Exception:
        logger.exception("day prep tick failed")
        db.rollback()
    finally:
        db.close()


@router.get("/ready-board", response_model=ReadyBoardResponse)
def ready_board(user: SubscribedUser, db: DB) -> ReadyBoardResponse:
    """Approved plays already graded for today, plus the same card buttons."""
    return ready_board_for_user(db, user.id)


@router.post("/day-prep/tick")
def day_prep_tick(
    db: DB,
    background: BackgroundTasks,
    x_ywp_day_prep_token: Annotated[str | None, Header()] = None,
    wait: bool = Query(default=False),
) -> dict[str, object]:
    """Scheduler wake-up. One Eastern-time schedule pull, then one priced pull."""
    if not _token_ok(x_ywp_day_prep_token):
        raise HTTPException(status_code=401, detail="Day prep token rejected")
    if wait:
        return advance_day_prep(db)
    background.add_task(_run_advance)
    return {"accepted": True, "mode": "background"}
