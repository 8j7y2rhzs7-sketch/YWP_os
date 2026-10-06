"""Markets API auth, scan, grade, and a track record that stays off the sports tables."""

from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models_markets import (
    MarketCall,
    MarketCandle,
    MarketJobRun,
    MarketModelVersion,
    MarketOutcome,
)
from app.services.markets.adapters.coinbase import CoinbaseAdapter
from app.services.markets.adapters.kalshi import KalshiAdapter
from app.services.markets.adapters.kraken import KrakenAdapter
from app.services.markets.scheduler_jobs import freeze_model_version, run_grade, run_scan


def _promote_admin(email: str = "owner@ywp-os.com") -> None:
    from app.core.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.role = "admin"
        db.commit()
    finally:
        db.close()


def _coinbase_client(now: datetime) -> httpx.Client:
    candles = []
    price = 100.0
    for index in range(48):
        stamp = int((now - timedelta(hours=48 - index)).timestamp())
        candles.append(
            {
                "start": str(stamp),
                "open": f"{price:.2f}",
                "high": f"{price * 1.01:.2f}",
                "low": f"{price * 0.99:.2f}",
                "close": f"{price * 1.002:.2f}",
                "volume": "30",
            }
        )
        price *= 1.002

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/ticker"):
            return httpx.Response(
                200,
                json={
                    "best_bid": "100",
                    "best_ask": "100.1",
                    "price": "100.05",
                    "time": now.isoformat().replace("+00:00", "Z"),
                },
            )
        if path.endswith("/candles"):
            return httpx.Response(200, json={"candles": candles})
        if "product_book" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "pricebook": {
                        "bids": [{"price": "100", "size": "40"}],
                        "asks": [{"price": "100.1", "size": "40"}],
                        "time": now.isoformat().replace("+00:00", "Z"),
                    }
                },
            )
        return httpx.Response(404, json={})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _kraken_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "error": [],
                "result": {
                    "XXBTZUSD": {
                        "c": ["100.05", "1"],
                        "b": ["100", "1", "1"],
                        "a": ["100.1", "1", "1"],
                    }
                },
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _kalshi_client() -> httpx.Client:
    market = {
        "ticker": "KXNFLGAME-KC",
        "title": "Kansas City winner",
        "yes_sub_title": "Kansas City",
        "status": "open",
        "series_ticker": "KXNFLGAME",
        "yes_bid_dollars": "0.40",
        "yes_ask_dollars": "0.42",
        "no_bid_dollars": "0.58",
        "no_ask_dollars": "0.60",
        "rules_primary": "Includes overtime.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/series"):
            return httpx.Response(200, json={"series": [{"ticker": "KXNFLGAME"}]})
        if path.endswith("/markets"):
            return httpx.Response(200, json={"markets": [market]})
        if path.endswith("/orderbook"):
            return httpx.Response(
                200,
                json={
                    "orderbook_fp": {
                        "yes_dollars": [["0.40", "40"]],
                        "no_dollars": [["0.58", "40"]],
                    }
                },
            )
        return httpx.Response(200, json={"market": market})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_reads_require_login_and_scan_is_admin_only(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    assert client.get("/api/v1/markets/health").status_code == 401
    health = client.get("/api/v1/markets/health", headers=auth_headers)
    assert health.status_code == 200, health.text
    body = health.json()
    assert body["read_only"] is True
    assert body["orders_enabled"] is False
    assert body["version"] == "3.3.70"

    denied = client.post("/api/v1/markets/scan", headers=auth_headers)
    assert denied.status_code == 403

    monkeypatch.setattr(
        "app.api.markets.run_scan",
        lambda db, **kwargs: {
            "status": "ok",
            "crypto_calls": 1,
            "exchange_calls": 0,
            "errors": [],
            "read_only": True,
        },
    )
    _promote_admin()
    allowed = client.post("/api/v1/markets/scan", headers=auth_headers)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["read_only"] is True


def test_scan_token_and_disabled_switch(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(settings, "markets_scan_token", "scan-token-value")
    monkeypatch.setattr(
        "app.api.markets.run_grade",
        lambda db, **kwargs: {
            "status": "ok",
            "graded": 0,
            "pending": 0,
            "errors": [],
            "read_only": True,
        },
    )
    graded = client.post(
        "/api/v1/markets/grade", headers={"X-YWP-Markets-Token": "scan-token-value"}
    )
    assert graded.status_code == 200, graded.text
    wrong = client.post("/api/v1/markets/grade", headers={"X-YWP-Markets-Token": "nope"})
    assert wrong.status_code == 401

    monkeypatch.setattr(settings, "markets_enabled", False)
    monkeypatch.setattr("app.api.markets.run_scan", run_scan)
    _promote_admin()
    paused = client.post("/api/v1/markets/scan", headers=auth_headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "disabled"


def test_scan_persists_calls_and_board_is_readable(
    client: TestClient, auth_headers: dict[str, str], db_session
) -> None:
    now = datetime.now(UTC)
    coinbase = CoinbaseAdapter(client=_coinbase_client(now), min_interval=0)
    kraken = KrakenAdapter(client=_kraken_client(), min_interval=0)
    kalshi = KalshiAdapter(client=_kalshi_client(), min_interval=0)
    result = run_scan(
        db_session,
        coinbase=coinbase,
        kraken=kraken,
        kalshi=kalshi,
        now=now,
        n_paths=80,
        horizons=(4.0,),
    )
    assert result["crypto_calls"] == 3
    assert result["exchange_calls"] == 1
    versions = db_session.query(MarketModelVersion).all()
    assert {row.version for row in versions} >= {
        "ywp-markets-crypto-v1.0.0",
        "ywp-markets-kalshi-v1.0.0",
    }
    again = freeze_model_version(
        db_session,
        kind="crypto",
        version="ywp-markets-crypto-v1.0.0",
        parameters={"again": True},
    )
    assert again.parameters.get("ewma_lambda") == 0.94

    board = client.get("/api/v1/markets/calls?venue=crypto", headers=auth_headers)
    assert board.status_code == 200, board.text
    calls = board.json()["calls"]
    assert len(calls) == 3
    assert calls[0]["read_only"] is True
    assert calls[0]["verdict"] in {"PLAY", "LEAN", "WATCH", "REVIEW", "WAIT", "SKIP"}
    detail = client.get(f"/api/v1/markets/calls/{calls[0]['id']}", headers=auth_headers)
    assert detail.status_code == 200
    exchange = client.get("/api/v1/markets/calls?venue=sports-exchange", headers=auth_headers)
    assert exchange.status_code == 200
    kalshi_call = exchange.json()["calls"][0]
    assert kalshi_call["model_probability"] is None
    assert kalshi_call["verdict"] == "SKIP"
    assert "NO_INDEPENDENT_PROBABILITY" in kalshi_call["reason_codes"]
    record = client.get("/api/v1/markets/performance?venue=crypto", headers=auth_headers)
    assert record.status_code == 200
    assert record.json()["separate_from_sports"] is True
    assert record.json()["n_calls"] == 3


def test_opening_the_board_reads_prices_once(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    reads: list[int] = []

    def fake_scan(db, **kwargs):
        reads.append(int(kwargs.get("n_paths") or 0))
        now = datetime.now(UTC)
        db.add(
            MarketJobRun(
                job_name="scan",
                started_at=now,
                finished_at=now,
                status="ok",
                items_processed=0,
                error_count=0,
                errors=[],
            )
        )
        db.commit()
        return {
            "status": "ok",
            "crypto_calls": 0,
            "exchange_calls": 0,
            "errors": [],
            "read_only": True,
        }

    monkeypatch.setattr("app.services.markets.scheduler_jobs.run_scan", fake_scan)
    first = client.get("/api/v1/markets/calls?venue=crypto", headers=auth_headers)
    assert first.status_code == 200, first.text
    second = client.get("/api/v1/markets/calls?venue=crypto", headers=auth_headers)
    assert second.status_code == 200, second.text
    assert reads == [800]


def test_a_fresh_read_is_not_repeated(
    client: TestClient, auth_headers: dict[str, str], db_session, monkeypatch
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        MarketJobRun(
            job_name="scan",
            started_at=now,
            finished_at=now,
            status="ok",
            items_processed=1,
            error_count=0,
            errors=[],
        )
    )
    db_session.commit()

    def fail_scan(db, **kwargs):
        del db, kwargs
        raise AssertionError("a fresh board must not read prices again")

    monkeypatch.setattr("app.services.markets.scheduler_jobs.run_scan", fail_scan)
    board = client.get("/api/v1/markets/calls?venue=crypto", headers=auth_headers)
    assert board.status_code == 200, board.text


def test_grade_crypto_from_stored_candles(db_session) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    call = MarketCall(
        venue="coinbase",
        venue_group="crypto",
        instrument_id="SOL-USD",
        call_type="crypto_bracket",
        title="SOL 4h",
        selection="Target before stop",
        entry=100,
        target=110,
        stop=95,
        horizon_hours=4,
        horizon_end=start + timedelta(hours=4),
        market_price=0.4,
        fair_price=0.42,
        model_probability=0.55,
        lower_90=0.5,
        edge=0.13,
        expected_value=0.08,
        confidence=88,
        verdict="PLAY",
        tier="edge_play",
        edge_class="Strong",
        stake_pct=0.01,
        reason_codes=[],
        reasons=[],
        warnings=[],
        model_version="ywp-markets-crypto-v1.0.0",
        idempotency_key="grade-test-sol",
        payload={"read_only": True},
        created_at=start,
    )
    db_session.add(call)
    db_session.flush()
    db_session.add(
        MarketCandle(
            venue="coinbase",
            instrument_id="SOL-USD",
            granularity="ONE_HOUR",
            ts=start + timedelta(hours=1),
            open=100,
            high=112,
            low=99,
            close=110,
            volume=10,
        )
    )
    db_session.commit()
    coinbase = CoinbaseAdapter(enabled=False, min_interval=0)
    kalshi = KalshiAdapter(enabled=False, min_interval=0)
    result = run_grade(db_session, coinbase=coinbase, kalshi=kalshi, now=start + timedelta(hours=5))
    assert result["graded"] == 1
    outcome = db_session.query(MarketOutcome).one()
    assert outcome.outcome == "TARGET"
    assert outcome.grading_method == "coinbase_candle_replay"
    assert outcome.won is True
    again = run_grade(db_session, coinbase=coinbase, kalshi=kalshi, now=start + timedelta(hours=6))
    assert again["graded"] == 0
    assert db_session.query(MarketOutcome).count() == 1


def test_phase1_has_no_order_code() -> None:
    from pathlib import Path

    root = Path("app/services/markets")
    text = "\n".join(path.read_text() for path in root.rglob("*.py"))
    assert "def place_order" not in text
    assert "def cancel_order" not in text
    assert "api_key" not in text.lower()
    assert "Authorization" not in text
