"""Correlation validation and copula ticket simulation (Gaussian + Student-t)."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import norm
from scipy.stats import t as student_t


def nearest_correlation(matrix: np.ndarray) -> tuple[np.ndarray, bool]:
    symmetric = (matrix + matrix.T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    changed = bool(np.min(values) < 1e-8)
    values = np.clip(values, 1e-8, None)
    rebuilt = vectors @ np.diag(values) @ vectors.T
    scale = np.sqrt(np.diag(rebuilt))
    rebuilt = rebuilt / np.outer(scale, scale)
    np.fill_diagonal(rebuilt, 1.0)
    return rebuilt, changed


def build_correlation(
    legs: list[dict[str, Any]], ticket: dict[str, Any]
) -> tuple[np.ndarray, list[str]]:
    size = len(legs)
    matrix = np.eye(size)
    warnings: list[str] = []
    supplied: dict[tuple[str, str], float] = {}
    for item in ticket.get("correlations", []):
        key = tuple(sorted((str(item["leg_a"]), str(item["leg_b"]))))
        supplied[key] = float(item["rho"])
    for i in range(size):
        for j in range(i + 1, size):
            key = tuple(sorted((str(legs[i]["id"]), str(legs[j]["id"]))))
            if key in supplied:
                rho = float(np.clip(supplied[key], -0.95, 0.95))
                matrix[i, j] = matrix[j, i] = rho
            elif legs[i].get("event_id") == legs[j].get("event_id"):
                warnings.append(f"UNVERIFIED_SAME_EVENT_CORRELATION:{key[0]}:{key[1]}")
    matrix, changed = nearest_correlation(matrix)
    if changed:
        warnings.append("CORRELATION_MATRIX_PROJECTED_TO_PSD")
    return matrix, sorted(set(warnings))


def joint_probability(
    probabilities: list[float],
    correlation: np.ndarray,
    simulations: int = 250_000,
    seed: int = 19,
    *,
    copula: str = "gaussian",
    df: float = 5.0,
) -> float:
    """P(all hit) under a Gaussian or Student-t copula."""
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    rng = np.random.default_rng(seed)
    if copula == "t":
        # Multivariate-t via normal / chi2.
        z = rng.multivariate_normal(np.zeros(len(p)), correlation, size=simulations)
        chi = rng.chisquare(df, size=simulations)[:, None]
        t_draws = z * np.sqrt(df / chi)
        # Uniform via t CDF, then compare to p (same orientation as Gaussian version).
        u = student_t.cdf(t_draws, df)
        return float(np.all(u <= p, axis=1).mean())

    thresholds = norm.ppf(p)
    draws = rng.multivariate_normal(np.zeros(len(p)), correlation, size=simulations)
    return float(np.all(draws <= thresholds, axis=1).mean())


def joint_probability_bundle(
    probabilities: list[float],
    correlation: np.ndarray,
    simulations: int,
    seed: int,
) -> dict[str, float]:
    """Report both Gaussian and t-copula joints (tail dependence matters for parlays)."""
    g = joint_probability(probabilities, correlation, simulations, seed, copula="gaussian")
    t_joint = joint_probability(
        probabilities, correlation, simulations, seed + 17, copula="t", df=5.0
    )
    # Conservative ticket probability uses the more pessimistic copula.
    return {
        "gaussian": g,
        "student_t": t_joint,
        "conservative": min(g, t_joint),
    }
