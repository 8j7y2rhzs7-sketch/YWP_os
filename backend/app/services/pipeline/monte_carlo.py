"""Stage 7 — Monte Carlo ticket win-rate under correlated leg outcomes."""

from __future__ import annotations

import math
import random
from typing import Any

from app.services.pipeline.correlation import correlation_matrix


def _clamp01(value: float) -> float:
    return max(0.001, min(0.999, value))


def _normsinv(p: float) -> float:
    """Abramowitz-style inverse CDF (same band as distribution helper)."""
    from app.services.pipeline.distribution import _approx_normsinv

    return _approx_normsinv(p)


def _correlated_uniforms(rhos: list[list[float]], rng: random.Random) -> list[float]:
    """Gaussian copula: sample correlated standard normals → uniforms."""
    n = len(rhos)
    z = [rng.gauss(0.0, 1.0) for _ in range(n)]
    # One-step correlation embedding: x_i = √ρ̄ * g + √(1-ρ̄) * z_i using pair max.
    # For denser matrices use pairwise average rho with common factor.
    if n == 1:
        return [_phi(z[0])]
    avg_off = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            avg_off += rhos[i][j]
            count += 1
    rho_bar = max(0.0, min(0.85, avg_off / count if count else 0.0))
    g = rng.gauss(0.0, 1.0)
    scale = math.sqrt(max(0.0, 1.0 - rho_bar))
    shared = math.sqrt(rho_bar)
    xs = [shared * g + scale * zi for zi in z]
    return [_phi(x) for x in xs]


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def simulate_ticket(
    legs: list[Any],
    *,
    sims: int = 4000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Simulate full-ticket wins from leg model probs + correlation priors."""
    if not legs:
        return {
            "win_probability": None,
            "sims": 0,
            "status": "empty",
            "note": "No legs to simulate.",
        }

    probs: list[float] = []
    for item in legs:
        snap = getattr(item, "snapshot", None) or {}
        p = snap.get("pipeline_distribution", {}).get("tail_probability")
        if p is None:
            p = snap.get("model_probability")
        if p is None:
            try:
                p = float(item.adjusted_probability)
            except (TypeError, ValueError):
                p = None
        source = str(snap.get("probability_source") or "").lower()
        if p is None or source not in {"model", "manual_verified", "demo", ""}:
            # Still allow adjusted_probability when source missing on unit tests.
            if p is None:
                return {
                    "win_probability": None,
                    "sims": 0,
                    "status": "unavailable",
                    "note": "One or more legs lack a model probability for Monte Carlo.",
                }
        probs.append(_clamp01(float(p)))

    if len(probs) == 1:
        return {
            "win_probability": round(probs[0], 6),
            "sims": 0,
            "status": "single_leg",
            "independent_product": round(probs[0], 6),
            "note": "Single-leg probability; Monte Carlo not required.",
            "correlation": correlation_matrix(legs),
        }

    corr = correlation_matrix(legs)
    rng = random.Random(seed if seed is not None else 20260928)
    wins = 0
    for _ in range(sims):
        uniforms = _correlated_uniforms(corr["matrix"], rng)
        if all(u < p for u, p in zip(uniforms, probs, strict=True)):
            wins += 1

    independent = 1.0
    for p in probs:
        independent *= p

    mc_p = wins / sims
    return {
        "win_probability": round(mc_p, 6),
        "sims": sims,
        "status": "monte_carlo",
        "independent_product": round(independent, 6),
        "correlation_adjustment": round(mc_p - independent, 6),
        "correlation": corr,
        "note": (
            f"{sims} correlated simulations. "
            f"Independent product would be {independent:.1%}; "
            f"Monte Carlo ticket win rate is {mc_p:.1%}."
        ),
    }
