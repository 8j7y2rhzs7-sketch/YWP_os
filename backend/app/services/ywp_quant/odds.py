"""American-odds conversion and two-way market de-vigging."""

from __future__ import annotations


def american_to_probability(odds: float) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)


def probability_to_american(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("Probability must be between zero and one")
    # At exactly 50%, prefer the conventional even-money representation: +100.
    if probability > 0.5:
        return -100.0 * probability / (1.0 - probability)
    return 100.0 * (1.0 - probability) / probability


def devig_two_way(side_odds: float, other_odds: float) -> dict[str, float]:
    side_raw = american_to_probability(side_odds)
    other_raw = american_to_probability(other_odds)
    overround = side_raw + other_raw
    return {
        "raw_probability": side_raw,
        "fair_probability": side_raw / overround,
        "overround": overround - 1.0,
    }
