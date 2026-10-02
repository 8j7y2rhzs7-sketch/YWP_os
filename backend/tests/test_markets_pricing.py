"""Fees come off the price before an edge exists."""

from app.services.markets.pricing import (
    crypto_break_even,
    crypto_expected_value,
    fee_adjusted_break_even,
    fee_adjusted_contract_cost,
    kalshi_coefficient,
    kalshi_taker_fee,
)


def test_kalshi_fee_schedule_examples() -> None:
    assert kalshi_taker_fee(100, 0.50) == 1.75
    assert kalshi_taker_fee(1, 0.50) == 0.02
    assert kalshi_coefficient("KXMLBGAME", "mlb") == 0.035
    assert kalshi_coefficient("KXNFLGAME", "nfl") == 0.07


def test_contract_cost_includes_fee() -> None:
    cost = fee_adjusted_contract_cost(0.37)
    assert cost > 0.37
    assert cost < 0.40


def test_crypto_break_even_rises_after_fees() -> None:
    raw = crypto_break_even(100, 110, 95)
    assert abs(raw - (5 / 15)) < 1e-9
    adjusted = fee_adjusted_break_even(100, 110, 95, taker_fee=0.006)
    assert adjusted > raw
    ev = crypto_expected_value(
        p_target=raw,
        p_stop=1 - raw,
        p_timeout=0,
        entry=100,
        target=110,
        stop=95,
        timeout_price=100,
        taker_fee=0.006,
    )
    assert ev < 0
