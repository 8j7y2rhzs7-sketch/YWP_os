"""Idempotent scan and grade jobs.

Safe to run twice. A repeated scan in the same hour does not insert a second
copy of the same call. Grading only fills calls that do not have an outcome yet.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import utcnow
from app.models import Recommendation
from app.models_markets import (
    MarketCall,
    MarketCandle,
    MarketInstrument,
    MarketJobRun,
    MarketModelVersion,
    MarketOutcome,
    MarketSnapshot,
)
from app.services.markets import (
    COINBASE_TAKER_FEE,
    CRYPTO_MODEL_VERSION,
    CRYPTO_WHITELIST,
    EXCHANGE_MODEL_VERSION,
)
from app.services.markets.adapter import Candle
from app.services.markets.adapters.coinbase import CoinbaseAdapter
from app.services.markets.adapters.kalshi import KalshiAdapter
from app.services.markets.adapters.kraken import KrakenAdapter
from app.services.markets.crypto_model import DRIFT_SHRINK, EWMA_LAMBDA
from app.services.markets.exchange_mapping import (
    INDEPENDENT_SOURCES,
    SportsModelQuote,
    select_independent_probability,
)
from app.services.markets.grading import (
    contract_realized_return,
    crypto_realized_return,
    grade_brier,
    grade_crypto_candles,
    grade_kalshi_result,
    outcome_won,
)
from app.services.markets.markets_engine import MarketDraft, build_crypto_call, build_exchange_call

logger = logging.getLogger(__name__)

HORIZONS = (4.0, 24.0)


def freeze_model_version(
    db: Session,
    *,
    kind: str,
    version: str,
    parameters: dict[str, object],
) -> MarketModelVersion:
    """First time a version is seen, freeze it. Later scans keep the same id."""
    existing = db.scalar(select(MarketModelVersion).where(MarketModelVersion.version == version))
    if existing is not None:
        return existing
    row = MarketModelVersion(
        kind=kind,
        version=version,
        parameters=parameters,
        frozen_at=utcnow(),
        active=True,
        notes="Frozen the first time this version ran. A new version string starts a new count.",
    )
    db.add(row)
    db.flush()
    return row


def run_scan(
    db: Session,
    *,
    coinbase: CoinbaseAdapter | None = None,
    kraken: KrakenAdapter | None = None,
    kalshi: KalshiAdapter | None = None,
    now: datetime | None = None,
    n_paths: int = 1500,
    horizons: tuple[float, ...] = HORIZONS,
) -> dict[str, object]:
    now = now or datetime.now(UTC)
    if not settings.markets_enabled:
        return {
            "status": "disabled",
            "crypto_calls": 0,
            "exchange_calls": 0,
            "errors": [{"venue": "markets", "message": "YWP_MARKETS_ENABLED is off"}],
            "read_only": True,
        }
    job = MarketJobRun(job_name="scan", started_at=now, status="running", errors=[])
    db.add(job)
    db.flush()
    errors: list[dict[str, str]] = []
    crypto_calls = 0
    exchange_calls = 0
    own_coinbase = coinbase is None
    own_kraken = kraken is None
    own_kalshi = kalshi is None
    coinbase = coinbase or CoinbaseAdapter(
        enabled=settings.markets_coinbase_enabled,
        min_interval=0.12,
    )
    kraken = kraken or KrakenAdapter(enabled=settings.markets_kraken_enabled, min_interval=1.05)
    kalshi = kalshi or KalshiAdapter(enabled=settings.markets_kalshi_enabled, min_interval=0.08)
    try:
        freeze_model_version(
            db,
            kind="crypto",
            version=CRYPTO_MODEL_VERSION,
            parameters={
                "ewma_lambda": EWMA_LAMBDA,
                "drift_shrink": DRIFT_SHRINK,
                "taker_fee": COINBASE_TAKER_FEE,
                "paths": n_paths,
                "whitelist": list(CRYPTO_WHITELIST),
                "minimum_edge": settings.minimum_edge,
            },
        )
        freeze_model_version(
            db,
            kind="sports_exchange",
            version=EXCHANGE_MODEL_VERSION,
            parameters={"fee": "kalshi_taker_0.07", "mlb_multiplier": 0.5},
        )
        if settings.markets_coinbase_enabled:
            crypto_calls = _scan_crypto(
                db,
                coinbase=coinbase,
                kraken=kraken,
                now=now,
                n_paths=n_paths,
                horizons=horizons,
                errors=errors,
            )
        else:
            errors.append({"venue": "coinbase", "message": "switched off"})
        if settings.markets_kalshi_enabled:
            exchange_calls = _scan_kalshi(db, kalshi=kalshi, now=now, errors=errors)
        else:
            errors.append({"venue": "kalshi", "message": "switched off"})
        status = "ok" if not errors else "completed_with_errors"
    except Exception as exc:
        logger.exception("markets scan failed")
        errors.append({"venue": "scan", "message": str(exc)})
        crypto_calls = 0
        exchange_calls = 0
        db.rollback()
        job = MarketJobRun(
            job_name="scan", started_at=now, status="error", errors=errors, error_count=len(errors)
        )
        db.add(job)
    else:
        job.status = status
        job.errors = errors
        job.error_count = len(errors)
        job.items_processed = crypto_calls + exchange_calls
        job.finished_at = utcnow()
    finally:
        if own_coinbase:
            coinbase.close()
        if own_kraken:
            kraken.close()
        if own_kalshi:
            kalshi.close()
    db.commit()
    return {
        "status": job.status,
        "crypto_calls": crypto_calls,
        "exchange_calls": exchange_calls,
        "errors": errors,
        "read_only": True,
        "job_id": job.id,
    }


def run_grade(
    db: Session,
    *,
    coinbase: CoinbaseAdapter | None = None,
    kalshi: KalshiAdapter | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    now = now or datetime.now(UTC)
    if not settings.markets_enabled:
        return {"status": "disabled", "graded": 0, "pending": 0, "errors": [], "read_only": True}
    job = MarketJobRun(job_name="grade", started_at=now, status="running", errors=[])
    db.add(job)
    db.flush()
    errors: list[dict[str, str]] = []
    graded = 0
    own_coinbase = coinbase is None
    own_kalshi = kalshi is None
    coinbase = coinbase or CoinbaseAdapter(
        enabled=settings.markets_coinbase_enabled, min_interval=0.12
    )
    kalshi = kalshi or KalshiAdapter(enabled=settings.markets_kalshi_enabled, min_interval=0.08)
    try:
        graded += _grade_crypto(db, coinbase=coinbase, now=now, errors=errors)
        graded += _grade_kalshi(db, kalshi=kalshi, errors=errors)
        pending = _pending_count(db)
        job.status = "ok" if not errors else "completed_with_errors"
        job.errors = errors
        job.error_count = len(errors)
        job.items_processed = graded
        job.finished_at = utcnow()
    except Exception as exc:
        logger.exception("markets grade failed")
        errors.append({"venue": "grade", "message": str(exc)})
        pending = _pending_count(db)
        db.rollback()
        job = MarketJobRun(
            job_name="grade",
            started_at=now,
            status="error",
            errors=errors,
            finished_at=utcnow(),
        )
        db.add(job)
    finally:
        if own_coinbase:
            coinbase.close()
        if own_kalshi:
            kalshi.close()
    db.commit()
    return {
        "status": job.status,
        "graded": graded,
        "pending": pending,
        "errors": errors,
        "read_only": True,
        "job_id": job.id,
    }


def _scan_crypto(
    db: Session,
    *,
    coinbase: CoinbaseAdapter,
    kraken: KrakenAdapter,
    now: datetime,
    n_paths: int,
    horizons: tuple[float, ...],
    errors: list[dict[str, str]],
) -> int:
    saved = 0
    start = now - timedelta(hours=220)
    kraken_on = settings.markets_kraken_enabled and kraken.enabled
    if not kraken_on:
        errors.append({"venue": "kraken", "message": "switched off"})
    for symbol in CRYPTO_WHITELIST:
        try:
            candles = coinbase.get_candles(symbol, "ONE_HOUR", start, now)
            quote = coinbase.get_quote(symbol)
            book = coinbase.get_orderbook(symbol, depth=15)
        except Exception as exc:
            errors.append({"venue": "coinbase", "message": f"{symbol}: {exc}"})
            continue
        _save_candles(db, candles)
        _save_snapshot(
            db, "coinbase", symbol, quote.bid, quote.ask, quote.last, book_levels=len(book.bids)
        )
        _save_instrument(db, "coinbase", symbol, "crypto_spot", symbol, symbol, None, None, "")
        cross_price = None
        if kraken_on:
            try:
                cross = kraken.get_quote(symbol)
                cross_price = cross.last or cross.bid
            except Exception as exc:
                errors.append({"venue": "kraken", "message": f"{symbol}: {exc}"})
        for horizon in horizons:
            draft = build_crypto_call(
                symbol=symbol,
                candles=candles,
                quote=quote,
                book=book,
                cross_price=cross_price,
                now=now,
                horizon_hours=horizon,
                n_paths=n_paths,
                seed=stable_seed(symbol, horizon),
            )
            if _save_call(db, draft):
                saved += 1
    return saved


def _scan_kalshi(
    db: Session,
    *,
    kalshi: KalshiAdapter,
    now: datetime,
    errors: list[dict[str, str]],
) -> int:
    saved = 0
    try:
        instruments = kalshi.list_instruments(category="Sports")
    except Exception as exc:
        errors.append({"venue": "kalshi", "message": str(exc)})
        return 0
    for instrument in instruments:
        try:
            quote = kalshi.get_quote(instrument.instrument_id)
            book = kalshi.get_orderbook(instrument.instrument_id, depth=5)
        except Exception as exc:
            errors.append({"venue": "kalshi", "message": f"{instrument.instrument_id}: {exc}"})
            continue
        model_p, sportsbook, source, rec_id = _lookup_sports_model(db, instrument)
        chosen = select_independent_probability(
            []
            if model_p is None or source is None
            else [
                SportsModelQuote(
                    model_probability=model_p,
                    sportsbook_implied=sportsbook,
                    source=source,
                    recommendation_id=rec_id,
                )
            ]
        )
        draft = build_exchange_call(
            instrument=instrument,
            quote=quote,
            book=book,
            model_probability=None if chosen is None else chosen.model_probability,
            probability_source=None if chosen is None else chosen.source,
            sportsbook_implied=None if chosen is None else chosen.sportsbook_implied,
            recommendation_id=None if chosen is None else chosen.recommendation_id,
            now=now,
        )
        _save_instrument(
            db,
            "kalshi",
            instrument.instrument_id,
            "event_contract",
            instrument.symbol,
            instrument.title,
            instrument.sport,
            instrument.league,
            instrument.rules_text,
        )
        _save_snapshot(
            db,
            "kalshi",
            instrument.instrument_id,
            quote.bid,
            quote.ask,
            quote.last,
            book_levels=len(book.bids),
        )
        if _save_call(db, draft):
            saved += 1
    return saved


def _lookup_sports_model(
    db: Session, instrument
) -> tuple[float | None, float | None, str | None, str | None]:
    from app.services.markets.exchange_mapping import team_name

    team = team_name(instrument)
    if len(team) < 3:
        return None, None, None, None
    rows = db.scalars(
        select(Recommendation)
        .where(Recommendation.market_type == "moneyline")
        .order_by(Recommendation.created_at.desc())
        .limit(300)
    ).all()
    needle = team.lower()
    for rec in rows:
        hay = f"{rec.selection} {rec.event_name}".lower()
        if needle not in hay:
            continue
        if instrument.sport and rec.sport and rec.sport.lower() != instrument.sport.lower():
            continue
        source = str((rec.snapshot or {}).get("probability_source") or "")
        if source not in INDEPENDENT_SOURCES:
            continue
        implied = float(rec.implied_probability) if rec.implied_probability is not None else None
        return float(rec.adjusted_probability), implied, source, rec.id
    return None, None, None, None


def _grade_crypto(
    db: Session,
    *,
    coinbase: CoinbaseAdapter,
    now: datetime,
    errors: list[dict[str, str]],
) -> int:
    graded_ids = select(MarketOutcome.call_id)
    pending = db.scalars(
        select(MarketCall).where(
            MarketCall.venue_group == "crypto",
            MarketCall.horizon_end.is_not(None),
            MarketCall.horizon_end <= now,
            MarketCall.id.not_in(graded_ids),
        )
    ).all()
    count = 0
    for call in pending:
        if (
            call.entry is None
            or call.target is None
            or call.stop is None
            or call.horizon_end is None
        ):
            continue
        candles = _load_candles(
            db, call.venue, call.instrument_id, call.created_at, call.horizon_end
        )
        if not candles and settings.markets_coinbase_enabled and coinbase.enabled:
            try:
                candles = coinbase.get_candles(
                    call.instrument_id,
                    "ONE_HOUR",
                    call.created_at,
                    call.horizon_end + timedelta(hours=1),
                )
                _save_candles(db, candles)
            except Exception as exc:
                errors.append(
                    {"venue": "coinbase", "message": f"grade {call.instrument_id}: {exc}"}
                )
                continue
        outcome, exit_price = grade_crypto_candles(
            candles,
            start=call.created_at,
            horizon_end=call.horizon_end,
            target=call.target,
            stop=call.stop,
            now=now,
        )
        if outcome is None:
            continue
        won = outcome_won(outcome)
        realized = crypto_realized_return(
            outcome,
            entry=call.entry,
            target=call.target,
            stop=call.stop,
            exit_price=exit_price,
        )
        db.add(
            MarketOutcome(
                call_id=call.id,
                resolved_at=now,
                outcome=outcome,
                realized_return=realized,
                closing_price=exit_price,
                brier=grade_brier(call.model_probability, outcome),
                grading_method="coinbase_candle_replay",
                won=won,
                notes="Same-candle target and stop counts as STOP.",
            )
        )
        count += 1
    return count


def _grade_kalshi(db: Session, *, kalshi: KalshiAdapter, errors: list[dict[str, str]]) -> int:
    if not settings.markets_kalshi_enabled or not kalshi.enabled:
        return 0
    graded_ids = select(MarketOutcome.call_id)
    pending = db.scalars(
        select(MarketCall).where(
            MarketCall.venue == "kalshi",
            MarketCall.id.not_in(graded_ids),
        )
    ).all()
    count = 0
    for call in pending:
        try:
            settlement = kalshi.get_settlement(call.instrument_id)
        except Exception as exc:
            errors.append({"venue": "kalshi", "message": f"grade {call.instrument_id}: {exc}"})
            continue
        if settlement is None:
            continue
        outcome = grade_kalshi_result(settlement.result)
        if outcome is None:
            continue
        won = outcome_won(outcome)
        db.add(
            MarketOutcome(
                call_id=call.id,
                resolved_at=settlement.settled_at or utcnow(),
                outcome=outcome,
                realized_return=contract_realized_return(outcome, call.market_price),
                closing_price=1.0 if outcome == "YES" else 0.0 if outcome == "NO" else None,
                brier=grade_brier(call.model_probability, outcome),
                grading_method="kalshi_settlement",
                won=won,
                notes="Public Kalshi settlement. No order was sent.",
            )
        )
        count += 1
    return count


def _pending_count(db: Session) -> int:
    graded_ids = select(MarketOutcome.call_id)
    rows = db.scalars(select(MarketCall.id).where(MarketCall.id.not_in(graded_ids))).all()
    return len(rows)


def _save_call(db: Session, draft: MarketDraft) -> bool:
    existing = db.scalar(
        select(MarketCall.id).where(MarketCall.idempotency_key == draft.idempotency_key)
    )
    if existing:
        return False
    db.add(
        MarketCall(
            venue=draft.venue,
            venue_group=draft.venue_group,
            instrument_id=draft.instrument_id,
            call_type=draft.call_type,
            title=draft.title,
            selection=draft.selection,
            entry=draft.entry,
            target=draft.target,
            stop=draft.stop,
            horizon_hours=draft.horizon_hours,
            horizon_end=draft.horizon_end,
            market_price=draft.market_price,
            fair_price=draft.fair_price,
            model_probability=draft.model_probability,
            lower_90=draft.lower_90,
            edge=draft.edge,
            expected_value=draft.expected_value,
            confidence=draft.confidence,
            verdict=draft.verdict,
            tier=draft.tier,
            edge_class=draft.edge_class,
            stake_pct=draft.stake_pct,
            reason_codes=draft.reason_codes,
            reasons=draft.reasons,
            warnings=draft.warnings,
            price_gap=draft.price_gap,
            model_version=draft.model_version,
            idempotency_key=draft.idempotency_key,
            payload=draft.payload,
            created_at=utcnow(),
        )
    )
    db.flush()
    return True


def _save_instrument(
    db: Session,
    venue: str,
    instrument_id: str,
    kind: str,
    symbol: str,
    title: str,
    sport: str | None,
    league: str | None,
    rules: str,
) -> None:
    existing = db.scalar(
        select(MarketInstrument).where(
            MarketInstrument.venue == venue,
            MarketInstrument.instrument_id == instrument_id,
        )
    )
    if existing:
        existing.title = title[:256]
        existing.active = True
        existing.updated_at = utcnow()
        return
    db.add(
        MarketInstrument(
            venue=venue,
            instrument_id=instrument_id,
            kind=kind,
            symbol=symbol[:128],
            title=title[:256],
            sport=sport,
            league=league,
            contract_rules=rules or "",
            active=True,
        )
    )


def _save_snapshot(
    db: Session,
    venue: str,
    instrument_id: str,
    bid: float | None,
    ask: float | None,
    last: float | None,
    *,
    book_levels: int,
) -> None:
    spread = None
    if bid and ask and bid > 0:
        spread = (ask - bid) / bid
    db.add(
        MarketSnapshot(
            venue=venue,
            instrument_id=instrument_id,
            bid=bid,
            ask=ask,
            last=last,
            spread=spread,
            depth_summary={"levels": book_levels},
            fetched_at=utcnow(),
            raw={"bid": bid, "ask": ask, "last": last},
        )
    )


def _save_candles(db: Session, candles: list[Candle]) -> None:
    for candle in candles:
        exists = db.scalar(
            select(MarketCandle.id).where(
                MarketCandle.venue == candle.venue,
                MarketCandle.instrument_id == candle.instrument_id,
                MarketCandle.granularity == candle.granularity,
                MarketCandle.ts == candle.ts,
            )
        )
        if exists:
            continue
        db.add(
            MarketCandle(
                venue=candle.venue,
                instrument_id=candle.instrument_id,
                granularity=candle.granularity,
                ts=candle.ts,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
        )


def _load_candles(
    db: Session,
    venue: str,
    instrument_id: str,
    start: datetime,
    end: datetime,
) -> list[Candle]:
    rows = db.scalars(
        select(MarketCandle)
        .where(
            MarketCandle.venue == venue,
            MarketCandle.instrument_id == instrument_id,
            MarketCandle.ts >= start,
            MarketCandle.ts < end,
        )
        .order_by(MarketCandle.ts)
    ).all()
    return [
        Candle(
            venue=row.venue,
            instrument_id=row.instrument_id,
            granularity=row.granularity,
            ts=row.ts,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    ]


def stable_seed(symbol: str, horizon: float) -> int:
    return sum(ord(char) for char in f"{symbol}:{horizon}") % 10_000
