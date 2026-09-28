"""Out-of-sample scoring: Brier, log loss, ECE, slope, CLV."""

from __future__ import annotations

import math
from typing import Any, Iterable


def brier_score(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probabilities, outcomes, strict=True))
    if not pairs:
        raise ValueError("At least one forecast is required")
    return sum((float(p) - int(y)) ** 2 for p, y in pairs) / len(pairs)


def log_loss(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    pairs = list(zip(probabilities, outcomes, strict=True))
    if not pairs:
        raise ValueError("At least one forecast is required")
    losses = []
    for p, y in pairs:
        clipped = min(max(float(p), 1e-12), 1 - 1e-12)
        losses.append(-(int(y) * math.log(clipped) + (1 - int(y)) * math.log(1 - clipped)))
    return sum(losses) / len(losses)


def calibration_table(
    probabilities: Iterable[float], outcomes: Iterable[int], bins: int = 10
) -> list[dict[str, float | int]]:
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in zip(probabilities, outcomes, strict=True):
        index = min(int(float(p) * bins), bins - 1)
        buckets[index].append((float(p), int(y)))
    result = []
    for index, bucket in enumerate(buckets):
        if bucket:
            result.append(
                {
                    "bin_low": index / bins,
                    "bin_high": (index + 1) / bins,
                    "count": len(bucket),
                    "mean_forecast": sum(p for p, _ in bucket) / len(bucket),
                    "hit_rate": sum(y for _, y in bucket) / len(bucket),
                }
            )
    return result


def expected_calibration_error(
    probabilities: Iterable[float], outcomes: Iterable[int], bins: int = 10
) -> float:
    """ECE = Σ (n_k/N) |acc_k - conf_k|."""
    table = calibration_table(probabilities, outcomes, bins=bins)
    n = sum(int(row["count"]) for row in table)
    if not n:
        return 0.0
    return sum(
        (int(row["count"]) / n) * abs(float(row["hit_rate"]) - float(row["mean_forecast"]))
        for row in table
    )


def brier_decomposition(
    probabilities: Iterable[float], outcomes: Iterable[int], bins: int = 10
) -> dict[str, float]:
    """Murphy decomposition: Reliability - Resolution + Uncertainty."""
    probs = [float(p) for p in probabilities]
    ys = [int(y) for y in outcomes]
    if not probs:
        raise ValueError("At least one forecast is required")
    n = len(probs)
    base_rate = sum(ys) / n
    uncertainty = base_rate * (1 - base_rate)
    table = calibration_table(probs, ys, bins=bins)
    reliability = 0.0
    resolution = 0.0
    for row in table:
        nk = int(row["count"])
        acc = float(row["hit_rate"])
        conf = float(row["mean_forecast"])
        reliability += (nk / n) * (acc - conf) ** 2
        resolution += (nk / n) * (acc - base_rate) ** 2
    return {
        "brier": brier_score(probs, ys),
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "ece": expected_calibration_error(probs, ys, bins=bins),
    }


def calibration_slope_intercept(
    probabilities: Iterable[float], outcomes: Iterable[int]
) -> dict[str, float]:
    """Simple OLS of outcome ~ forecast. Slope≈1, intercept≈0 ⇒ calibrated."""
    xs = [float(p) for p in probabilities]
    ys = [float(y) for y in outcomes]
    n = len(xs)
    if n < 3:
        return {"slope": 1.0, "intercept": 0.0, "n": n}
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    var_x = sum((x - x_mean) ** 2 for x in xs)
    if var_x <= 1e-12:
        return {"slope": 0.0, "intercept": y_mean, "n": n}
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    slope = cov / var_x
    intercept = y_mean - slope * x_mean
    return {"slope": slope, "intercept": intercept, "n": n}


def clv_from_probabilities(
    model_probability: float, closing_probability: float
) -> dict[str, float]:
    """Positive CLV ⇒ you beat the close (model got a better number than close)."""
    edge = float(closing_probability) - float(model_probability)
    # Sign convention for bettors who bet the model side: CLV = model_p - close_fair
    # when you locked model_p as your fair and close moved toward you.
    # Here report both.
    return {
        "model_minus_close": float(model_probability) - float(closing_probability),
        "close_minus_model": edge,
        "beat_close": float(model_probability) > float(closing_probability),
    }


def rich_grade_report(
    probabilities: list[float],
    outcomes: list[int],
    *,
    closing_probabilities: list[float | None] | None = None,
) -> dict[str, Any]:
    decomp = brier_decomposition(probabilities, outcomes)
    slope = calibration_slope_intercept(probabilities, outcomes)
    clvs = []
    if closing_probabilities:
        for p, c in zip(probabilities, closing_probabilities, strict=True):
            if c is not None:
                clvs.append(float(p) - float(c))
    return {
        **decomp,
        "log_loss": log_loss(probabilities, outcomes),
        "calibration_slope": slope["slope"],
        "calibration_intercept": slope["intercept"],
        "mean_clv_model_minus_close": (sum(clvs) / len(clvs)) if clvs else None,
        "calibration": calibration_table(probabilities, outcomes),
    }
