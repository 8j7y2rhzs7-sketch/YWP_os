"""Orchestrate the nine-stage edge pipeline for a leg or ticket."""

from __future__ import annotations

from typing import Any

from app.services.pipeline.correlation import correlation_matrix
from app.services.pipeline.distribution import estimate_stat_distribution
from app.services.pipeline.market_math import compare_to_market
from app.services.pipeline.monte_carlo import simulate_ticket
from app.services.pipeline.threshold import map_decision_threshold

PIPELINE_STAGES = [
    {
        "id": 1,
        "key": "verification",
        "name": "Verification gate",
        "description": "Confirm event, player, opponent, market, line, availability, timestamp.",
    },
    {
        "id": 2,
        "key": "minutes_usage",
        "name": "Minutes / usage model",
        "description": "Project opportunity under normal, injury, foul-trouble, blowout.",
    },
    {
        "id": 3,
        "key": "stat_distribution",
        "name": "Stat distribution",
        "description": "Mean, variance, and tail probability — not merely the average.",
    },
    {
        "id": 4,
        "key": "context",
        "name": "Context adjustments",
        "description": "Opponent, pace, role, rest, venue, game state, lineups.",
    },
    {
        "id": 5,
        "key": "market_comparison",
        "name": "Market comparison",
        "description": "De-vigged implied probability versus model fair probability.",
    },
    {
        "id": 6,
        "key": "correlation",
        "name": "Correlation engine",
        "description": "How one result changes another inside the same game.",
    },
    {
        "id": 7,
        "key": "monte_carlo",
        "name": "Monte Carlo simulation",
        "description": "Simulate the full ticket thousands of times.",
    },
    {
        "id": 8,
        "key": "decision_threshold",
        "name": "Decision threshold",
        "description": "qualify / borderline / reject — no forced pick.",
    },
    {
        "id": 9,
        "key": "calibration",
        "name": "Calibration and backtesting",
        "description": "Brier, CLV, ROI, predicted vs actual, by market category.",
    },
]


def run_leg_pipeline(
    *,
    decision: str,
    confidence_score: int,
    edge: float,
    miss_by_one_risk: float,
    reason_codes: list[str],
    model_probability: float,
    american_odds: int,
    opposite_american_odds: int | None,
    line: float | None,
    is_over: bool,
    mean: float | None,
    sigma: float | None,
    hit_rate: float | None,
    cushion_scale: float,
    verification_status: str,
    role_stability: float | None,
    context_scores: dict[str, float | None],
    readiness: str,
) -> dict[str, Any]:
    """Produce per-leg stage outputs attached to recommendation.snapshot."""
    market = compare_to_market(
        model_probability=model_probability,
        american_odds=american_odds,
        opposite_american_odds=opposite_american_odds,
    )
    dist = estimate_stat_distribution(
        line=line,
        is_over=is_over,
        mean=mean,
        sigma=sigma,
        hit_rate=hit_rate,
        model_probability=model_probability,
        cushion_scale=cushion_scale,
    )
    threshold = map_decision_threshold(
        decision=decision,
        confidence_score=confidence_score,
        edge=edge,
        miss_by_one_risk=miss_by_one_risk,
        reason_codes=reason_codes,
    )

    minutes_status = "partial" if role_stability is not None else "missing"
    context_present = any(v is not None for v in context_scores.values())
    stages = {
        "verification": {
            "status": "ok" if verification_status in {"VERIFIED", "DOUBLE_CLEARED"} else "partial",
            "verification_status": verification_status,
            "readiness": readiness,
        },
        "minutes_usage": {
            "status": minutes_status,
            "role_stability": role_stability,
            "note": (
                "Full minutes model (injury/foul/blowout) is staged; "
                "role_stability is the current opportunity proxy."
            ),
        },
        "stat_distribution": dist,
        "context": {
            "status": "partial" if context_present else "missing",
            "scores": context_scores,
        },
        "market_comparison": market,
        "decision_threshold": threshold,
        # Correlation + MC are ticket-level; mark pending on the leg.
        "correlation": {"status": "ticket_level"},
        "monte_carlo": {"status": "ticket_level"},
        "calibration": {"status": "post_settle"},
    }
    return {
        "pipeline_version": "1.0",
        "stages": stages,
        "pipeline_threshold": threshold["threshold"],
        "fair_implied_probability": market["fair_implied_probability"],
        "edge_vs_fair": market["edge_vs_fair"],
        "distribution": dist,
        "threshold": threshold,
        "market_comparison": market,
    }


def run_ticket_pipeline(legs: list[Any], *, sims: int = 4000) -> dict[str, Any]:
    """Ticket-level stages 6–8."""
    corr = correlation_matrix(legs)
    mc = simulate_ticket(legs, sims=sims)
    thresholds = []
    for item in legs:
        snap = getattr(item, "snapshot", None) or {}
        thresholds.append(snap.get("pipeline_threshold") or "reject")
    if not legs or any(t == "reject" for t in thresholds):
        card_threshold = "reject"
    elif any(t == "borderline" for t in thresholds):
        card_threshold = "borderline"
    else:
        card_threshold = "qualify"
    return {
        "pipeline_version": "1.0",
        "correlation": corr,
        "monte_carlo": mc,
        "card_threshold": card_threshold,
        "force_pick": False,
        "joint_win_probability": mc.get("win_probability"),
        "joint_probability_status": mc.get("status", "unavailable"),
        "joint_probability_note": mc.get("note"),
    }
