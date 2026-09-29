"""Empirical-Bayes / hierarchical-style model for threshold events.

v0.2 upgrades:
- Negative Binomial / Poisson outcome families when counts are overdispersed
- Explicit minutes / foul-trouble / blowout mixture
- Availability haircut on hit probability
- Richer estimate diagnostics (family, overdispersion, minutes mixture)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .distributions import (
    choose_family,
    minutes_mixture_means,
    overdispersion_ratio,
    sample_outcomes,
)


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
    family: str = "normal"
    overdispersion: float | None = None
    minutes: dict[str, Any] | None = None
    tail_mass_beyond_line: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pooled_summary(
    groups: list[dict[str, Any]],
) -> tuple[float, float, float, np.ndarray, list[str]]:
    means: list[float] = []
    variances: list[float] = []
    weights: list[float] = []
    all_values: list[float] = []
    warnings: list[str] = []
    overlap_seen: set[str] = set()
    for group in groups:
        values = np.asarray(group.get("values", []), dtype=float)
        if values.size < 2:
            continue
        raw_weight = max(0.0, min(float(group.get("weight", 1.0)), 1.0))
        # Recency weights: optional exponential decay index 0 = most recent.
        if group.get("recency_halflife"):
            half = max(float(group["recency_halflife"]), 0.5)
            idx = np.arange(values.size)
            decay = 0.5 ** (idx / half)
            values_w = values
            # Weighted mean/var via decay on the series order (assumes newest first).
            decay = decay / decay.sum()
            mean_g = float(np.dot(values_w, decay))
            var_g = float(
                np.dot((values_w - mean_g) ** 2, decay) * values.size / max(values.size - 1, 1)
            )
            effective_n = (
                min(float(values.size), float(group.get("max_effective_n", 12.0))) * raw_weight
            )
            means.append(mean_g)
            variances.append(max(var_g, 0.05))
        else:
            effective_n = (
                min(float(values.size), float(group.get("max_effective_n", 12.0))) * raw_weight
            )
            means.append(float(values.mean()))
            variances.append(float(values.var(ddof=1)))
        overlap = group.get("overlap_group")
        if overlap and overlap in overlap_seen:
            effective_n *= 0.35
            warnings.append(f"OVERLAP_DISCOUNTED:{overlap}")
        if overlap:
            overlap_seen.add(overlap)
        weights.append(max(effective_n, 0.01))
        all_values.extend(values.tolist())
    if not weights:
        raise ValueError("At least one observation group with two values is required")
    w = np.asarray(weights)
    m = np.asarray(means)
    mean = float(np.average(m, weights=w))
    within = float(np.average(np.asarray(variances), weights=w))
    between = float(np.average((m - mean) ** 2, weights=w))
    sd = max((within + between) ** 0.5, 0.25)
    return mean, sd, float(w.sum()), np.asarray(all_values, dtype=float), sorted(set(warnings))


def estimate_probability(leg: dict[str, Any], seed: int = 7) -> ProbabilityEstimate:
    direct = leg.get("direct_probability")
    if direct is not None:
        p = float(direct["probability"])
        uncertainty = float(direct.get("uncertainty", 0.10))
        availability = float(leg.get("context", {}).get("availability_probability", 1.0))
        p_avail = p * availability
        return ProbabilityEstimate(
            probability=p_avail,
            lower_90=max(0.001, p_avail - uncertainty),
            upper_90=min(0.999, p_avail + uncertainty),
            projected_mean=None,
            projected_sd=None,
            effective_samples=float(direct.get("effective_samples", 0)),
            availability_probability=availability,
            warnings=["DIRECT_PROBABILITY_REQUIRES_EXTERNAL_CALIBRATION"],
            family="direct",
        )

    mean, sd, effective_n, all_values, warnings = _pooled_summary(leg.get("observation_groups", []))
    context = leg.get("context", {})
    mean = (mean + float(context.get("mean_add", 0.0))) * float(context.get("mean_multiplier", 1.0))
    sd *= max(float(context.get("variance_multiplier", 1.0)), 0.25) ** 0.5

    # Pace / opponent context multipliers (explicit, not hidden).
    pace_mult = float(context.get("pace_multiplier", 1.0))
    opponent_mult = float(context.get("opponent_multiplier", 1.0))
    mean *= pace_mult * opponent_mult

    availability = min(max(float(context.get("availability_probability", 1.0)), 0.0), 1.0)
    blowout_p = min(max(float(context.get("blowout_probability", 0.0)), 0.0), 1.0)
    blowout_workload = min(max(float(context.get("blowout_workload_multiplier", 0.78)), 0.1), 1.0)
    foul_p = min(max(float(context.get("foul_trouble_probability", 0.0)), 0.0), 0.5)
    foul_mult = min(max(float(context.get("foul_trouble_minutes_multiplier", 0.85)), 0.2), 1.0)
    workload_mean = float(context.get("workload_multiplier", 1.0))
    workload_sd = max(float(context.get("workload_uncertainty", 0.05)), 0.0)
    quality = min(max(float(leg.get("data_quality", 0.75)), 0.1), 1.0)

    minutes_info = minutes_mixture_means(
        mean,
        expected_minutes=context.get("expected_minutes"),
        baseline_minutes=context.get("baseline_minutes"),
        blowout_probability=blowout_p,
        blowout_minutes_multiplier=blowout_workload,
        foul_trouble_probability=foul_p,
        foul_trouble_minutes_multiplier=foul_mult,
        injury_restriction_multiplier=float(context.get("injury_restriction_multiplier", 1.0)),
    )
    # Blend legacy workload_multiplier with minutes mixture.
    mean = 0.5 * (mean * workload_mean) + 0.5 * float(minutes_info["adjusted_mean"])

    count_like = str(leg.get("market_family", "count")).lower() != "continuous"
    family = choose_family(
        all_values,
        forced=leg.get("distribution_family"),
        count_like=count_like,
    )
    disp = overdispersion_ratio(all_values) if all_values.size else None
    if family == "negbin":
        warnings.append("NEGBIN_OVERDISPERSION")
    if family == "poisson":
        warnings.append("POISSON_COUNT_FAMILY")

    rng = np.random.default_rng(seed)
    posterior_draws = int(leg.get("posterior_draws", 1000))
    outcomes_per_draw = int(leg.get("outcomes_per_draw", 400))
    mean_se = sd / max(effective_n * quality, 1.0) ** 0.5
    posterior_means = rng.normal(mean, mean_se, posterior_draws)
    posterior_sds = sd * rng.lognormal(0.0, 0.18 / quality, posterior_draws)

    # Scenario mixture on the mean (blowout / foul / normal) via multinomial weights.
    weights = minutes_info["scenario_weights"]
    scenario = rng.choice(
        ["normal", "blowout", "foul_trouble"],
        size=(posterior_draws, outcomes_per_draw),
        p=[weights["normal"], weights["blowout"], weights["foul_trouble"]],
    )
    mult_map = minutes_info["scenario_multipliers"]
    scenario_mult = np.vectorize(mult_map.__getitem__)(scenario)
    # Also apply continuous workload noise.
    workload_noise = np.clip(rng.normal(1.0, workload_sd, (posterior_draws, 1)), 0.5, 1.5)
    mean_matrix = posterior_means[:, None] * scenario_mult * workload_noise
    sd_matrix = posterior_sds[:, None] * np.sqrt(np.maximum(scenario_mult, 0.2))

    simulated = sample_outcomes(
        rng,
        family=family,
        mean=mean_matrix,
        sd=sd_matrix,
        size=(posterior_draws, outcomes_per_draw),
    )

    line = float(leg["line"])
    direction = str(leg["direction"]).lower()
    hits = simulated > line if direction in {"over", "yes"} else simulated < line
    draw_probabilities = hits.mean(axis=1) * availability
    probability = float(np.median(draw_probabilities))
    lower, upper = np.quantile(draw_probabilities, [0.05, 0.95])
    tail = float(hits.mean())

    if effective_n < 8:
        warnings.append("LOW_EFFECTIVE_SAMPLE_SIZE")
    if quality < 0.7:
        warnings.append("LOW_DATA_QUALITY")
    if blowout_p > 0.2:
        warnings.append("BLOWOUT_MIXTURE_APPLIED")
    if foul_p > 0.1:
        warnings.append("FOUL_TROUBLE_MIXTURE_APPLIED")
    if availability < 0.98:
        warnings.append("AVAILABILITY_HAIRCUT")

    return ProbabilityEstimate(
        probability=probability,
        lower_90=float(lower),
        upper_90=float(upper),
        projected_mean=float(mean),
        projected_sd=float(sd),
        effective_samples=effective_n,
        availability_probability=availability,
        warnings=sorted(set(warnings)),
        family=family,
        overdispersion=None if disp is None else round(float(disp), 4),
        minutes=minutes_info,
        tail_mass_beyond_line=round(tail, 6),
    )
