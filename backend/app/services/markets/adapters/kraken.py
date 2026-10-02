"""Kraken public OHLC and depth. Used as a price cross-check, not a trading venue."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.services.markets import KRAKEN_TAKER_FEE
from app.services.markets.adapter import (
    AdapterError,
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

BASE = "https://api.kraken.com/0/public"
PAIR_MAP = {
    "BTC-USD": "XBTUSD",
    "ETH-USD": "ETHUSD",
    "SOL-USD": "SOLUSD",
    "XBTUSD": "XBTUSD",
    "ETHUSD": "ETHUSD",
    "SOLUSD": "SOLUSD",
}
INTERVALS = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "ONE_HOUR": 60,
    "FIFTEEN_MINUTE": 15,
    "ONE_DAY": 1440,
}


def _f(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class KrakenAdapter:
    venue = "kraken"
    kind = "crypto_spot"

    def __init__(
        self,
        *,
        enabled: bool = True,
        client: httpx.Client | None = None,
        min_interval: float = 1.05,
    ) -> None:
        self.enabled = enabled
        self.http = PublicHttp(self.venue, client=client, min_interval=min_interval)

    def close(self) -> None:
        self.http.close()

    def _require(self) -> None:
        if not self.enabled:
            raise VenueDisabled(self.venue, "Kraken is switched off")

    def list_instruments(self, *, category: str | None = None) -> list[Instrument]:
        del category
        self._require()
        return [
            Instrument(
                venue=self.venue,
                instrument_id=symbol,
                kind=self.kind,
                symbol=symbol,
                title=symbol,
                active=True,
            )
            for symbol in ("BTC-USD", "ETH-USD", "SOL-USD")
        ]

    def _pair(self, instrument_id: str) -> str:
        pair = PAIR_MAP.get(instrument_id.upper())
        if not pair:
            raise AdapterError(self.venue, f"{instrument_id} is not on the Kraken cross-check list")
        return pair

    def get_quote(self, instrument_id: str) -> Quote:
        self._require()
        pair = self._pair(instrument_id)
        payload = self.http.get_json(f"{BASE}/Ticker", params={"pair": pair})
        result = _result(payload)
        row = _first_row(result)
        # Kraken ticker: c = last [price, lot], b = bid, a = ask
        last = _f(row.get("c", [None])[0]) if isinstance(row.get("c"), list) else 0.0
        bid_row = row.get("b") if isinstance(row.get("b"), list) else [None, None]
        ask_row = row.get("a") if isinstance(row.get("a"), list) else [None, None]
        return Quote(
            instrument_id=instrument_id,
            bid=_f(bid_row[0]) or None,
            ask=_f(ask_row[0]) or None,
            last=last or None,
            bid_size=_f(bid_row[1]) if len(bid_row) > 1 else None,
            ask_size=_f(ask_row[1]) if len(ask_row) > 1 else None,
            timestamp=datetime.now(UTC),
        )

    def get_orderbook(self, instrument_id: str, depth: int = 10) -> OrderBook:
        self._require()
        pair = self._pair(instrument_id)
        payload = self.http.get_json(f"{BASE}/Depth", params={"pair": pair, "count": int(depth)})
        result = _result(payload)
        row = _first_row(result)
        bids = [
            Level(price=_f(level[0]), size=_f(level[1]))
            for level in row.get("bids", [])
            if isinstance(level, list) and len(level) >= 2
        ]
        asks = [
            Level(price=_f(level[0]), size=_f(level[1]))
            for level in row.get("asks", [])
            if isinstance(level, list) and len(level) >= 2
        ]
        return OrderBook(
            instrument_id=instrument_id,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(UTC),
        )

    def get_candles(
        self,
        instrument_id: str,
        granularity: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self._require()
        pair = self._pair(instrument_id)
        interval = INTERVALS.get(granularity, 60)
        payload = self.http.get_json(
            f"{BASE}/OHLC",
            params={"pair": pair, "interval": interval, "since": int(start.timestamp())},
        )
        result = _result(payload)
        rows: list[object] = []
        for key, value in result.items():
            if key != "last" and isinstance(value, list):
                rows = value
                break
        candles: list[Candle] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 7:
                continue
            stamp = datetime.fromtimestamp(int(float(row[0])), tz=UTC)
            if stamp < start or stamp > end:
                continue
            candles.append(
                Candle(
                    venue=self.venue,
                    instrument_id=instrument_id,
                    granularity=str(interval),
                    ts=stamp,
                    open=_f(row[1]),
                    high=_f(row[2]),
                    low=_f(row[3]),
                    close=_f(row[4]),
                    volume=_f(row[6]),
                )
            )
        candles.sort(key=lambda item: item.ts)
        return candles

    def get_settlement(self, instrument_id: str) -> Settlement | None:
        del instrument_id
        self._require()
        return None

    def fee_for(self, side: str, price: float, qty: float, maker: bool = False) -> float:
        del side
        rate = 0.004 if maker else KRAKEN_TAKER_FEE
        return rate * float(price) * float(qty)

    def health(self) -> AdapterHealth:
        if not self.enabled:
            status = "disabled"
        elif self.http.last_error:
            status = "error"
        elif self.http.last_success_at is None:
            status = "not_probed"
        else:
            status = "ok"
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


def _result(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    errors = payload.get("error")
    if isinstance(errors, list) and errors:
        raise AdapterError("kraken", "; ".join(str(item) for item in errors))
    result = payload.get("result")
    return result if isinstance(result, dict) else {}


def _first_row(result: dict[str, object]) -> dict[str, object]:
    for key, value in result.items():
        if key != "last" and isinstance(value, dict):
            return value
    return {}
