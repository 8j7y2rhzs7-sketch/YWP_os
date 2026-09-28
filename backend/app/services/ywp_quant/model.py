"""Conservative empirical-Bayes model for threshold events."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np


@dataclass
class ProbabilityEstimate:
    probability: float
    lower_90: float
    upper_90: float
    projected_mean: float | None
    projected_sd: float | None
    effective_samples: float
    availability_probability: float
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pooled_summary(groups: list[dict[str, Any]]) -> tuple[float, float, float, list[str]]:
    means: list[float] = []
    variances: list[float] = []
    weights: list[float] = []
    warnings: list[str] = []
    overlap_seen: set[str] = set()
    for group in groups:
        values = np.asarray(group.get("values", []), dtype=float)
        if values.size < 2:
            continue
        raw_weight = max(0.0, min(float(group.get("weight", 1.0)), 1.0))
        effective_n = min(float(values.size), float(group.get("max_effective_n", 12.0))) * raw_weight
        overlap = group.get("overlap_group")
        if overlap and overlap in overlap_seen:
            effective_n *= 0.35
            warnings.append(f"OVERLAP_DISCOUNTED:{overlap}")
        if overlap:
            overlap_seen.add(overlap)
        means.append(float(values.mean()))
        variances.append(float(values.var(ddof=1)))
        weights.append(max(effective_n, 0.01))
    if not weights:
        raise ValueError("At least one observation group with two values is required")
    w = np.asarray(weights)
    m = np.asarray(means)
    mean = float(np.average(m, weights=w))
    within = float(np.average(np.asarray(variances), weights=w))
    between = float(np.average((m - mean) ** 2, weights=w))
    sd = max((within + between) ** 0.5, 0.25)
    return mean, sd, float(w.sum()), sorted(set(warnings))


def estimate_probability(leg: dict[str, Any], seed: int = 7) -> ProbabilityEstimate:
    direct = leg.get("direct_probability")
    if direct is not None:
        p = float(direct["probability"])
        uncertainty = float(direct.get("uncertainty", 0.10))
        return ProbabilityEstimate(
            probability=p,
            lower_90=max(0.001, p - uncertainty),
            upper_90=min(0.999, p + uncertainty),
            projected_mean=None,
            projected_sd=None,
            effective_samples=float(direct.get("effective_samples", 0)),
            availability_probability=float(leg.get("context", {}).get("availability_probability", 1.0)),
            warnings=["DIRECT_PROBABILITY_REQUIRES_EXTERNAL_CALIBRATION"],
        )

    mean, sd, effective_n, warnings = _pooled_summary(leg.get("observation_groups", []))
    context = leg.get("context", {})
    mean = (mean + float(context.get("mean_add", 0.0))) * float(context.get("mean_multiplier", 1.0))
    sd *= max(float(context.get("variance_multiplier", 1.0)), 0.25) ** 0.5
    availability = min(max(float(context.get("availability_probability", 1.0)), 0.0), 1.0)
    blowout_p = min(max(float(context.get("blowout_probability", 0.0)), 0.0), 1.0)
    blowout_workload = min(max(float(context.get("blowout_workload_multiplier", 0.78)), 0.1), 1.0)
    workload_mean = float(context.get("workload_multiplier", 1.0))
    workload_sd = max(float(context.get("workload_uncertainty", 0.05)), 0.0)
    quality = min(max(float(leg.get("data_quality", 0.75)), 0.1), 1.0)

    rng = np.random.default_rng(seed)
    posterior_draws = int(leg.get("posterior_draws", 800))
    outcomes_per_draw = int(leg.get("outcomes_per_draw", 300))
    # Low sample count and weak data widen the posterior instead of creating false confidence.
    mean_se = sd / max(effective_n * quality, 1.0) ** 0.5
    posterior_means = rng.normal(mean, mean_se, posterior_draws)
    posterior_sds = sd * rng.lognormal(0.0, 0.18 / quality, posterior_draws)
    workload = np.clip(rng.normal(workload_mean, workload_sd, (posterior_draws, 1)), 0.2, 1.5)
    blowout = rng.random((posterior_draws, outcomes_per_draw)) < blowout_p
    workload_matrix = workload * np.where(blowout, blowout_workload, 1.0)
    simulated = rng.normal(
        posterior_means[:, None] * workload_matrix,
        posterior_sds[:, None] * np.sqrt(np.maximum(workload_matrix, 0.2)),
    )
    line = float(leg["line"])
    direction = str(leg["direction"]).lower()
    hits = simulated > line if direction in {"over", "yes"} else simulated < line
    draw_probabilities = hits.mean(axis=1)
    probability = float(np.median(draw_probabilities))
    lower, upper = np.quantile(draw_probabilities, [0.05, 0.95])
    if effective_n < 8:
        warnings.append("LOW_EFFECTIVE_SAMPLE_SIZE")
    if quality < 0.7:
        warnings.append("LOW_DATA_QUALITY")
    if blowout_p > 0.2:
        warnings.append("BLOWOUT_MIXTURE_APPLIED")
    return ProbabilityEstimate(
        probability=probability,
        lower_90=float(lower),
        upper_90=float(upper),
        projected_mean=float(mean * workload_mean * (1 - blowout_p + blowout_p * blowout_workload)),
        projected_sd=float(sd),
        effective_samples=effective_n,
        availability_probability=availability,
        warnings=sorted(set(warnings)),
    )
