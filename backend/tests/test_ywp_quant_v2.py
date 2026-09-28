"""ywp_quant v0.2 — Shin de-vig, NegBin, t-copula, Kelly, calibration."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from app.services.ywp_quant.calibration import (
    brier_decomposition,
    calibration_slope_intercept,
    expected_calibration_error,
)
from app.services.ywp_quant.correlation import joint_probability, joint_probability_bundle
from app.services.ywp_quant.distributions import choose_family, overdispersion_ratio
from app.services.ywp_quant.engine import ENGINE_VERSION, analyze_document
from app.services.ywp_quant.model import estimate_probability
from app.services.ywp_quant.odds import devig_best, devig_multiway, devig_shin, expected_value
from app.services.ywp_quant.sizing import fractional_kelly


def test_engine_version_is_v2() -> None:
    assert ENGINE_VERSION.startswith("0.2")


def test_shin_devig_on_skewed_favorite() -> None:
    # Heavy favorite / dog — Shin should differ from multiplicative.
    shin = devig_shin(-400, 300)
    best = devig_best(-400, 300)
    assert 0.0 < shin["fair_probability"] < 1.0
    assert best["method"] in {"shin", "multiplicative"}
    assert "alternatives" in best


def test_multiway_devig_sums_to_one() -> None:
    # Classic 3-way soccer-ish book with juice.
    result = devig_multiway([150, 220, 200])
    fair = result["fair_probabilities"]
    assert abs(sum(fair) - 1.0) < 1e-9
    assert all(0.0 < p < 1.0 for p in fair)
    power = devig_multiway([150, 220, 200], method="power")
    assert abs(sum(power["fair_probabilities"]) - 1.0) < 1e-9


def test_overdispersion_chooses_negbin() -> None:
    # High variance count series.
    values = np.array([0, 2, 1, 8, 0, 12, 3, 15, 1, 9], dtype=float)
    assert overdispersion_ratio(values) > 1.35
    assert choose_family(values, count_like=True) == "negbin"


def test_minutes_mixture_and_negbin_estimate() -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    leg = {
        "id": "pts",
        "event_id": "e1",
        "market": "points",
        "direction": "over",
        "line": 19.5,
        "data_quality": 0.85,
        "verification": {
            "status": "pregame",
            "event_confirmed": True,
            "line_confirmed": True,
            "role_confirmed": True,
            "source_timestamp": now,
            "max_age_hours": 48,
        },
        "observation_groups": [
            {
                "name": "recent",
                "values": [22, 18, 25, 14, 30, 19, 21, 17, 28, 24],
                "weight": 1.0,
                "recency_halflife": 4.0,
            }
        ],
        "context": {
            "expected_minutes": 32.0,
            "baseline_minutes": 34.0,
            "blowout_probability": 0.25,
            "blowout_workload_multiplier": 0.78,
            "foul_trouble_probability": 0.12,
            "pace_multiplier": 1.03,
            "opponent_multiplier": 0.98,
            "availability_probability": 0.99,
        },
    }
    est = estimate_probability(leg, seed=11)
    assert est.family in {"negbin", "poisson", "normal"}
    assert est.minutes is not None
    assert 0.0 < est.probability < 1.0
    assert est.lower_90 <= est.probability <= est.upper_90


def test_student_t_copula_differs_with_dependence() -> None:
    corr = np.array([[1.0, 0.7], [0.7, 1.0]])
    bundle = joint_probability_bundle([0.6, 0.6], corr, simulations=40_000, seed=5)
    assert bundle["conservative"] <= max(bundle["gaussian"], bundle["student_t"]) + 1e-9
    indep = joint_probability([0.6, 0.6], np.eye(2), simulations=40_000, seed=5)
    assert abs(indep - 0.36) < 0.02


def test_fractional_kelly_and_ev() -> None:
    ev = expected_value(0.58, -110)
    assert ev > 0
    kelly = fractional_kelly(0.58, -110, fraction=0.25, lower_90=0.50)
    assert kelly["recommended_stake_pct"] >= 0
    assert kelly["recommended_stake_pct"] <= kelly["full_kelly"] + 1e-9


def test_calibration_metrics() -> None:
    probs = [0.1, 0.2, 0.4, 0.6, 0.8, 0.9]
    outs = [0, 0, 0, 1, 1, 1]
    decomp = brier_decomposition(probs, outs)
    assert "reliability" in decomp and "resolution" in decomp
    assert expected_calibration_error(probs, outs) >= 0
    slope = calibration_slope_intercept(probs, outs)
    assert "slope" in slope


def test_analyze_document_emits_v2_ticket_fields() -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    document = {
        "seed": 3,
        "ticket": {
            "market": {"american_odds": 240, "opposite_american_odds": -300},
            "simulations": 12_000,
            "correlations": [],
        },
        "legs": [
            {
                "id": "a",
                "event_id": "e1",
                "market": "ml",
                "direction": "yes",
                "line": 0.5,
                "data_quality": 0.9,
                "verification": {
                    "status": "pregame",
                    "event_confirmed": True,
                    "line_confirmed": True,
                    "role_confirmed": True,
                    "source_timestamp": now,
                    "max_age_hours": 48,
                },
                "direct_probability": {
                    "probability": 0.62,
                    "uncertainty": 0.05,
                    "effective_samples": 20,
                },
            },
            {
                "id": "b",
                "event_id": "e2",
                "market": "ml",
                "direction": "yes",
                "line": 0.5,
                "data_quality": 0.9,
                "verification": {
                    "status": "pregame",
                    "event_confirmed": True,
                    "line_confirmed": True,
                    "role_confirmed": True,
                    "source_timestamp": now,
                    "max_age_hours": 48,
                },
                "direct_probability": {
                    "probability": 0.60,
                    "uncertainty": 0.05,
                    "effective_samples": 20,
                },
            },
        ],
    }
    result = analyze_document(document)
    assert result["engine_version"].startswith("0.2")
    ticket = result["ticket"]
    assert "kelly" in ticket
    assert "expected_value" in ticket
    assert "model_probability_student_t" in ticket
    assert ticket["copula"] == "conservative_min_gaussian_t"
