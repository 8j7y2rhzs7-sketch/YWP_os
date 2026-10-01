"""Public adapters normalize mocked HTTP. No live network."""

from datetime import UTC, datetime

import httpx

from app.services.markets.adapter import VenueDisabled
from app.services.markets.adapters.coinbase import CoinbaseAdapter
from app.services.markets.adapters.kalshi import KalshiAdapter, parse_market
from app.services.markets.adapters.kraken import KrakenAdapter


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_coinbase_normalizes_ticker_book_and_candles() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/ticker"):
            return httpx.Response(
                200,
                json={
                    "best_bid": "100.0",
                    "best_ask": "100.2",
                    "price": "100.1",
                    "time": "2026-10-01T18:00:00Z",
                },
            )
        if path.endswith("/candles"):
            return httpx.Response(
                200,
                json={
                    "candles": [
                        {
                            "start": "1760000000",
                            "open": "99",
                            "high": "101",
                            "low": "98",
                            "close": "100",
                            "volume": "12",
                        }
                    ]
                },
            )
        if "product_book" in path:
            return httpx.Response(
                200,
                json={
                    "pricebook": {
                        "bids": [{"price": "100", "size": "2"}],
                        "asks": [{"price": "100.2", "size": "3"}],
                        "time": "2026-10-01T18:00:01Z",
                    }
                },
            )
        return httpx.Response(404, json={"error": "missing"})

    adapter = CoinbaseAdapter(client=_client(handler), min_interval=0)
    quote = adapter.get_quote("BTC-USD")
    book = adapter.get_orderbook("BTC-USD")
    candles = adapter.get_candles(
        "BTC-USD",
        "ONE_HOUR",
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2026, 10, 2, tzinfo=UTC),
    )
    assert quote.last == 100.1
    assert quote.bid == 100.0
    assert book.asks[0].size == 3
    assert candles[0].close == 100
    assert candles[0].venue == "coinbase"
    assert adapter.get_settlement("BTC-USD") is None
    assert adapter.fee_for("buy", 100, 1) == 0.6
    adapter.close()


def test_coinbase_retries_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, json={"price": "10", "best_bid": "10", "best_ask": "10.1"})

    adapter = CoinbaseAdapter(client=_client(handler), min_interval=0)
    quote = adapter.get_quote("ETH-USD")
    assert quote.last == 10
    assert calls["n"] == 2
    adapter.close()


def test_disabled_coinbase_refuses() -> None:
    adapter = CoinbaseAdapter(enabled=False, min_interval=0)
    try:
        adapter.get_quote("BTC-USD")
        raised = False
    except VenueDisabled:
        raised = True
    assert raised
    assert adapter.health().status == "disabled"


def test_kraken_ohlc_and_ticker() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Ticker"):
            return httpx.Response(
                200,
                json={
                    "error": [],
                    "result": {
                        "XXBTZUSD": {
                            "c": ["64000.5", "0.1"],
                            "b": ["64000", "1", "1"],
                            "a": ["64010", "1", "1"],
                        }
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "error": [],
                "result": {
                    "XXBTZUSD": [
                        [1760000000, "100", "110", "90", "105", "102", "8", 4],
                        [1760003600, "105", "112", "104", "108", "107", "9", 5],
                    ],
                    "last": 1760003600,
                },
            },
        )

    adapter = KrakenAdapter(client=_client(handler), min_interval=0)
    quote = adapter.get_quote("BTC-USD")
    candles = adapter.get_candles(
        "BTC-USD",
        "ONE_HOUR",
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert quote.last == 64000.5
    assert len(candles) == 2
    assert candles[0].low == 90
    assert candles[1].close == 108
    adapter.close()


def test_kalshi_market_orderbook_and_settlement() -> None:
    market = {
        "ticker": "KXNFLGAME-25OCT-KC",
        "title": "Kansas City winner",
        "yes_sub_title": "Kansas City",
        "status": "open",
        "series_ticker": "KXNFLGAME",
        "yes_bid_dollars": "0.40",
        "yes_ask_dollars": "0.43",
        "no_bid_dollars": "0.57",
        "no_ask_dollars": "0.60",
        "rules_primary": "Includes overtime.",
        "result": "",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/series"):
            return httpx.Response(
                200, json={"series": [{"ticker": "KXNFLGAME", "category": "Sports"}]}
            )
        if path.endswith("/markets"):
            return httpx.Response(200, json={"markets": [market]})
        if path.endswith("/orderbook"):
            return httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [["0.40", "25"]],
                        "no_dollars": [["0.57", "30"]],
                    }
                },
            )
        if path.endswith("/KXNFLGAME-25OCT-KC-SETTLED"):
            settled = dict(market)
            settled["ticker"] = "KXNFLGAME-25OCT-KC-SETTLED"
            settled["status"] = "settled"
            settled["result"] = "yes"
            return httpx.Response(200, json={"market": settled})
        return httpx.Response(200, json={"market": market})

    adapter = KalshiAdapter(client=_client(handler), min_interval=0)
    instruments = adapter.list_instruments()
    assert instruments[0].sport == "nfl"
    assert instruments[0].extra["yes_ask"] == 0.43
    quote = adapter.get_quote("KXNFLGAME-25OCT-KC")
    book = adapter.get_orderbook("KXNFLGAME-25OCT-KC")
    assert quote.ask == 0.43
    assert book.bids[0].price == 0.40
    assert abs(book.asks[0].price - 0.43) < 1e-9
    assert adapter.get_settlement("KXNFLGAME-25OCT-KC") is None
    settled = adapter.get_settlement("KXNFLGAME-25OCT-KC-SETTLED")
    assert settled is not None and settled.result == "YES"
    parsed = parse_market({"ticker": "KXMLBGAME-1", "title": "Yankees winner", "status": "active"})
    assert parsed.sport == "mlb"
    adapter.close()
