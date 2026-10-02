"""Kalshi public market data. No key, no signed requests, no orders.

Base: https://external-api.kalshi.com/trade-api/v2
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

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
from app.services.markets.pricing import kalshi_coefficient, kalshi_taker_fee

BASE = "https://external-api.kalshi.com/trade-api/v2"

SPORT_PREFIXES = (
    ("KXNFL", "nfl"),
    ("KXNCAAF", "ncaaf"),
    ("KXNBA", "nba"),
    ("KXNCAAB", "ncaab"),
    ("KXWNBA", "wnba"),
    ("KXMLB", "mlb"),
    ("KXNHL", "nhl"),
    ("KXMLS", "soccer"),
    ("KXEPL", "soccer"),
    ("Kxucl", "soccer"),
)


def _f(value: object, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _price_dollars(market: dict[str, object], *keys: str) -> float | None:
    """Prefer fixed-point dollar fields, then legacy cent fields."""
    for key in keys:
        if key.endswith("_dollars") or "dollar" in key:
            value = _f(market.get(key))
            if value is not None:
                return value
        else:
            cents = _f(market.get(key))
            if cents is not None:
                # Legacy fields are cents (47) or already dollars (0.47).
                return cents / 100.0 if cents > 1.5 else cents
    return None


def sport_from_ticker(ticker: str) -> str | None:
    upper = ticker.upper()
    for prefix, sport in SPORT_PREFIXES:
        if upper.startswith(prefix.upper()):
            return sport
    return None


def parse_market(market: dict[str, object]) -> Instrument:
    ticker = str(market.get("ticker") or "")
    title = str(market.get("title") or market.get("yes_sub_title") or ticker)
    rules = str(market.get("rules_primary") or market.get("rules_secondary") or "")
    sport = sport_from_ticker(ticker) or sport_from_ticker(str(market.get("event_ticker") or ""))
    status = str(market.get("status") or "")
    return Instrument(
        venue="kalshi",
        instrument_id=ticker,
        kind="event_contract",
        symbol=ticker,
        title=title,
        sport=sport,
        league=str(market.get("series_ticker") or "") or None,
        rules_text=rules,
        active=status.lower() in {"open", "active", ""},
        extra={
            "yes_sub_title": market.get("yes_sub_title"),
            "no_sub_title": market.get("no_sub_title"),
            "event_ticker": market.get("event_ticker"),
            "series_ticker": market.get("series_ticker"),
            "status": status,
            "result": market.get("result"),
            "can_close_early": bool(
                market.get("can_close_early") or market.get("early_close_condition")
            ),
            "close_time": market.get("close_time"),
            "yes_bid": _price_dollars(market, "yes_bid_dollars", "yes_bid"),
            "yes_ask": _price_dollars(market, "yes_ask_dollars", "yes_ask"),
            "no_bid": _price_dollars(market, "no_bid_dollars", "no_bid"),
            "no_ask": _price_dollars(market, "no_ask_dollars", "no_ask"),
            "volume": _f(market.get("volume_fp") or market.get("volume")),
        },
    )


class KalshiAdapter:
    venue = "kalshi"
    kind = "event_contract"

    def __init__(
        self,
        *,
        enabled: bool = True,
        client: httpx.Client | None = None,
        min_interval: float = 0.08,
        base_url: str = BASE,
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.http = PublicHttp(self.venue, client=client, min_interval=min_interval)

    def close(self) -> None:
        self.http.close()

    def _require(self) -> None:
        if not self.enabled:
            raise VenueDisabled(self.venue, "Kalshi is switched off")

    def list_instruments(self, *, category: str | None = "Sports") -> list[Instrument]:
        self._require()
        series_payload = self.http.get_json(
            f"{self.base_url}/series",
            params={"category": category} if category else None,
        )
        series_rows = series_payload.get("series") if isinstance(series_payload, dict) else []
        if not isinstance(series_rows, list):
            series_rows = []
        game_series = []
        for row in series_rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "")
            if "GAME" in ticker.upper() or sport_from_ticker(ticker):
                game_series.append(ticker)
        if not game_series:
            game_series = [
                str(row.get("ticker"))
                for row in series_rows
                if isinstance(row, dict) and row.get("ticker")
            ][:4]
        instruments: list[Instrument] = []
        for series_ticker in game_series[:4]:
            payload = self.http.get_json(
                f"{self.base_url}/markets",
                params={"series_ticker": series_ticker, "status": "open", "limit": 8},
            )
            markets = payload.get("markets") if isinstance(payload, dict) else []
            if not isinstance(markets, list):
                continue
            for market in markets:
                if isinstance(market, dict):
                    market.setdefault("series_ticker", series_ticker)
                    instruments.append(parse_market(market))
            if len(instruments) >= 12:
                break
        return instruments[:12]

    def get_market(self, instrument_id: str) -> dict[str, object]:
        self._require()
        payload = self.http.get_json(f"{self.base_url}/markets/{instrument_id}")
        if isinstance(payload, dict) and isinstance(payload.get("market"), dict):
            return payload["market"]
        if isinstance(payload, dict):
            return payload
        raise AdapterError(self.venue, "Kalshi market payload was empty")

    def get_quote(self, instrument_id: str) -> Quote:
        market = self.get_market(instrument_id)
        instrument = parse_market(market)
        extra = instrument.extra
        yes_bid = extra.get("yes_bid") if isinstance(extra.get("yes_bid"), float) else None
        yes_ask = extra.get("yes_ask") if isinstance(extra.get("yes_ask"), float) else None
        no_bid = extra.get("no_bid") if isinstance(extra.get("no_bid"), float) else None
        if yes_ask is None and isinstance(no_bid, float):
            yes_ask = max(0.0, 1.0 - no_bid)
        if yes_bid is None and isinstance(extra.get("no_ask"), float):
            yes_bid = max(0.0, 1.0 - float(extra["no_ask"]))
        last = _f(market.get("last_price_dollars"))
        if last is None:
            cents = _f(market.get("last_price"))
            last = None if cents is None else (cents / 100.0 if cents > 1.5 else cents)
        return Quote(
            instrument_id=instrument_id,
            bid=yes_bid,
            ask=yes_ask,
            last=last,
            timestamp=_ts(market.get("updated_time") or market.get("close_time"))
            or datetime.now(UTC),
        )

    def get_orderbook(self, instrument_id: str, depth: int = 10) -> OrderBook:
        self._require()
        payload = self.http.get_json(f"{self.base_url}/markets/{instrument_id}/orderbook")
        body = payload if isinstance(payload, dict) else {}
        book = body.get("orderbook_fp") if isinstance(body.get("orderbook_fp"), dict) else None
        if book is None and isinstance(body.get("orderbook"), dict):
            book = body["orderbook"]
        book = book or {}
        dollar_book = "yes_dollars" in book or "no_dollars" in book
        yes_levels = _book_side(book.get("yes_dollars") or book.get("yes"), dollars=dollar_book)
        no_levels = _book_side(book.get("no_dollars") or book.get("no"), dollars=dollar_book)
        # Kalshi books are bids. The YES ask is one dollar minus the best NO bid.
        asks = [
            Level(price=max(0.0, 1.0 - level.price), size=level.size)
            for level in no_levels
            if level.price < 1
        ]
        asks.sort(key=lambda level: level.price)
        yes_levels.sort(key=lambda level: level.price, reverse=True)
        return OrderBook(
            instrument_id=instrument_id,
            bids=yes_levels[:depth],
            asks=asks[:depth],
            timestamp=datetime.now(UTC),
        )

    def get_candles(
        self,
        instrument_id: str,
        granularity: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        del granularity
        self._require()
        payload = self.http.get_json(
            f"{self.base_url}/markets/{instrument_id}/candlesticks",
            params={
                "start_ts": int(start.timestamp()),
                "end_ts": int(end.timestamp()),
                "period_interval": 60,
            },
        )
        rows = []
        if isinstance(payload, dict):
            raw = payload.get("candlesticks") or payload.get("candles") or []
            if isinstance(raw, list):
                rows = raw
        candles: list[Candle] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_ts = row.get("end_period_ts")
            if isinstance(raw_ts, (int, float)):
                stamp = datetime.fromtimestamp(int(raw_ts), tz=UTC)
            else:
                stamp = _ts(raw_ts)
            price = row.get("price") if isinstance(row.get("price"), dict) else row
            if stamp is None or not isinstance(price, dict):
                continue
            candles.append(
                Candle(
                    venue=self.venue,
                    instrument_id=instrument_id,
                    granularity="60",
                    ts=stamp,
                    open=_f(price.get("open_dollars") or price.get("open")) or 0.0,
                    high=_f(price.get("high_dollars") or price.get("high")) or 0.0,
                    low=_f(price.get("low_dollars") or price.get("low")) or 0.0,
                    close=_f(price.get("close_dollars") or price.get("close")) or 0.0,
                    volume=_f(row.get("volume_fp") or row.get("volume")) or 0.0,
                )
            )
        return candles

    def get_settlement(self, instrument_id: str) -> Settlement | None:
        market = self.get_market(instrument_id)
        result = str(market.get("result") or market.get("settlement_value") or "").lower()
        status = str(market.get("status") or "").lower()
        if result in {"yes", "no"}:
            return Settlement(
                instrument_id=instrument_id,
                result=result.upper(),
                settled_at=_ts(market.get("settlement_ts") or market.get("close_time")),
            )
        if result in {"void", "scalar"} or status in {"voided", "void"}:
            return Settlement(
                instrument_id=instrument_id, result="VOID", settled_at=_ts(market.get("close_time"))
            )
        if status in {"finalized", "settled", "determined"} and result in {"", "all"}:
            return None
        return None

    def fee_for(self, side: str, price: float, qty: float, maker: bool = False) -> float:
        del side
        # Phase 1 always prices the taker fee. Maker fills are a Phase 2 concern.
        del maker
        return kalshi_taker_fee(qty, price, coefficient=kalshi_coefficient())

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


def _book_side(raw: object, *, dollars: bool) -> list[Level]:
    if not isinstance(raw, list):
        return []
    levels: list[Level] = []
    for item in raw:
        if isinstance(item, list) and len(item) >= 2:
            price = _f(item[0])
            size = _f(item[1])
        elif isinstance(item, dict):
            price = _f(item.get("price") or item.get("price_dollars"))
            size = _f(item.get("size") or item.get("count") or item.get("quantity"))
        else:
            continue
        if price is None or size is None:
            continue
        if not dollars and price > 1.5:
            price = price / 100.0
        levels.append(Level(price=price, size=size))
    return levels
