"""Stage 5 — market comparison with de-vigged fair probability."""

from __future__ import annotations

from typing import Any


def implied_from_american(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def devig_two_way(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Multiplicative de-vig for a two-way market. Returns fair probs for A and B."""
    raw_a = implied_from_american(odds_a)
    raw_b = implied_from_american(odds_b)
    total = raw_a + raw_b
    if total <= 0:
        return 0.5, 0.5
    return raw_a / total, raw_b / total


def compare_to_market(
    *,
    model_probability: float,
    american_odds: int,
    opposite_american_odds: int | None = None,
) -> dict[str, Any]:
    """Compare model fair p to market. Prefer de-vigged when opposite side exists."""
    raw_implied = implied_from_american(american_odds)
    if opposite_american_odds is not None:
        fair_implied, _opposite_fair = devig_two_way(american_odds, opposite_american_odds)
        status = "devigged_two_way"
        vig = max(0.0, (raw_implied + implied_from_american(opposite_american_odds)) - 1.0)
    else:
        # Conservative single-side proxy: assume ~4.5% two-way vig on US -110/-110 books.
        fair_implied = min(0.99, max(0.01, raw_implied / 1.045))
        status = "raw_implied_vig_proxy"
        vig = None

    edge = float(model_probability) - float(fair_implied)
    decimal_odds = american_to_decimal(american_odds)
    expected_value = float(model_probability) * (decimal_odds - 1.0) - (1.0 - float(model_probability))
    return {
        "status": status,
        "raw_implied_probability": round(raw_implied, 6),
        "fair_implied_probability": round(fair_implied, 6),
        "model_probability": round(float(model_probability), 6),
        "edge_vs_fair": round(edge, 6),
        "expected_value": round(expected_value, 6),
        "vig_estimate": round(vig, 6) if vig is not None else None,
        "opposite_american_odds": opposite_american_odds,
    }
