"""Shared YWP ticket and slate integrity gates."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.models import Recommendation

CASH_CARD_KEYS = {"cash_builder", "no_stress", "quick_cash"}
MAX_MODEL_EDGE = 0.15
IDENTICAL_PROBABILITY_LIMIT = 3
PRE_GAME = "PRE_GAME"
LIVE = "LIVE"
MARKET_OPEN = "OPEN"
MARKET_CLOSED = "CLOSED"
BOARD_ELIGIBLE_GAME = {PRE_GAME, LIVE}


def early_live_grace() -> timedelta:
    """Wall-clock window after tip/kickoff where LIVE markets stay OPEN."""
    seconds = max(0, int(getattr(settings, "early_live_grace_seconds", 45 * 60) or 0))
    return timedelta(seconds=seconds)


def event_market_status(start_time: datetime, now: datetime) -> tuple[str, str]:
    """Classify event timing for board + lock eligibility.

    Pre-tip → PRE_GAME / OPEN.
    Just tipped (within grace) → LIVE / OPEN so Run still surfaces plays.
    Deeper into the game → LIVE / CLOSED (no silent late-game board spam).
    """
    if start_time > now:
        return PRE_GAME, MARKET_OPEN
    elapsed = now - start_time
    if elapsed <= early_live_grace():
        return LIVE, MARKET_OPEN
    return LIVE, MARKET_CLOSED


def is_early_live_open(
    *,
    game_status: str | None,
    market_status: str | None,
    start_time: datetime | None = None,
    now: datetime | None = None,
) -> bool:
    """True when a LIVE game is still inside the post-tip open window."""
    if (game_status or PRE_GAME).upper() != LIVE:
        return False
    if (market_status or MARKET_OPEN).upper() == MARKET_OPEN:
        return True
    if start_time is None:
        return False
    clock = now or datetime.now(tz=start_time.tzinfo)
    if start_time.tzinfo is None and clock.tzinfo is not None:
        start_time = start_time.replace(tzinfo=clock.tzinfo)
    if clock.tzinfo is None and start_time.tzinfo is not None:
        clock = clock.replace(tzinfo=start_time.tzinfo)
    return start_time <= clock <= start_time + early_live_grace()


def board_game_eligible(game_status: str | None, market_status: str | None) -> bool:
    """Board + ticket eligibility: pre-game, or early LIVE while markets stay OPEN."""
    status = (game_status or PRE_GAME).upper()
    market = (market_status or MARKET_OPEN).upper()
    if status == PRE_GAME and market == MARKET_OPEN:
        return True
    return status == LIVE and market == MARKET_OPEN


def is_pitcher_k_over(item: Recommendation | dict[str, Any]) -> bool:
    if isinstance(item, dict):
        market_type = str(item.get("market_type", ""))
        flag = bool(item.get("market_is_pitcher_strikeout_over"))
    else:
        snapshot = item.snapshot or {}
        market_type = item.market_type
        flag = bool(snapshot.get("market_is_pitcher_strikeout_over"))
    return flag or market_type == "player_strikeouts_over"


def snapshot_game_status(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return PRE_GAME
    return str(snapshot.get("game_status") or PRE_GAME).upper()


def snapshot_market_status(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return MARKET_OPEN
    return str(snapshot.get("market_status") or MARKET_OPEN).upper()


def game_status_ok(status: str | None) -> bool:
    """Allow PRE_GAME and LIVE (market_status_ok still requires OPEN)."""
    return (status or PRE_GAME).upper() in BOARD_ELIGIBLE_GAME


def market_status_ok(status: str | None) -> bool:
    return (status or MARKET_OPEN).upper() == MARKET_OPEN


def model_edge_quarantine(edge: float) -> bool:
    return abs(edge) > MAX_MODEL_EDGE


def pitcher_k_over_count(recommendations: list[Recommendation]) -> int:
    return sum(1 for item in recommendations if is_pitcher_k_over(item))


def cash_card_k_overs_ok(ticket_type: str, recommendations: list[Recommendation]) -> bool:
    if ticket_type not in CASH_CARD_KEYS:
        return True
    return pitcher_k_over_count(recommendations) <= 1


def identical_probability_keys(probabilities: list[float]) -> set[float]:
    counts = Counter(round(value, 4) for value in probabilities)
    return {key for key, count in counts.items() if count >= IDENTICAL_PROBABILITY_LIMIT}


def cap_pitcher_k_overs(
    legs: list[Recommendation], max_k: int = 1
) -> tuple[list[Recommendation], bool]:
    """Keep at most one pitcher-K over. Returns (legs, rejected)."""
    kept: list[Recommendation] = []
    k_count = 0
    rejected = False
    for item in legs:
        if is_pitcher_k_over(item):
            if k_count >= max_k:
                rejected = True
                continue
            k_count += 1
        kept.append(item)
    return kept, rejected
