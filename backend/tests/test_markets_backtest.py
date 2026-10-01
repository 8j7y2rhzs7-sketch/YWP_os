"""Offline backtest on the committed candle fixture."""

from pathlib import Path

from scripts.backtest_crypto import load_fixture, run_backtest, synthetic_rows


def test_fixture_backtest_reports_hit_rate_and_fees() -> None:
    path = Path("tests/fixtures/markets_candles.json")
    candles = load_fixture(path)
    assert set(candles) == {"BTC-USD", "ETH-USD", "SOL-USD"}
    assert len(candles["BTC-USD"]) >= 70
    report = run_backtest(candles, n_paths=120, lookback=40, step_hours=8, horizon_hours=4)
    combined = report["combined"]
    assert combined["graded"] > 0
    assert 0 <= combined["hit_rate"] <= 1
    assert combined["brier"] is not None
    assert combined["mean_ev_after_fees"] is not None
    assert report["taker_fee"] == 0.006
    assert report["symbols"]["BTC-USD"]["calibration_buckets"] is not None


def test_synthetic_rows_match_fixture_length() -> None:
    rows = synthetic_rows("BTC-USD", 100_000, 0.01, bars=80)
    assert len(rows) == 80
    assert rows[0]["ts"].startswith("2026-01-01")
