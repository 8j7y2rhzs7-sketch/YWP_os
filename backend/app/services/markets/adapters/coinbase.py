"""Coinbase Advanced Trade public market data.

Host: https://api.coinbase.com/api/v3/brokerage
Candles, ticker, and product book are public. This adapter never sends a key.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.services.markets import COINBASE_TAKER_FEE, CRYPTO_WHITELIST
from app.services.markets.adapter import (
    AdapterHealth,
    Candle,
    Instrument,
    Level,
    OrderBook,
    Quote,
    Settlement,
    VenueDisabled,
)
from app.services.markets.http import PublicHttp

BASE = "https://api.coinbase.com/api/v3/brokerage"
GRANULARITY = {
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h": "ONE_HOUR",
    "1d": "ONE_DAY",
    "ONE_MINUTE": "ONE_MINUTE",
    "FIVE_MINUTE": "FIVE_MINUTE",
    "FIFTEEN_MINUTE": "FIFTEEN_MINUTE",
    "ONE_HOUR": "ONE_HOUR",
    "ONE_DAY": "ONE_DAY",
}


def _f(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(int(float(str(value))), tz=UTC)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


class CoinbaseAdapter:
    venue = "coinbase"
    kind = "crypto_spot"

    def __init__(
        self,
        *,
        enabled: bool = True,
        client: httpx.Client | None = None,
        min_interval: float = 0.12,
    ) -> None:
        self.enabled = enabled
        self.http = PublicHttp(
            self.venue,
            client=client,
            min_interval=min_interval,
        )

    def close(self) -> None:
        self.http.close()

    def _require(self) -> None:
        if not self.enabled:
            raise VenueDisabled(self.venue, "Coinbase is switched off")

    def list_instruments(self, *, category: str | None = None) -> list[Instrument]:
        del category
        self._require()
        return [
            Instrument(
                venue=self.venue,
                instrument_id=symbol,
                kind=self.kind,
                symbol=symbol,
                title=symbol.replace("-", "/"),
                active=True,
            )
            for symbol in CRYPTO_WHITELIST
        ]

    def get_quote(self, instrument_id: str) -> Quote:
        self._require()
        payload = self.http.get_json(f"{BASE}/market/products/{instrument_id}/ticker")
        body = payload if isinstance(payload, dict) else {}
        trades = body.get("trades") if isinstance(body.get("trades"), list) else []
        last = _f(body.get("price"), 0.0)
        stamp = _ts(body.get("time"))
        if trades and isinstance(trades[0], dict):
            last = _f(trades[0].get("price"), last)
            stamp = _ts(trades[0].get("time")) or stamp
        return Quote(
            instrument_id=instrument_id,
            bid=_f(body.get("best_bid"), 0.0) or None,
            ask=_f(body.get("best_ask"), 0.0) or None,
            last=last or None,
            bid_size=_f(body.get("best_bid_quantity"), 0.0) or None,
            ask_size=_f(body.get("best_ask_quantity"), 0.0) or None,
            timestamp=stamp,
        )

    def get_orderbook(self, instrument_id: str, depth: int = 10) -> OrderBook:
        self._require()
        payload = self.http.get_json(
            f"{BASE}/market/product_book",
            params={"product_id": instrument_id, "limit": int(depth)},
        )
        body = payload if isinstance(payload, dict) else {}
        book = body.get("pricebook") if isinstance(body.get("pricebook"), dict) else body
        bids = _levels(book.get("bids") if isinstance(book, dict) else None)
        asks = _levels(book.get("asks") if isinstance(book, dict) else None)
        stamp = _ts(book.get("time")) if isinstance(book, dict) else None
        return OrderBook(instrument_id=instrument_id, bids=bids, asks=asks, timestamp=stamp)

    def get_candles(
        self,
        instrument_id: str,
        granularity: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self._require()
        grain = GRANULARITY.get(granularity, granularity)
        payload = self.http.get_json(
            f"{BASE}/market/products/{instrument_id}/candles",
            params={
                "start": str(int(start.timestamp())),
                "end": str(int(end.timestamp())),
                "granularity": grain,
            },
        )
        rows = _candle_rows(payload)
        candles: list[Candle] = []
        for row in rows:
            parsed = _parse_candle(row, instrument_id, grain)
            if parsed is not None:
                candles.append(parsed)
        candles.sort(key=lambda item: item.ts)
        return candles

    def get_settlement(self, instrument_id: str) -> Settlement | None:
        del instrument_id
        self._require()
        return None

    def fee_for(self, side: str, price: float, qty: float, maker: bool = False) -> float:
        del side
        rate = 0.004 if maker else COINBASE_TAKER_FEE
        return rate * float(price) * float(qty)

    def health(self) -> AdapterHealth:
        status = (
            "disabled" if not self.enabled else "ok" if self.http.last_error is None else "error"
        )
        if self.enabled and self.http.last_success_at is None and self.http.last_error is None:
            status = "not_probed"
        return AdapterHealth(
            venue=self.venue,
            kind=self.kind,
            enabled=self.enabled,
            status=status,
            last_error=self.http.last_error,
            last_latency_ms=self.http.last_latency_ms,
            last_success_at=self.http.last_success_at.isoformat()
            if self.http.last_success_at
            else None,
        )


def _levels(raw: object) -> list[Level]:
    if not isinstance(raw, list):
        return []
    levels: list[Level] = []
    for item in raw:
        if isinstance(item, dict):
            levels.append(Level(price=_f(item.get("price")), size=_f(item.get("size"))))
        elif isinstance(item, list) and len(item) >= 2:
            levels.append(Level(price=_f(item[0]), size=_f(item[1])))
    return [level for level in levels if level.price > 0]


def _candle_rows(payload: object) -> list[object]:
    if isinstance(payload, dict):
        candles = payload.get("candles")
        if isinstance(candles, list):
            return candles
    if isinstance(payload, list):
        return payload
    return []


def _parse_candle(row: object, instrument_id: str, grain: str) -> Candle | None:
    if isinstance(row, dict):
        stamp = _ts(row.get("start") or row.get("time"))
        if stamp is None:
            return None
        return Candle(
            venue="coinbase",
            instrument_id=instrument_id,
            granularity=grain,
            ts=stamp,
            open=_f(row.get("open")),
            high=_f(row.get("high")),
            low=_f(row.get("low")),
            close=_f(row.get("close")),
            volume=_f(row.get("volume")),
        )
    if isinstance(row, list) and len(row) >= 6:
        # Coinbase exchange shape: [time, low, high, open, close, volume]
        stamp = _ts(row[0])
        if stamp is None:
            return None
        return Candle(
            venue="coinbase",
            instrument_id=instrument_id,
            granularity=grain,
            ts=stamp,
            open=_f(row[3]),
            high=_f(row[2]),
            low=_f(row[1]),
            close=_f(row[4]),
            volume=_f(row[5]),
        )
    return None
