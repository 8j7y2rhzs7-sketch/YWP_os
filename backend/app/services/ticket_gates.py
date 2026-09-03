"""Shared YWP ticket and slate integrity gates."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from app.models import Recommendation

CASH_CARD_KEYS = {"cash_builder", "no_stress", "quick_cash"}
MAX_MODEL_EDGE = 0.15
IDENTICAL_PROBABILITY_LIMIT = 3
PRE_GAME = "PRE_GAME"
MARKET_OPEN = "OPEN"


def event_market_status(start_time: datetime, now: datetime) -> tuple[str, str]:
    if start_time <= now:
        return "LIVE", "CLOSED"
    return PRE_GAME, MARKET_OPEN


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
    return (status or PRE_GAME).upper() == PRE_GAME


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
