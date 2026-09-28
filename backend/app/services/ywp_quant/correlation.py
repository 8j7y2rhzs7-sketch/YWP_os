"""Correlation validation and Gaussian-copula ticket simulation."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import norm


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


def build_correlation(legs: list[dict[str, Any]], ticket: dict[str, Any]) -> tuple[np.ndarray, list[str]]:
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


def joint_probability(probabilities: list[float], correlation: np.ndarray, simulations: int = 250_000, seed: int = 19) -> float:
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    thresholds = norm.ppf(p)
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(np.zeros(len(p)), correlation, size=simulations)
    return float(np.all(draws <= thresholds, axis=1).mean())
