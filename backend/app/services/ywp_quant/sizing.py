"""Bankroll sizing — fractional Kelly under probability uncertainty."""

from __future__ import annotations

from typing import Any

from .odds import american_to_decimal


def kelly_fraction(probability: float, american_odds: float) -> float:
    """Full Kelly f* for a 1-unit stake at American odds."""
    p = min(max(float(probability), 1e-9), 1 - 1e-9)
    b = american_to_decimal(american_odds) - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - p
    f = (b * p - q) / b
    return max(0.0, f)


def fractional_kelly(
    probability: float,
    american_odds: float,
    *,
    fraction: float = 0.25,
    lower_90: float | None = None,
    uncertainty_haircut: bool = True,
) -> dict[str, Any]:
    """Quarter-Kelly by default; optionally size off the downside 90% probability."""
    base = kelly_fraction(probability, american_odds)
    p_use = float(probability)
    if uncertainty_haircut and lower_90 is not None:
        p_use = min(p_use, float(lower_90))
    conservative = kelly_fraction(p_use, american_odds)
    stake = conservative * max(0.0, min(float(fraction), 1.0))
    return {
        "full_kelly": round(base, 6),
        "conservative_kelly": round(conservative, 6),
        "fraction": fraction,
        "recommended_stake_pct": round(stake, 6),
        "probability_used": p_use,
        "note": (
            "Fractional Kelly on downside (lower-90) probability when available. "
            "Full Kelly is too aggressive under model error."
        ),
    }
