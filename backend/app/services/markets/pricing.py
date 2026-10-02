"""Fees, implied probability, and crypto break-even.

A contract price is never treated as the model's own probability. Fees are
added to the price before any edge is computed.
"""

from __future__ import annotations

import math

from app.services.markets import COINBASE_TAKER_FEE, KALSHI_TAKER_COEFFICIENT
from app.services.ywp_quant.odds import (
    decimal_to_american,
    probability_to_american,
)


def round_up_cents(amount: float) -> float:
    """Kalshi rounds the fee up to the next cent."""
    if amount <= 0:
        return 0.0
    cents = math.ceil(amount * 100 - 1e-9)
    return cents / 100.0


def kalshi_coefficient(series_ticker: str | None = None, sport: str | None = None) -> float:
    """MLB game series are half the base taker coefficient. Everything else is 0.07."""
    text = f"{series_ticker or ''} {sport or ''}".lower()
    if "mlb" in text or "kxmlb" in text:
        return KALSHI_TAKER_COEFFICIENT * 0.5
    return KALSHI_TAKER_COEFFICIENT


def kalshi_taker_fee(
    contracts: float,
    price: float,
    *,
    coefficient: float = KALSHI_TAKER_COEFFICIENT,
) -> float:
    """Taker fee in dollars. ``price`` is the contract price in dollars (0–1)."""
    p = min(max(float(price), 0.0), 1.0)
    qty = max(float(contracts), 0.0)
    raw = coefficient * qty * p * (1.0 - p)
    return round_up_cents(raw)


def fee_adjusted_contract_cost(
    price: float,
    *,
    contracts: float = 1.0,
    coefficient: float = KALSHI_TAKER_COEFFICIENT,
) -> float:
    """What one contract costs after the taker fee, as a 0–1 implied price."""
    if contracts <= 0:
        return min(max(price, 0.0), 0.999)
    fee = kalshi_taker_fee(contracts, price, coefficient=coefficient)
    return min(0.999, max(0.0, float(price) + fee / contracts))


def cost_to_american(cost: float) -> int:
    """Fee-adjusted contract cost (implied probability) to American odds."""
    probability = min(max(float(cost), 0.001), 0.999)
    return int(round(probability_to_american(probability)))


def crypto_break_even(entry: float, target: float, stop: float) -> float:
    """Chance of touching the target first if price is a fair coin, before fees.

    This is risk / (risk + reward), which is (entry - stop) / (target - stop)
    for a long bracket.
    """
    span = float(target) - float(stop)
    if span <= 0 or target <= entry or stop >= entry:
        return 1.0
    return (float(entry) - float(stop)) / span


def fee_adjusted_break_even(
    entry: float,
    target: float,
    stop: float,
    *,
    taker_fee: float = COINBASE_TAKER_FEE,
) -> float:
    """Break-even after a taker fee on the way in and on the way out.

    Reward shrinks by the round trip. Risk grows by the same fee. The result
    is the probability of hitting the target that merely covers costs.
    """
    if entry <= 0 or target <= stop:
        return 1.0
    round_trip = 2.0 * max(float(taker_fee), 0.0)
    reward = (float(target) - float(entry)) / float(entry) - round_trip
    risk = (float(entry) - float(stop)) / float(entry) + round_trip
    if reward <= 0 or risk <= 0:
        return 1.0
    return risk / (risk + reward)


def crypto_expected_value(
    *,
    p_target: float,
    p_stop: float,
    p_timeout: float,
    entry: float,
    target: float,
    stop: float,
    timeout_price: float,
    taker_fee: float = COINBASE_TAKER_FEE,
) -> float:
    """Expected return as a fraction of entry, after round-trip taker fees."""
    if entry <= 0:
        return 0.0
    fee = 2.0 * max(float(taker_fee), 0.0)

    def net(exit_price: float) -> float:
        return (float(exit_price) - float(entry)) / float(entry) - fee

    return (
        float(p_target) * net(target)
        + float(p_stop) * net(stop)
        + float(p_timeout) * net(timeout_price)
    )


def reward_risk_american(
    entry: float,
    target: float,
    stop: float,
    *,
    taker_fee: float = COINBASE_TAKER_FEE,
) -> float:
    """American odds implied by the fee-adjusted reward/risk of a long bracket."""
    if entry <= 0:
        return -10000.0
    round_trip = 2.0 * max(float(taker_fee), 0.0) * float(entry)
    reward = (float(target) - float(entry)) - round_trip
    risk = (float(entry) - float(stop)) + round_trip
    if reward <= 0 or risk <= 0:
        return -10000.0
    decimal_odds = 1.0 + reward / risk
    return float(decimal_to_american(decimal_odds))
