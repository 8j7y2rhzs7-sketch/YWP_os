"""Build a market call and grade it with the shared sports verdict ladder.

Edge and EV passed to the ladder already have fees subtracted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.core.verdict import assign_verdict, quarter_kelly_stake
from app.services.markets import (
    COINBASE_TAKER_FEE,
    CRYPTO_MODEL_VERSION,
    CRYPTO_WHITELIST,
    EXCHANGE_MODEL_VERSION,
)
from app.services.markets.adapter import Candle, Instrument, OrderBook, Quote
from app.services.markets.crypto_model import (
    BracketForecast,
    bracket_is_sane,
    forecast_bracket,
    suggest_bracket,
)
from app.services.markets.exchange_mapping import (
    classify_contract,
    price_gap_cannot_authorize_play,
    price_gap_signal,
    rules_need_review,
    team_name,
)
from app.services.markets.gates import (
    GateResult,
    book_depth_ok,
    contract_spread_ok,
    macro_event_inside,
    price_is_fresh,
    prices_agree,
    volume_is_thin,
)
from app.services.markets.pricing import (
    cost_to_american,
    crypto_break_even,
    crypto_expected_value,
    fee_adjusted_break_even,
    fee_adjusted_contract_cost,
    kalshi_coefficient,
    reward_risk_american,
)
from app.services.pipeline.market_math import compare_to_market

REASON_TEXT = {
    "NO_CLEAN_EDGE": "After fees, the price does not leave a clean edge.",
    "ODDS_TOO_EXPENSIVE": "The cost is too high for the model's chance of being right.",
    "NO_INDEPENDENT_PROBABILITY": (
        "No independent model probability is on file. The market price is not used as the model."
    ),
    "PRICE_GAP": (
        "The sportsbook and Kalshi disagree. That gap is noted and cannot create a PLAY by itself."
    ),
    "NO_PICK_YET": "Evidence is incomplete, so this is not an official play.",
    "CONFIDENCE_BELOW_THRESHOLD": "Confidence is below the watch line.",
    "STALE_PRICE": "The price is older than 60 seconds.",
    "SOURCE_DISAGREEMENT": "Coinbase and Kraken disagree by more than 0.3 percent.",
    "SOURCE_UNCONFIRMED": "A second price source did not confirm this quote.",
    "BOOK_UNAVAILABLE": "The order book was not available.",
    "THIN_BOOK": "The book is too thin within 0.5 percent of the mid price.",
    "THIN_VOLUME": "Recent volume is far below its 20-bar average.",
    "THIN_LIQUIDITY": "The contract spread is wider than 4 cents or the ask is too small.",
    "BRACKET_INVALID": "The stop or target is outside the noise band.",
    "PAIR_NOT_WHITELISTED": "This pair is not on the spot whitelist (BTC, ETH, SOL).",
    "SPOT_ONLY": "Markets mode is spot only. Leveraged products are skipped.",
    "INSUFFICIENT_HISTORY": "There are not enough candles to estimate volatility.",
    "MACRO_EVENT": "A scheduled macro event falls inside the horizon.",
    "VENUE_DISABLED": "This venue is switched off.",
    "MARKET_NOT_OPEN": "The contract is not open.",
    "CAN_CLOSE_EARLY": "The contract can close early, so it needs a review.",
    "CONTRACT_RULES_UNMATCHED": "The contract rules do not match the model question.",
    "CONTRACT_IDENTITY_UNCLEAR": "The team on the contract is not clear.",
    "DATA_QUALITY_BAD": "The inputs are too thin to trust.",
}


@dataclass
class MarketDraft:
    venue: str
    venue_group: str
    instrument_id: str
    call_type: str
    title: str
    selection: str
    entry: float | None
    target: float | None
    stop: float | None
    horizon_hours: float | None
    horizon_end: datetime | None
    market_price: float | None
    fair_price: float | None
    model_probability: float | None
    lower_90: float | None
    edge: float | None
    expected_value: float | None
    confidence: int
    verdict: str
    tier: str
    edge_class: str
    stake_pct: float
    reason_codes: list[str]
    reasons: list[str]
    warnings: list[str]
    price_gap: dict[str, object] | None
    model_version: str
    idempotency_key: str
    payload: dict[str, object]


def explain(codes: list[str]) -> list[str]:
    return [REASON_TEXT.get(code, code.replace("_", " ").lower()) for code in dict.fromkeys(codes)]


def _idempotency(parts: dict[str, object]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _confidence(quality: float, edge: float | None) -> int:
    strength = 0.0 if edge is None else max(0.0, min(edge / 0.08, 1.0))
    return int(round(68 + 19 * max(0.0, min(quality, 1.0)) + 15 * strength))


def build_crypto_call(
    *,
    symbol: str,
    candles: list[Candle],
    quote: Quote | None,
    book: OrderBook | None,
    cross_price: float | None,
    now: datetime | None = None,
    horizon_hours: float = 4.0,
    macro_events: list[datetime] | None = None,
    n_paths: int = 1500,
    seed: int = 7,
    taker_fee: float = COINBASE_TAKER_FEE,
) -> MarketDraft:
    now = now or datetime.now(UTC)
    gates = GateResult()
    symbol = symbol.upper()
    if symbol not in CRYPTO_WHITELIST:
        gates.add_hard("PAIR_NOT_WHITELISTED", REASON_TEXT["PAIR_NOT_WHITELISTED"])
    if "PERP" in symbol or symbol.endswith("-PERP"):
        gates.add_hard("SPOT_ONLY", REASON_TEXT["SPOT_ONLY"])

    entry = _entry_price(quote, candles)
    fresh_time = quote.timestamp if quote and quote.timestamp else now
    if quote is None or entry is None:
        gates.add_hard("STALE_PRICE", "No fresh Coinbase price was available.", wait=False)
        entry = entry or 0.0
    elif not price_is_fresh(fresh_time, now):
        gates.add_hard("STALE_PRICE", REASON_TEXT["STALE_PRICE"])

    if cross_price is None:
        gates.add_hard("SOURCE_UNCONFIRMED", REASON_TEXT["SOURCE_UNCONFIRMED"], wait=True)
    elif entry and not prices_agree(entry, cross_price):
        gates.add_hard("SOURCE_DISAGREEMENT", REASON_TEXT["SOURCE_DISAGREEMENT"])

    book_code = book_depth_ok(book, entry or 0.0)
    if book_code == "BOOK_UNAVAILABLE":
        gates.add_hard("BOOK_UNAVAILABLE", REASON_TEXT["BOOK_UNAVAILABLE"], wait=True)
    elif book_code == "THIN_BOOK":
        gates.add_hard("THIN_BOOK", REASON_TEXT["THIN_BOOK"])

    volumes = [row.volume for row in candles]
    if volume_is_thin(volumes):
        gates.add_hard("THIN_VOLUME", REASON_TEXT["THIN_VOLUME"])
    if macro_event_inside(now, horizon_hours, macro_events):
        gates.add_hard("MACRO_EVENT", REASON_TEXT["MACRO_EVENT"])
    elif not macro_events:
        gates.warnings.append(
            "No macro calendar is loaded. CPI and FOMC are not blocking calls in this version."
        )

    forecast: BracketForecast | None = None
    target: float | None = None
    stop: float | None = None
    if entry and len(candles) >= 40:
        hourly_seed = _hourly_vol_guess(candles)
        target, stop = suggest_bracket(entry, hourly_seed, horizon_hours)
        if not bracket_is_sane(entry, target, stop, hourly_seed, horizon_hours):
            gates.add_hard("BRACKET_INVALID", REASON_TEXT["BRACKET_INVALID"])
        forecast = forecast_bracket(
            candles,
            entry=entry,
            target=target,
            stop=stop,
            horizon_hours=horizon_hours,
            n_paths=n_paths,
            seed=seed,
        )
    else:
        gates.add_hard("INSUFFICIENT_HISTORY", REASON_TEXT["INSUFFICIENT_HISTORY"], wait=True)

    model_p = forecast.p_target if forecast else None
    lower_90 = forecast.lower_90 if forecast else None
    raw_be = crypto_break_even(entry, target, stop) if entry and target and stop else None
    fair = (
        fee_adjusted_break_even(entry, target, stop, taker_fee=taker_fee)
        if entry and target and stop
        else None
    )
    timeout_price = forecast.timeout_price if forecast else entry
    ev = None
    edge = None
    if forecast and fair is not None and entry and target and stop and timeout_price is not None:
        edge = model_p - fair if model_p is not None else None
        ev = crypto_expected_value(
            p_target=forecast.p_target,
            p_stop=forecast.p_stop,
            p_timeout=forecast.p_timeout,
            entry=entry,
            target=target,
            stop=stop,
            timeout_price=timeout_price,
            taker_fee=taker_fee,
        )
    quality = 0.82
    if "SOURCE_UNCONFIRMED" in gates.reason_codes or "SOURCE_DISAGREEMENT" in gates.reason_codes:
        quality -= 0.2
    if "THIN_BOOK" in gates.reason_codes or "BOOK_UNAVAILABLE" in gates.reason_codes:
        quality -= 0.1
    confidence = _confidence(quality, edge)
    verdict = assign_verdict(
        edge=edge if edge is not None else -1.0,
        expected_value=ev if ev is not None else -1.0,
        confidence=confidence,
        reasons=gates.reason_codes,
        hard_skip_reasons=gates.hard_skip_reasons,
        review_reasons=gates.review_reasons,
        wait_codes=gates.wait_codes,
        variance=min(0.9, (forecast.hourly_vol * 10) if forecast else 0.5),
        quality=quality,
        american_odds=reward_risk_american(entry, target, stop, taker_fee=taker_fee)
        if entry and target and stop
        else -110,
    )
    kelly = None
    stake = verdict.suggested_stake_pct
    if forecast and entry and target and stop and model_p is not None:
        american = reward_risk_american(entry, target, stop, taker_fee=taker_fee)
        kelly = quarter_kelly_stake(model_p, american, lower_90=lower_90)
        kelly_stake = float(kelly.get("recommended_stake_pct") or 0.0)
        if verdict.decision in {"SKIP", "WAIT", "REVIEW"}:
            stake = 0.0
        else:
            stake = round(min(verdict.suggested_stake_pct, kelly_stake), 6)
    bucket = now.strftime("%Y%m%d%H")
    key = _idempotency(
        {
            "venue": "coinbase",
            "symbol": symbol,
            "horizon": horizon_hours,
            "bucket": bucket,
            "version": CRYPTO_MODEL_VERSION,
            "target": None if target is None else round(target, 2),
            "stop": None if stop is None else round(stop, 2),
        }
    )
    reasons = explain(verdict.reason_codes)
    return MarketDraft(
        venue="coinbase",
        venue_group="crypto",
        instrument_id=symbol,
        call_type="crypto_bracket",
        title=f"{symbol} {int(horizon_hours)}h bracket",
        selection=f"Target before stop within {int(horizon_hours)}h",
        entry=entry,
        target=target,
        stop=stop,
        horizon_hours=horizon_hours,
        horizon_end=now + timedelta(hours=horizon_hours),
        market_price=fair,
        fair_price=fair,
        model_probability=model_p,
        lower_90=lower_90,
        edge=edge,
        expected_value=ev,
        confidence=verdict.confidence,
        verdict=verdict.decision,
        tier=verdict.tier,
        edge_class=verdict.edge_class,
        stake_pct=stake,
        reason_codes=verdict.reason_codes,
        reasons=reasons,
        warnings=list(dict.fromkeys(verdict.warnings + gates.warnings)),
        price_gap=None,
        model_version=CRYPTO_MODEL_VERSION,
        idempotency_key=key,
        payload={
            "read_only": True,
            "fees_included": True,
            "taker_fee": taker_fee,
            "raw_break_even": raw_be,
            "fee_adjusted_break_even": fair,
            "cross_price": cross_price,
            "forecast": None
            if forecast is None
            else {
                "p_target": forecast.p_target,
                "p_stop": forecast.p_stop,
                "p_timeout": forecast.p_timeout,
                "lower_90": forecast.lower_90,
                "hourly_vol": forecast.hourly_vol,
                "drift_per_bar": forecast.drift_per_bar,
                "timeout_price": forecast.timeout_price,
                "paths": forecast.paths,
            },
            "kelly": kelly,
            "gates": gates.reason_codes,
        },
    )


def build_exchange_call(
    *,
    instrument: Instrument,
    quote: Quote | None,
    book: OrderBook | None,
    model_probability: float | None,
    probability_source: str | None,
    sportsbook_implied: float | None,
    now: datetime | None = None,
    recommendation_id: str | None = None,
) -> MarketDraft:
    now = now or datetime.now(UTC)
    gates = GateResult()
    source = (probability_source or "").lower()
    independent = source in {"model", "manual_verified"} and model_probability is not None
    if source == "market_implied" or not independent:
        model_probability = None
        gates.add_hard("NO_INDEPENDENT_PROBABILITY", REASON_TEXT["NO_INDEPENDENT_PROBABILITY"])

    status = str((instrument.extra or {}).get("status") or "open").lower()
    if status not in {"open", "active", ""}:
        gates.add_hard("MARKET_NOT_OPEN", REASON_TEXT["MARKET_NOT_OPEN"])
    if (instrument.extra or {}).get("can_close_early"):
        gates.add_review("CAN_CLOSE_EARLY", REASON_TEXT["CAN_CLOSE_EARLY"])

    contract_type = classify_contract(instrument)
    rules_issue = rules_need_review(instrument, contract_type)
    if rules_issue:
        gates.add_review("CONTRACT_RULES_UNMATCHED", rules_issue)
    team = team_name(instrument)
    if len(team) < 3:
        gates.add_review("CONTRACT_IDENTITY_UNCLEAR", REASON_TEXT["CONTRACT_IDENTITY_UNCLEAR"])

    yes_ask = quote.ask if quote else None
    yes_bid = quote.bid if quote else None
    no_ask = _no_ask(instrument, yes_bid)
    if yes_ask is None or no_ask is None:
        gates.add_hard("BOOK_UNAVAILABLE", REASON_TEXT["BOOK_UNAVAILABLE"], wait=True)
    if not contract_spread_ok(yes_bid, yes_ask):
        gates.add_hard("THIN_LIQUIDITY", REASON_TEXT["THIN_LIQUIDITY"])
    ask_size = _ask_size(book, quote)
    if ask_size is not None and ask_size < 20:
        gates.add_hard("THIN_LIQUIDITY", REASON_TEXT["THIN_LIQUIDITY"])
    if quote and not price_is_fresh(quote.timestamp, now):
        gates.add_hard("STALE_PRICE", REASON_TEXT["STALE_PRICE"])

    sport = instrument.sport
    series = str((instrument.extra or {}).get("series_ticker") or instrument.league or "")
    coefficient = kalshi_coefficient(series, sport)
    yes_cost = (
        fee_adjusted_contract_cost(yes_ask, coefficient=coefficient)
        if yes_ask is not None
        else None
    )
    no_cost = (
        fee_adjusted_contract_cost(no_ask, coefficient=coefficient) if no_ask is not None else None
    )
    fair = None
    edge = None
    ev = None
    if yes_cost is not None and no_cost is not None:
        compared = compare_to_market(
            model_probability=float(model_probability) if model_probability is not None else 0.0,
            american_odds=cost_to_american(yes_cost),
            opposite_american_odds=cost_to_american(no_cost),
        )
        fair = float(compared["fair_implied_probability"])
        if model_probability is not None:
            edge = float(compared["edge_vs_fair"])
            ev = float(compared["expected_value"])
    gap = price_gap_signal(sportsbook_implied, fair)
    if gap and abs(float(gap["gap"])) >= 0.02:
        gates.reason_codes.append("PRICE_GAP")

    quality = 0.8 if independent else 0.45
    confidence = _confidence(quality, edge)
    verdict = assign_verdict(
        edge=edge if edge is not None else -1.0,
        expected_value=ev if ev is not None else -1.0,
        confidence=confidence,
        reasons=gates.reason_codes,
        hard_skip_reasons=gates.hard_skip_reasons,
        review_reasons=gates.review_reasons,
        wait_codes=gates.wait_codes,
        variance=0.35,
        quality=quality,
        american_odds=cost_to_american(yes_cost) if yes_cost is not None else -110,
    )
    decision = price_gap_cannot_authorize_play(verdict.decision, has_independent_model=independent)
    stake = 0.0 if decision in {"SKIP", "WAIT", "REVIEW"} else verdict.suggested_stake_pct
    kelly = None
    if independent and model_probability is not None and yes_cost is not None:
        kelly = quarter_kelly_stake(
            model_probability,
            cost_to_american(yes_cost),
            lower_90=max(0.0, model_probability - 0.05),
        )
        if decision in {"PLAY", "LEAN", "WATCH"}:
            stake = round(min(stake, float(kelly.get("recommended_stake_pct") or 0.0)), 6)
    verdict_tier = "stay_away" if decision != verdict.decision else verdict.tier
    bucket = now.strftime("%Y%m%d%H")
    key = _idempotency(
        {
            "venue": "kalshi",
            "ticker": instrument.instrument_id,
            "bucket": bucket,
            "version": EXCHANGE_MODEL_VERSION,
            "yes": None if yes_ask is None else round(yes_ask, 4),
        }
    )
    return MarketDraft(
        venue="kalshi",
        venue_group="sports_exchange",
        instrument_id=instrument.instrument_id,
        call_type="contract_side",
        title=instrument.title,
        selection=f"YES {team}" if team else "YES",
        entry=yes_cost,
        target=None,
        stop=None,
        horizon_hours=None,
        horizon_end=_close_time(instrument),
        market_price=yes_cost,
        fair_price=fair,
        model_probability=model_probability,
        lower_90=None if model_probability is None else max(0.0, model_probability - 0.05),
        edge=edge,
        expected_value=ev,
        confidence=verdict.confidence
        if decision == verdict.decision
        else min(verdict.confidence, 69),
        verdict=decision,
        tier=verdict_tier,
        edge_class=verdict.edge_class,
        stake_pct=stake,
        reason_codes=verdict.reason_codes,
        reasons=explain(verdict.reason_codes),
        warnings=verdict.warnings,
        price_gap=gap,
        model_version=EXCHANGE_MODEL_VERSION,
        idempotency_key=key,
        payload={
            "read_only": True,
            "fees_included": True,
            "contract_type": contract_type,
            "probability_source": source or None,
            "recommendation_id": recommendation_id,
            "coefficient": coefficient,
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "yes_cost": yes_cost,
            "no_cost": no_cost,
            "kelly": kelly,
            "gates": gates.reason_codes,
            "price_gap_cannot_create_play": True,
        },
    )


def _entry_price(quote: Quote | None, candles: list[Candle]) -> float | None:
    if quote and quote.last:
        return float(quote.last)
    if quote and quote.bid and quote.ask:
        return (float(quote.bid) + float(quote.ask)) / 2.0
    if candles:
        return float(sorted(candles, key=lambda row: row.ts)[-1].close)
    return None


def _hourly_vol_guess(candles: list[Candle]) -> float:
    ordered = sorted(candles, key=lambda row: row.ts)
    closes = [row.close for row in ordered if row.close > 0]
    if len(closes) < 5:
        return 0.01
    rets = []
    for prev, nxt in zip(closes, closes[1:], strict=False):
        if prev > 0 and nxt > 0:
            rets.append(abs((nxt - prev) / prev))
    if not rets:
        return 0.01
    return max(sum(rets) / len(rets), 1e-4)


def _no_ask(instrument: Instrument, yes_bid: float | None) -> float | None:
    extra = instrument.extra or {}
    no_ask = extra.get("no_ask")
    if isinstance(no_ask, (int, float)) and float(no_ask) > 0:
        return float(no_ask)
    if yes_bid is not None:
        return max(0.0, 1.0 - float(yes_bid))
    return None


def _ask_size(book: OrderBook | None, quote: Quote | None) -> float | None:
    if quote and quote.ask_size:
        return float(quote.ask_size)
    if book and book.asks:
        return float(book.asks[0].size)
    return None


def _close_time(instrument: Instrument) -> datetime | None:
    raw = (instrument.extra or {}).get("close_time")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
