"""Market adapter contract for public, read-only venue data.

Phase 1 adapters implement quotes, books, candles, and settlement.
Order placement is not part of this interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Instrument:
    venue: str
    instrument_id: str
    kind: str
    symbol: str
    title: str
    sport: str | None = None
    league: str | None = None
    rules_text: str = ""
    active: bool = True
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass(frozen=True)
class Quote:
    instrument_id: str
    bid: float | None
    ask: float | None
    last: float | None
    bid_size: float | None = None
    ask_size: float | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class OrderBook:
    instrument_id: str
    bids: list[Level]
    asks: list[Level]
    timestamp: datetime | None = None


@dataclass(frozen=True)
class Candle:
    venue: str
    instrument_id: str
    granularity: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Settlement:
    instrument_id: str
    result: str
    settled_at: datetime | None = None


@dataclass(frozen=True)
class AdapterHealth:
    venue: str
    kind: str
    enabled: bool
    status: str
    last_error: str | None
    last_latency_ms: float | None
    last_success_at: str | None


class AdapterError(Exception):
    def __init__(self, venue: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.venue = venue
        self.status_code = status_code


class VenueDisabled(AdapterError):
    pass


class MarketAdapter(Protocol):
    venue: str
    kind: str

    def list_instruments(self, *, category: str | None = None) -> list[Instrument]: ...

    def get_quote(self, instrument_id: str) -> Quote: ...

    def get_orderbook(self, instrument_id: str, depth: int = 10) -> OrderBook: ...

    def get_candles(
        self,
        instrument_id: str,
        granularity: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]: ...

    def get_settlement(self, instrument_id: str) -> Settlement | None: ...

    def fee_for(self, side: str, price: float, qty: float, maker: bool = False) -> float: ...

    def health(self) -> AdapterHealth: ...
