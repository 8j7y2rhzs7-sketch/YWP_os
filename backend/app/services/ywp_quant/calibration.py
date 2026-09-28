"""Out-of-sample scoring helpers."""

from __future__ import annotations

import math
from typing import Iterable


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


def calibration_table(probabilities: Iterable[float], outcomes: Iterable[int], bins: int = 10) -> list[dict[str, float | int]]:
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in zip(probabilities, outcomes, strict=True):
        index = min(int(float(p) * bins), bins - 1)
        buckets[index].append((float(p), int(y)))
    result = []
    for index, bucket in enumerate(buckets):
        if bucket:
            result.append({
                "bin_low": index / bins,
                "bin_high": (index + 1) / bins,
                "count": len(bucket),
                "mean_forecast": sum(p for p, _ in bucket) / len(bucket),
                "hit_rate": sum(y for _, y in bucket) / len(bucket),
            })
    return result
