"""Locked live cash-out rulings.

These are the misses from the last card:
- a batter cashed out before the last plate appearance still cashed
- a two-catch receiver was used as a reason to sell a different sport
- a basketball number one point away is the miss itself, not a reason to panic-sell
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.calculation_discipline import (
    is_batter_prop_market,
    is_points_count_market,
    is_reception_count_market,
)

CashoutAction = Literal["HOLD", "CASH_OUT"]
CashoutScope = Literal["LEG", "TICKET"]

_FINAL_STATUSES = {"FINAL", "CANCELLED", "CANCELED", "POSTPONED"}


@dataclass(frozen=True, slots=True)
class CashoutRuling:
    action: CashoutAction
    scope: CashoutScope
    code: str
    reason: str


def locked_live_trigger(sport: str, market_type: str) -> str | None:
    """Short card line. Must stay inside the 255-character live_trigger column."""
    market = str(market_type or "")
    sport_l = str(sport or "").lower()
    if is_batter_prop_market(market):
        return "HOLD through the last plate appearance. A quiet box score is not a broken thesis."
    if is_reception_count_market(market):
        return "HOLD until the catch total is final. Two catches does not cash out another leg."
    if sport_l in {"wnba", "nba", "basketball"} and (
        is_points_count_market(market) or "spread" in market.lower() or "handicap" in market.lower()
    ):
        return "One point is the miss. Do not cash a live leg just because the number is close."
    return None


def advise_live_cashout(
    *,
    market_type: str,
    game_status: str,
    thesis_broken: bool = False,
    plate_appearances_remaining: int | None = None,
    sibling_legs_live: bool = False,
) -> CashoutRuling:
    """Say HOLD or CASH_OUT for one leg. A dead leg never authorizes selling the ticket."""
    market = str(market_type or "")
    final = str(game_status or "").upper() in _FINAL_STATUSES
    scope: CashoutScope = "LEG"

    if is_batter_prop_market(market) and not final:
        remaining = plate_appearances_remaining
        if remaining is None or remaining > 0:
            return CashoutRuling(
                action="HOLD",
                scope="LEG",
                code="HOLD_THROUGH_PLATE_APPEARANCE",
                reason=(
                    "A plate appearance is still left. A quiet box score is not a broken thesis."
                ),
            )

    if is_reception_count_market(market) and not final:
        return CashoutRuling(
            action="HOLD",
            scope="LEG",
            code="HOLD_RECEPTIONS_UNTIL_FINAL",
            reason=("The catch total is not final. Two catches does not cash out a different leg."),
        )

    if not thesis_broken:
        return CashoutRuling(
            action="HOLD",
            scope="TICKET" if sibling_legs_live else "LEG",
            code="HOLD_THESIS_INTACT",
            reason="The thesis is intact. A cash-out offer is a new price, not a reason to sell.",
        )

    if not final and is_batter_prop_market(market):
        return CashoutRuling(
            action="HOLD",
            scope="LEG",
            code="HOLD_THROUGH_PLATE_APPEARANCE",
            reason="The batter's night is not verified as over.",
        )

    if sibling_legs_live:
        scope = "LEG"
        return CashoutRuling(
            action="CASH_OUT",
            scope=scope,
            code="CASH_DEAD_LEG_ONLY",
            reason=(
                "This leg is final and the thesis is broken. Cash this leg only. "
                "Leave every live leg on HOLD."
            ),
        )

    return CashoutRuling(
        action="CASH_OUT",
        scope="LEG",
        code="THESIS_BROKEN_FINAL",
        reason="The game is final and the thesis is broken. Close this leg. Do not chase it.",
    )


def ticket_must_hold(rulings: list[CashoutRuling]) -> bool:
    """One surviving leg keeps the ticket on HOLD."""
    return any(item.action == "HOLD" for item in rulings)
