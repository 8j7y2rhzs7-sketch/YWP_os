"""Grade a past call without placing anything.

Crypto: replay candles and see whether the target or the stop printed first.
If both print inside the same candle, the grade is STOP.
Kalshi: use the public settled result.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.markets import COINBASE_TAKER_FEE
from app.services.markets.adapter import Candle
from app.services.pipeline.calibration import brier_score


def _aware(value: datetime) -> datetime:
    """SQLite gives naive timestamps. Treat them as UTC so grading can compare."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def grade_crypto_candles(
    candles: list[Candle],
    *,
    start: datetime,
    horizon_end: datetime,
    target: float,
    stop: float,
    now: datetime,
) -> tuple[str | None, float | None]:
    """Return (outcome, exit price). Outcome is None when the horizon is still open."""
    start = _aware(start)
    horizon_end = _aware(horizon_end)
    now = _aware(now)
    ordered = sorted(candles, key=lambda row: _aware(row.ts))
    window = [row for row in ordered if start <= _aware(row.ts) < horizon_end]
    for row in window:
        hit_target = row.high >= target
        hit_stop = row.low <= stop
        if hit_target and hit_stop:
            return "STOP", stop
        if hit_stop:
            return "STOP", stop
        if hit_target:
            return "TARGET", target
    if now < horizon_end:
        return None, None
    closing = window[-1].close if window else (ordered[-1].close if ordered else None)
    return "TIMEOUT", closing


def crypto_realized_return(
    outcome: str,
    *,
    entry: float,
    target: float,
    stop: float,
    exit_price: float | None,
    taker_fee: float = COINBASE_TAKER_FEE,
) -> float:
    if entry <= 0:
        return 0.0
    if outcome == "TARGET":
        exit_px = target
    elif outcome == "STOP":
        exit_px = stop
    else:
        exit_px = exit_price if exit_price is not None else entry
    return (exit_px - entry) / entry - 2.0 * taker_fee


def grade_kalshi_result(result: str | None) -> str | None:
    if result is None:
        return None
    label = result.strip().upper()
    if label in {"YES", "NO", "VOID"}:
        return label
    return None


def contract_realized_return(outcome: str, cost: float | None) -> float:
    """Return on the fee-adjusted cost of one YES contract. Payout is $1."""
    if outcome == "VOID" or cost is None or cost <= 0:
        return 0.0
    if outcome == "YES":
        return (1.0 - cost) / cost
    if outcome == "NO":
        return -1.0
    return 0.0


def outcome_won(outcome: str) -> bool | None:
    if outcome in {"TARGET", "YES"}:
        return True
    if outcome in {"STOP", "TIMEOUT", "NO"}:
        return False
    return None


def grade_brier(model_probability: float | None, outcome: str) -> float | None:
    won = outcome_won(outcome)
    if model_probability is None or won is None:
        return None
    return float(brier_score(model_probability, won))
