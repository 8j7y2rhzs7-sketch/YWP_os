"""Crypto bracket model v1.

Question: will price hit the target before the stop inside the horizon?

Volatility is an EWMA of log returns. Drift is a heavily shrunk mix of trend,
momentum, and volume, pulled toward zero. Paths are bootstrapped historical
returns, rescaled to the forecast volatility. Same-bar target and stop counts
as a stop (conservative).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.services.markets.adapter import Candle

MIN_BARS = 40
DRIFT_SHRINK = 0.15
EWMA_LAMBDA = 0.94


@dataclass(frozen=True)
class BracketForecast:
    p_target: float
    p_stop: float
    p_timeout: float
    lower_90: float
    hourly_vol: float
    drift_per_bar: float
    timeout_price: float
    bars_used: int
    paths: int


def log_returns(closes: np.ndarray) -> np.ndarray:
    safe = np.clip(closes.astype(float), 1e-12, None)
    return np.diff(np.log(safe))


def ewma_vol(returns: np.ndarray, lam: float = EWMA_LAMBDA) -> float:
    if len(returns) == 0:
        return 0.0
    variance = float(np.var(returns))
    for value in returns:
        variance = lam * variance + (1.0 - lam) * float(value) ** 2
    return math.sqrt(max(variance, 0.0))


def shrunk_drift(returns: np.ndarray, volumes: np.ndarray) -> float:
    """Per-bar drift, shrunk hard toward zero unless volume confirms the move."""
    if len(returns) < 30:
        return 0.0
    short = float(np.mean(returns[-20:]))
    long = float(np.mean(returns[-50:])) if len(returns) >= 50 else float(np.mean(returns))
    momentum = float(np.mean(returns[-10:]))
    volume_scale = 1.0
    if len(volumes) >= 20:
        base = float(np.mean(volumes[-20:]))
        recent = float(np.mean(volumes[-5:]))
        if base > 0:
            volume_scale = 1.0 if recent >= base else 0.5
    raw = (0.5 * (short - long) + 0.5 * momentum) * volume_scale
    return raw * DRIFT_SHRINK


def expected_noise(entry: float, hourly_vol: float, horizon_hours: float) -> float:
    raw = float(entry) * max(hourly_vol, 1e-4) * math.sqrt(max(horizon_hours, 1.0))
    return max(raw, float(entry) * 0.002)


def suggest_bracket(entry: float, hourly_vol: float, horizon_hours: float) -> tuple[float, float]:
    """Stop at 1x expected noise, target at 1.5x. Both stay inside the sanity band."""
    noise = expected_noise(entry, hourly_vol, horizon_hours)
    return entry + 1.5 * noise, entry - noise


def bracket_is_sane(
    entry: float,
    target: float,
    stop: float,
    hourly_vol: float,
    horizon_hours: float,
) -> bool:
    noise = expected_noise(entry, hourly_vol, horizon_hours)
    if noise <= 0 or stop >= entry or target <= entry:
        return False
    risk = entry - stop
    reward = target - entry
    return noise * 0.99 <= risk <= noise * 3.01 and noise * 0.99 <= reward <= noise * 3.01


def forecast_bracket(
    candles: list[Candle],
    *,
    entry: float,
    target: float,
    stop: float,
    horizon_hours: float,
    n_paths: int = 2000,
    seed: int = 7,
) -> BracketForecast | None:
    """Bootstrap paths. Returns None when there is not enough history."""
    if len(candles) < MIN_BARS or entry <= 0 or n_paths < 1:
        return None
    ordered = sorted(candles, key=lambda row: row.ts)
    closes = np.array([row.close for row in ordered], dtype=float)
    volumes = np.array([row.volume for row in ordered], dtype=float)
    returns = log_returns(closes)
    if len(returns) < MIN_BARS - 1:
        return None
    hourly_vol = ewma_vol(returns)
    drift = shrunk_drift(returns, volumes)
    hist_vol = float(np.std(returns))
    scale = (hourly_vol / hist_vol) if hist_vol > 1e-12 else 1.0
    steps = max(1, int(round(horizon_hours)))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(returns), size=(n_paths, steps))
    sampled = returns[draws] * scale + drift
    log_paths = math.log(entry) + np.cumsum(sampled, axis=1)
    prices = np.exp(log_paths)
    hit_target = prices >= target
    hit_stop = prices <= stop
    never = steps + 1
    target_idx = np.where(hit_target.any(axis=1), hit_target.argmax(axis=1), never)
    stop_idx = np.where(hit_stop.any(axis=1), hit_stop.argmax(axis=1), never)
    same_bar = (target_idx == stop_idx) & (target_idx < never)
    target_first = (target_idx < stop_idx) & ~same_bar
    stop_first = (stop_idx < target_idx) | same_bar
    timeout = ~target_first & ~stop_first
    p_target = float(target_first.mean())
    p_stop = float(stop_first.mean())
    p_timeout = float(timeout.mean())
    # Tiny rounding residue stays a timeout so the three outcomes sum to 1.
    residue = 1.0 - (p_target + p_stop + p_timeout)
    p_timeout = max(0.0, p_timeout + residue)
    se = math.sqrt(max(p_target * (1.0 - p_target), 1e-12) / n_paths)
    lower_90 = max(0.0, p_target - 1.2815515655446004 * se)
    timeout_price = float(prices[timeout, -1].mean()) if timeout.any() else float(entry)
    return BracketForecast(
        p_target=p_target,
        p_stop=p_stop,
        p_timeout=p_timeout,
        lower_90=lower_90,
        hourly_vol=hourly_vol,
        drift_per_bar=drift,
        timeout_price=timeout_price,
        bars_used=len(ordered),
        paths=n_paths,
    )
