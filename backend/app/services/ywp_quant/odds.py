"""American-odds conversion and institutional-grade de-vigging.

Methods:
- multiplicative (normalize raw implied)
- power (odds-ratio power that balances favorites/dogs)
- Shin (accounts for insider-trading share on skewed books)
"""

from __future__ import annotations

from typing import Any


def american_to_probability(odds: float) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)


def probability_to_american(probability: float) -> float:
    if not 0.0 < probability < 1.0:
        raise ValueError("Probability must be between zero and one")
    if probability > 0.5:
        return -100.0 * probability / (1.0 - probability)
    return 100.0 * (1.0 - probability) / probability


def decimal_to_american(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must exceed 1")
    if decimal_odds >= 2.0:
        return 100.0 * (decimal_odds - 1.0)
    return -100.0 / (decimal_odds - 1.0)


def american_to_decimal(odds: float) -> float:
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def expected_value(model_probability: float, american_odds: float) -> float:
    """EV per unit stake at American odds."""
    decimal = american_to_decimal(american_odds)
    p = float(model_probability)
    return p * (decimal - 1.0) - (1.0 - p)


def devig_multiplicative(side_odds: float, other_odds: float) -> dict[str, float]:
    side_raw = american_to_probability(side_odds)
    other_raw = american_to_probability(other_odds)
    overround = side_raw + other_raw
    return {
        "method": "multiplicative",
        "raw_probability": side_raw,
        "fair_probability": side_raw / overround,
        "overround": overround - 1.0,
    }


def devig_two_way(side_odds: float, other_odds: float) -> dict[str, float]:
    """Backward-compatible alias → multiplicative."""
    result = devig_multiplicative(side_odds, other_odds)
    # Preserve legacy keys used by v0.1 callers.
    return {
        "raw_probability": result["raw_probability"],
        "fair_probability": result["fair_probability"],
        "overround": result["overround"],
        "method": "multiplicative",
    }


def devig_power(side_odds: float, other_odds: float, *, tol: float = 1e-10) -> dict[str, float]:
    """Power method: find k such that q_i^k sum to 1."""
    raw = [american_to_probability(side_odds), american_to_probability(other_odds)]
    overround = sum(raw) - 1.0
    # Binary search for exponent k.
    low, high = 0.5, 3.0
    for _ in range(80):
        mid = (low + high) / 2.0
        total = raw[0] ** mid + raw[1] ** mid
        if abs(total - 1.0) < tol:
            break
        if total > 1.0:
            low = mid
        else:
            high = mid
    k = (low + high) / 2.0
    powered = [r**k for r in raw]
    total = sum(powered)
    fair = powered[0] / total
    return {
        "method": "power",
        "raw_probability": raw[0],
        "fair_probability": fair,
        "overround": overround,
        "power_k": k,
    }


def devig_shin(side_odds: float, other_odds: float, *, tol: float = 1e-12) -> dict[str, float]:
    """Shin (1993) de-vig — better on skewed favorites with insider share z."""
    q = [american_to_probability(side_odds), american_to_probability(other_odds)]
    overround = sum(q) - 1.0

    def _total(z: float) -> float:
        # p_i = (sqrt(z^2 + 4(1-z) q_i^2 / Σq) - z) / (2(1-z))
        s = sum(q)
        terms = []
        for qi in q:
            root = (z * z + 4.0 * (1.0 - z) * (qi * qi) / s) ** 0.5
            terms.append((root - z) / (2.0 * (1.0 - z)))
        return sum(terms)

    # z in (0, 1); search so Σp = 1.
    low, high = 0.0, 0.5
    for _ in range(100):
        mid = (low + high) / 2.0
        total = _total(mid)
        if abs(total - 1.0) < tol:
            z = mid
            break
        if total > 1.0:
            low = mid
        else:
            high = mid
    else:
        z = (low + high) / 2.0

    s = sum(q)
    root = (z * z + 4.0 * (1.0 - z) * (q[0] * q[0]) / s) ** 0.5
    fair = (root - z) / (2.0 * (1.0 - z)) if z < 1.0 else q[0] / s
    return {
        "method": "shin",
        "raw_probability": q[0],
        "fair_probability": float(fair),
        "overround": overround,
        "shin_z": float(z),
    }


def devig_best(side_odds: float, other_odds: float) -> dict[str, Any]:
    """Return Shin as primary (skew-aware), with multiplicative/power comparables."""
    multi = devig_multiplicative(side_odds, other_odds)
    power = devig_power(side_odds, other_odds)
    shin = devig_shin(side_odds, other_odds)
    # Prefer Shin when overround is material or market is skewed.
    skew = abs(multi["raw_probability"] - 0.5)
    primary = shin if (multi["overround"] > 0.02 or skew > 0.12) else multi
    return {
        **primary,
        "alternatives": {
            "multiplicative": multi["fair_probability"],
            "power": power["fair_probability"],
            "shin": shin["fair_probability"],
        },
        "power_k": power.get("power_k"),
        "shin_z": shin.get("shin_z"),
    }


def vig_proxy_fair(side_odds: float, assumed_overround: float = 0.045) -> dict[str, float]:
    """When only one side is quoted, peel a conservative assumed two-way overround."""
    raw = american_to_probability(side_odds)
    fair = min(0.99, max(0.01, raw / (1.0 + assumed_overround)))
    return {
        "method": "vig_proxy",
        "raw_probability": raw,
        "fair_probability": fair,
        "overround": assumed_overround,
    }


def devig_multiway(american_odds: list[float], *, method: str = "multiplicative") -> dict[str, Any]:
    """De-vig an n-way market (3-way ML, futures bucket, props with push).

    Returns fair probabilities for every outcome in input order.
    ``method``: multiplicative (default) or power.
    """
    if len(american_odds) < 2:
        raise ValueError("Need at least two outcomes to de-vig")
    raw = [american_to_probability(float(o)) for o in american_odds]
    overround = sum(raw) - 1.0
    if method == "power":
        low, high = 0.5, 4.0
        for _ in range(80):
            mid = (low + high) / 2.0
            total = sum(r**mid for r in raw)
            if abs(total - 1.0) < 1e-10:
                break
            if total > 1.0:
                low = mid
            else:
                high = mid
        k = (low + high) / 2.0
        powered = [r**k for r in raw]
        total = sum(powered)
        fair = [p / total for p in powered]
        return {
            "method": "power",
            "raw_probabilities": raw,
            "fair_probabilities": fair,
            "overround": overround,
            "power_k": k,
        }
    # Multiplicative normalize.
    total = sum(raw)
    fair = [r / total for r in raw]
    return {
        "method": "multiplicative",
        "raw_probabilities": raw,
        "fair_probabilities": fair,
        "overround": overround,
    }
