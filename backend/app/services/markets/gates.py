"""Crypto and exchange gates. A failing hard gate cannot become a PLAY."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.services.markets.adapter import OrderBook

FRESH_PRICE_SECONDS = 60
SOURCE_AGREEMENT = 0.003
DEPTH_BAND = 0.005
MIN_DEPTH_MULTIPLE = 20.0
INTENDED_NOTIONAL = 100.0
KALSHI_MAX_SPREAD = 0.04
KALSHI_MIN_ASK_SIZE = 20.0
THIN_VOLUME_RATIO = 0.25


@dataclass
class GateResult:
    hard_skip_reasons: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    wait_codes: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_hard(self, code: str, message: str, *, wait: bool = False) -> None:
        self.hard_skip_reasons.append(message)
        self.reason_codes.append(code)
        if wait:
            self.wait_codes.append(code)

    def add_review(self, code: str, message: str) -> None:
        self.review_reasons.append(message)
        self.reason_codes.append(code)


def prices_agree(primary: float, other: float, tolerance: float = SOURCE_AGREEMENT) -> bool:
    if primary <= 0 or other <= 0:
        return False
    return abs(primary - other) / primary <= tolerance


def price_is_fresh(
    source_time: datetime | None, now: datetime, *, limit_seconds: int = FRESH_PRICE_SECONDS
) -> bool:
    if source_time is None:
        return False
    if source_time.tzinfo is None:
        return False
    age = (now - source_time).total_seconds()
    return 0 <= age <= limit_seconds


def volume_is_thin(volumes: list[float]) -> bool:
    if len(volumes) < 20:
        return False
    base = sum(volumes[-20:]) / 20.0
    if base <= 0:
        return True
    return volumes[-1] < THIN_VOLUME_RATIO * base


def book_depth_ok(
    book: OrderBook | None, mid: float, *, intended_notional: float = INTENDED_NOTIONAL
) -> str | None:
    """Return a reason code when the book cannot support a small read-only size."""
    if book is None or not book.bids or not book.asks or mid <= 0:
        return "BOOK_UNAVAILABLE"
    low = mid * (1.0 - DEPTH_BAND)
    high = mid * (1.0 + DEPTH_BAND)
    bid_notional = sum(level.price * level.size for level in book.bids if level.price >= low)
    ask_notional = sum(level.price * level.size for level in book.asks if level.price <= high)
    if min(bid_notional, ask_notional) < MIN_DEPTH_MULTIPLE * intended_notional:
        return "THIN_BOOK"
    return None


def macro_event_inside(
    now: datetime,
    horizon_hours: float,
    events: list[datetime] | None,
) -> bool:
    if not events:
        return False
    end = now + timedelta(hours=horizon_hours)
    return any(now <= event <= end for event in events)


def contract_spread_ok(bid: float | None, ask: float | None) -> bool:
    if bid is None or ask is None:
        return False
    return (ask - bid) <= KALSHI_MAX_SPREAD and ask >= bid
