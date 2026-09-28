"""Stage 3 — stat distribution (mean, variance, tail) from available research."""

from __future__ import annotations

import math
from typing import Any


def _normal_cdf(x: float, mean: float, sigma: float) -> float:
    if sigma <= 0:
        return 1.0 if x >= mean else 0.0
    z = (x - mean) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def estimate_stat_distribution(
    *,
    line: float | None,
    is_over: bool,
    mean: float | None,
    sigma: float | None = None,
    hit_rate: float | None = None,
    model_probability: float | None = None,
    cushion_scale: float = 3.0,
    family: str = "normal",
) -> dict[str, Any]:
    """Build a minimal distribution object for Monte Carlo + disclosure.

    Prefers an explicit mean/σ. Falls back to inverting a model probability
    around the line with a sport-prior σ when mean is missing.
    """
    prior_sigma = max(0.35, float(sigma) if sigma is not None else float(cushion_scale) * 0.55)
    working_mean = mean
    if working_mean is None and line is not None and model_probability is not None:
        # Invert Φ so P(over) ≈ model_probability under Normal(mean, prior_σ).
        p = min(0.98, max(0.02, float(model_probability)))
        # Approximate inverse erf via a simple rational-ish mapping for tails we care about.
        # For p≈0.5 → mean≈line; for higher over-prob → mean above line.
        z = _approx_normsinv(p if is_over else (1.0 - p))
        # P(X > line) = 1 - Φ(line; mean, σ) ⇒ mean = line + z*σ for over.
        working_mean = float(line) + z * prior_sigma if is_over else float(line) - z * prior_sigma

    if working_mean is None:
        return {
            "family": "unavailable",
            "mean": None,
            "variance": None,
            "sigma": None,
            "tail_probability": model_probability,
            "line": line,
            "direction": "over" if is_over else "under",
            "status": "unavailable",
            "note": "No mean or invertible model probability for a distribution.",
        }

    variance = prior_sigma**2
    tail = None
    if line is not None:
        over_p = 1.0 - _normal_cdf(float(line), float(working_mean), prior_sigma)
        tail = over_p if is_over else (1.0 - over_p)
        tail = min(0.98, max(0.02, tail))
    elif model_probability is not None:
        tail = float(model_probability)

    return {
        "family": family,
        "mean": round(float(working_mean), 4),
        "variance": round(float(variance), 4),
        "sigma": round(float(prior_sigma), 4),
        "tail_probability": round(float(tail), 6) if tail is not None else None,
        "empirical_hit_rate": round(float(hit_rate), 4) if hit_rate is not None else None,
        "line": float(line) if line is not None else None,
        "direction": "over" if is_over else "under",
        "status": "ok",
        "note": "Normal approximation from research mean/σ (or inverted model p).",
    }


def _approx_normsinv(p: float) -> float:
    """Cheap inverse standard-normal CDF for p in (0,1)."""
    p = min(0.999, max(0.001, p))
    # Beasley-Springer/Moro-inspired rational approximation (truncated).
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464858e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )
