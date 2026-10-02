"""Bracket math, Kalshi mapping, and grading. No network."""

from datetime import UTC, datetime, timedelta

from app.services.markets.adapter import Candle, Instrument, Level, OrderBook, Quote
from app.services.markets.crypto_model import bracket_is_sane, forecast_bracket, suggest_bracket
from app.services.markets.exchange_mapping import (
    SportsModelQuote,
    price_gap_cannot_authorize_play,
    select_independent_probability,
)
from app.services.markets.grading import grade_crypto_candles, grade_kalshi_result
from app.services.markets.markets_engine import build_crypto_call, build_exchange_call


def _candles(n: int = 60, start: float = 100.0) -> list[Candle]:
    rows: list[Candle] = []
    price = start
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(n):
        drift = 0.002 * ((index % 5) - 2)
        opened = price
        closed = price * (1 + drift)
        rows.append(
            Candle(
                venue="coinbase",
                instrument_id="BTC-USD",
                granularity="ONE_HOUR",
                ts=base + timedelta(hours=index),
                open=opened,
                high=max(opened, closed) * 1.002,
                low=min(opened, closed) * 0.998,
                close=closed,
                volume=20 + index,
            )
        )
        price = closed
    return rows


def _book(entry: float) -> OrderBook:
    return OrderBook(
        instrument_id="BTC-USD",
        bids=[Level(price=entry * 0.999, size=40)],
        asks=[Level(price=entry * 1.001, size=40)],
        timestamp=datetime(2026, 1, 3, tzinfo=UTC),
    )


def test_forecast_probabilities_sum_and_respect_distance() -> None:
    candles = _candles()
    entry = candles[-1].close
    vol = 0.01
    target, stop = suggest_bracket(entry, vol, 4)
    assert bracket_is_sane(entry, target, stop, vol, 4)
    near = forecast_bracket(
        candles,
        entry=entry,
        target=entry * 1.01,
        stop=entry * 0.8,
        horizon_hours=8,
        n_paths=400,
        seed=3,
    )
    far = forecast_bracket(
        candles,
        entry=entry,
        target=entry * 1.2,
        stop=entry * 0.8,
        horizon_hours=8,
        n_paths=400,
        seed=3,
    )
    assert near is not None and far is not None
    assert abs(near.p_target + near.p_stop + near.p_timeout - 1) < 1e-9
    assert near.lower_90 <= near.p_target
    assert near.p_target > far.p_target


def test_insane_bracket_is_rejected() -> None:
    target, stop = suggest_bracket(100, 0.01, 4)
    assert bracket_is_sane(100, target, stop, 0.01, 4)
    assert not bracket_is_sane(100, 180, 20, 0.01, 4)


def test_market_price_is_not_the_model_and_gap_cannot_play() -> None:
    only_price = [
        SportsModelQuote(model_probability=0.8, sportsbook_implied=0.4, source="market_implied")
    ]
    assert select_independent_probability(only_price) is None
    kept = select_independent_probability(
        only_price
        + [
            SportsModelQuote(
                model_probability=0.57,
                sportsbook_implied=0.5,
                source="model",
                recommendation_id="r1",
            )
        ]
    )
    assert kept is not None and kept.model_probability == 0.57
    assert price_gap_cannot_authorize_play("PLAY", has_independent_model=False) == "SKIP"
    assert price_gap_cannot_authorize_play("PLAY", has_independent_model=True) == "PLAY"

    now = datetime(2026, 10, 1, 18, tzinfo=UTC)
    instrument = Instrument(
        venue="kalshi",
        instrument_id="KXNFLGAME-KC",
        kind="event_contract",
        symbol="KXNFLGAME-KC",
        title="Kansas City winner",
        sport="nfl",
        league="KXNFLGAME",
        rules_text="Includes overtime.",
        extra={
            "yes_sub_title": "Kansas City",
            "status": "open",
            "no_ask": 0.60,
            "series_ticker": "KXNFLGAME",
            "can_close_early": False,
        },
    )
    quote = Quote(
        instrument_id=instrument.instrument_id,
        bid=0.40,
        ask=0.42,
        last=0.41,
        ask_size=100,
        timestamp=now,
    )
    blocked = build_exchange_call(
        instrument=instrument,
        quote=quote,
        book=None,
        model_probability=0.9,
        probability_source="market_implied",
        sportsbook_implied=0.55,
        now=now,
    )
    assert blocked.model_probability is None
    assert blocked.verdict == "SKIP"
    assert "NO_INDEPENDENT_PROBABILITY" in blocked.reason_codes
    assert blocked.market_price is not None and blocked.market_price > 0.42
    assert blocked.price_gap is not None
    assert "PRICE_GAP" in blocked.reason_codes

    playable = build_exchange_call(
        instrument=instrument,
        quote=quote,
        book=None,
        model_probability=0.72,
        probability_source="model",
        sportsbook_implied=0.55,
        recommendation_id="rec-1",
        now=now,
    )
    assert playable.model_probability == 0.72
    assert playable.model_probability != playable.market_price
    assert playable.verdict == "PLAY"
    assert playable.edge is not None and playable.edge > 0
    assert "PRICE_GAP" in playable.reason_codes
    assert playable.payload["fees_included"] is True


def test_crypto_call_uses_model_not_break_even_as_probability() -> None:
    candles = _candles()
    when = candles[-1].ts
    entry = candles[-1].close
    draft = build_crypto_call(
        symbol="BTC-USD",
        candles=candles,
        quote=Quote(
            instrument_id="BTC-USD",
            bid=entry * 0.999,
            ask=entry * 1.001,
            last=entry,
            ask_size=40,
            timestamp=when,
        ),
        book=_book(entry),
        cross_price=entry,
        now=when,
        horizon_hours=4,
        n_paths=300,
        seed=4,
    )
    assert draft.model_probability is not None
    assert draft.fair_price is not None
    assert draft.model_probability != draft.fair_price
    assert draft.payload["fees_included"] is True
    assert draft.venue_group == "crypto"


def test_crypto_wait_when_kraken_is_missing_but_edge_exists(monkeypatch) -> None:
    candles = _candles()
    when = candles[-1].ts
    entry = candles[-1].close

    def forced(*args, **kwargs):
        from app.services.markets.crypto_model import BracketForecast

        del args, kwargs
        return BracketForecast(
            p_target=0.7,
            p_stop=0.2,
            p_timeout=0.1,
            lower_90=0.6,
            hourly_vol=0.01,
            drift_per_bar=0.0,
            timeout_price=entry,
            bars_used=len(candles),
            paths=10,
        )

    monkeypatch.setattr("app.services.markets.markets_engine.forecast_bracket", forced)
    monkeypatch.setattr(
        "app.services.markets.markets_engine.suggest_bracket",
        lambda entry, vol, horizon: (entry * 1.05, entry * 0.97),
    )
    monkeypatch.setattr(
        "app.services.markets.markets_engine.bracket_is_sane",
        lambda *args, **kwargs: True,
    )
    draft = build_crypto_call(
        symbol="ETH-USD",
        candles=candles,
        quote=Quote(
            instrument_id="ETH-USD",
            bid=entry,
            ask=entry * 1.001,
            last=entry,
            ask_size=40,
            timestamp=when,
        ),
        book=_book(entry),
        cross_price=None,
        now=when,
        horizon_hours=4,
        n_paths=10,
        seed=1,
    )
    assert draft.verdict == "WAIT"
    assert "SOURCE_UNCONFIRMED" in draft.reason_codes


def test_grading_stop_first_and_same_candle_and_kalshi() -> None:
    start = datetime(2026, 1, 2, tzinfo=UTC)
    later = start + timedelta(hours=1)
    stop_first = [
        Candle("coinbase", "BTC-USD", "ONE_HOUR", start, 100, 101, 90, 95, 1),
        Candle("coinbase", "BTC-USD", "ONE_HOUR", later, 95, 120, 94, 110, 1),
    ]
    outcome, _ = grade_crypto_candles(
        stop_first,
        start=start,
        horizon_end=start + timedelta(hours=4),
        target=110,
        stop=92,
        now=start + timedelta(hours=5),
    )
    assert outcome == "STOP"
    both = [Candle("coinbase", "BTC-USD", "ONE_HOUR", start, 100, 120, 80, 100, 1)]
    outcome, _ = grade_crypto_candles(
        both,
        start=start,
        horizon_end=start + timedelta(hours=2),
        target=110,
        stop=90,
        now=start + timedelta(hours=3),
    )
    assert outcome == "STOP"
    target_only = [Candle("coinbase", "BTC-USD", "ONE_HOUR", start, 100, 112, 99, 110, 1)]
    outcome, _ = grade_crypto_candles(
        target_only,
        start=start,
        horizon_end=start + timedelta(hours=2),
        target=110,
        stop=90,
        now=start + timedelta(hours=3),
    )
    assert outcome == "TARGET"
    pending, _ = grade_crypto_candles(
        target_only,
        start=start,
        horizon_end=start + timedelta(hours=5),
        target=150,
        stop=50,
        now=start + timedelta(hours=1),
    )
    assert pending is None
    assert grade_kalshi_result("yes") == "YES"
    assert grade_kalshi_result("void") == "VOID"
    assert grade_kalshi_result(None) is None
