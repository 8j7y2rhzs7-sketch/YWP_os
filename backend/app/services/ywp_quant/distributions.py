"""Outcome families: Normal, Poisson, Negative Binomial with overdispersion test."""

from __future__ import annotations

from typing import Any

import numpy as np


def overdispersion_ratio(values: np.ndarray) -> float:
    if values.size < 3:
        return 1.0
    mean = float(values.mean())
    if mean <= 1e-9:
        return 1.0
    return float(values.var(ddof=1) / mean)


def choose_family(
    values: np.ndarray,
    *,
    forced: str | None = None,
    count_like: bool = True,
) -> str:
    if forced in {"normal", "poisson", "negbin"}:
        return forced
    if not count_like:
        return "normal"
    # Integer-ish counts with overdispersion → NegBin; else Poisson; continuous → Normal.
    nearly_int = np.mean(np.abs(values - np.round(values)) < 1e-6) > 0.8
    if not nearly_int:
        return "normal"
    ratio = overdispersion_ratio(values)
    if ratio > 1.35:
        return "negbin"
    return "poisson"


def sample_outcomes(
    rng: np.random.Generator,
    *,
    family: str,
    mean: np.ndarray,
    sd: np.ndarray,
    size: tuple[int, int],
) -> np.ndarray:
    """Sample outcome matrix shaped (posterior_draws, outcomes_per_draw)."""
    mean = np.maximum(mean, 1e-6)
    if family == "poisson":
        # Broadcast mean across outcomes.
        lam = np.broadcast_to(mean, size)
        return rng.poisson(lam).astype(float)
    if family == "negbin":
        # Parameterize by mean μ and variance μ + μ²/k  ⇒ k = μ² / (var - μ).
        # Use sd² as target variance when available.
        var = np.maximum(sd**2, mean * 1.05)
        # k = μ² / (var - μ)
        excess = np.maximum(var - mean, 1e-6)
        k = np.maximum(mean**2 / excess, 0.25)
        # numpy negbin uses number of failures until n successes; p = k/(k+μ)
        p = k / (k + mean)
        n = k
        n_b = np.broadcast_to(n, size)
        p_b = np.broadcast_to(p, size)
        return rng.negative_binomial(n_b, p_b).astype(float)
    # Normal (continuous props / margins)
    mean_b = np.broadcast_to(mean, size)
    sd_b = np.broadcast_to(np.maximum(sd, 0.05), size)
    return rng.normal(mean_b, sd_b)


def minutes_mixture_means(
    base_mean: float,
    *,
    expected_minutes: float | None,
    baseline_minutes: float | None,
    blowout_probability: float,
    blowout_minutes_multiplier: float,
    foul_trouble_probability: float = 0.0,
    foul_trouble_minutes_multiplier: float = 0.85,
    injury_restriction_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Translate minutes / usage scenarios into a mean multiplier mixture."""
    if expected_minutes and baseline_minutes and baseline_minutes > 0:
        minutes_mult = expected_minutes / baseline_minutes
    else:
        minutes_mult = 1.0
    minutes_mult *= max(0.2, min(1.5, injury_restriction_multiplier))

    # Mixture: normal / blowout / foul trouble (exclusive priority blowout > foul > normal).
    p_blow = min(max(blowout_probability, 0.0), 0.95)
    p_foul = min(max(foul_trouble_probability, 0.0), 1.0 - p_blow)
    p_norm = max(0.0, 1.0 - p_blow - p_foul)

    mult_blow = minutes_mult * blowout_minutes_multiplier
    mult_foul = minutes_mult * foul_trouble_minutes_multiplier
    mult_norm = minutes_mult

    expected_mult = p_norm * mult_norm + p_blow * mult_blow + p_foul * mult_foul
    return {
        "minutes_multiplier": minutes_mult,
        "expected_mean_multiplier": expected_mult,
        "scenario_weights": {
            "normal": p_norm,
            "blowout": p_blow,
            "foul_trouble": p_foul,
        },
        "scenario_multipliers": {
            "normal": mult_norm,
            "blowout": mult_blow,
            "foul_trouble": mult_foul,
        },
        "adjusted_mean": base_mean * expected_mult,
    }
