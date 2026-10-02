"""Replay the crypto bracket model on hourly candles.

No orders are sent. Pass --fixture to stay offline. --live pages public
Coinbase candles for BTC, ETH, and SOL (needs a network).

    uv run python scripts/backtest_crypto.py --fixture tests/fixtures/markets_candles.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.markets import COINBASE_TAKER_FEE, CRYPTO_MODEL_VERSION  # noqa: E402
from app.services.markets.adapter import Candle, Level, OrderBook, Quote  # noqa: E402
from app.services.markets.grading import (  # noqa: E402
    crypto_realized_return,
    grade_crypto_candles,
    outcome_won,
)
from app.services.markets.markets_engine import build_crypto_call  # noqa: E402
from app.services.pipeline.calibration import summarize_calibration  # noqa: E402
from app.services.ywp_quant.calibration import calibration_table  # noqa: E402


def rows_to_candles(symbol: str, rows: list[dict[str, object]]) -> list[Candle]:
    candles: list[Candle] = []
    for row in rows:
        stamp = datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        candles.append(
            Candle(
                venue="coinbase",
                instrument_id=symbol,
                granularity="ONE_HOUR",
                ts=stamp,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    candles.sort(key=lambda item: item.ts)
    return candles


def load_fixture(path: Path) -> dict[str, list[Candle]]:
    payload = json.loads(path.read_text())
    return {symbol: rows_to_candles(symbol, rows) for symbol, rows in payload.items()}


def synthetic_rows(
    symbol: str, start_price: float, vol: float, bars: int = 80
) -> list[dict[str, object]]:
    """Deterministic hourly bars. Used to rebuild the committed fixture."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    price = start_price
    rows: list[dict[str, object]] = []
    for index in range(bars):
        shock = vol * math.sin(index * 1.3) + 0.15 * vol * math.sin(index / 5)
        opened = price
        closed = max(1.0, price * (1 + shock))
        high = max(opened, closed) * (1 + vol * 0.35)
        low = min(opened, closed) * (1 - vol * 0.35)
        rows.append(
            {
                "ts": (start + timedelta(hours=index)).isoformat(),
                "open": round(opened, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(closed, 4),
                "volume": 100 + (index % 7) * 5,
            }
        )
        price = closed
    del symbol
    return rows


def _book(entry: float, instrument_id: str, ts: datetime) -> OrderBook:
    return OrderBook(
        instrument_id=instrument_id,
        bids=[Level(price=entry * 0.999, size=50)],
        asks=[Level(price=entry * 1.001, size=50)],
        timestamp=ts,
    )


def run_backtest(
    candles_by_symbol: dict[str, list[Candle]],
    *,
    horizon_hours: float = 4.0,
    step_hours: int = 4,
    lookback: int = 48,
    n_paths: int = 400,
    seed: int = 7,
) -> dict[str, object]:
    """Walk forward. Each call sees only candles before the decision bar."""
    per_symbol: dict[str, object] = {}
    combined_rows: list[tuple[float, bool, None, str]] = []
    combined_returns: list[float] = []
    for symbol, candles in candles_by_symbol.items():
        ordered = sorted(candles, key=lambda row: row.ts)
        hits = 0
        graded = 0
        returns: list[float] = []
        rows: list[tuple[float, bool, None, str]] = []
        index = lookback
        while index + int(horizon_hours) < len(ordered):
            history = ordered[:index]
            start = ordered[index].ts
            horizon_end = start + timedelta(hours=horizon_hours)
            future = [row for row in ordered if start <= row.ts < horizon_end]
            entry = history[-1].close
            when = history[-1].ts
            quote = Quote(
                instrument_id=symbol,
                bid=entry * 0.999,
                ask=entry * 1.001,
                last=entry,
                bid_size=50,
                ask_size=50,
                timestamp=when,
            )
            draft = build_crypto_call(
                symbol=symbol,
                candles=history,
                quote=quote,
                book=_book(entry, symbol, when),
                cross_price=entry,
                now=when,
                horizon_hours=horizon_hours,
                n_paths=n_paths,
                seed=seed,
            )
            if draft.model_probability is None or draft.target is None or draft.stop is None:
                index += step_hours
                continue
            outcome, exit_price = grade_crypto_candles(
                future,
                start=start,
                horizon_end=horizon_end,
                target=draft.target,
                stop=draft.stop,
                now=horizon_end,
            )
            if outcome is None:
                index += step_hours
                continue
            won = outcome_won(outcome)
            realized = crypto_realized_return(
                outcome,
                entry=entry,
                target=draft.target,
                stop=draft.stop,
                exit_price=exit_price,
            )
            graded += 1
            hits += int(bool(won))
            returns.append(realized)
            if won is not None:
                rows.append((float(draft.model_probability), bool(won), None, "crypto_bracket"))
            index += step_hours
        summary = summarize_calibration(rows)
        buckets = (
            calibration_table([row[0] for row in rows], [int(row[1]) for row in rows])
            if rows
            else []
        )
        per_symbol[symbol] = {
            "graded": graded,
            "hit_rate": round(hits / graded, 4) if graded else None,
            "mean_ev_after_fees": round(sum(returns) / len(returns), 6) if returns else None,
            "brier": summary["brier"],
            "calibration_buckets": buckets,
        }
        combined_rows.extend(rows)
        combined_returns.extend(returns)
    combined = summarize_calibration(combined_rows)
    return {
        "model_version": CRYPTO_MODEL_VERSION,
        "taker_fee": COINBASE_TAKER_FEE,
        "horizon_hours": horizon_hours,
        "read_only": True,
        "symbols": per_symbol,
        "combined": {
            "graded": len(combined_returns),
            "hit_rate": combined["actual_hit_rate"],
            "mean_ev_after_fees": round(sum(combined_returns) / len(combined_returns), 6)
            if combined_returns
            else None,
            "brier": combined["brier"],
            "calibration_buckets": calibration_table(
                [row[0] for row in combined_rows],
                [int(row[1]) for row in combined_rows],
            )
            if combined_rows
            else [],
        },
        "note": (
            "Hit rate is how often the target printed before the stop. "
            "If both printed in one candle, the grade is a stop. Fees are included."
        ),
    }


def _live_candles(symbols: tuple[str, ...], bars: int = 300) -> dict[str, list[Candle]]:
    from app.services.markets.adapters.coinbase import CoinbaseAdapter

    end = datetime.now(UTC)
    start = end - timedelta(hours=bars + 5)
    adapter = CoinbaseAdapter(min_interval=0.15)
    try:
        return {symbol: adapter.get_candles(symbol, "ONE_HOUR", start, end) for symbol in symbols}
    finally:
        adapter.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the read-only crypto bracket model.")
    parser.add_argument("--fixture", type=Path, help="JSON candles. No network.")
    parser.add_argument("--live", action="store_true", help="Fetch public Coinbase candles.")
    parser.add_argument("--paths", type=int, default=600)
    parser.add_argument("--lookback", type=int, default=48)
    args = parser.parse_args()
    if args.fixture:
        candles = load_fixture(args.fixture)
    elif args.live:
        candles = _live_candles(("BTC-USD", "ETH-USD", "SOL-USD"))
    else:
        parser.error("Pass --fixture or --live")
    report = run_backtest(candles, n_paths=args.paths, lookback=args.lookback)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
