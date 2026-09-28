"""End-to-end orchestration and conservative decision policy."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .correlation import build_correlation, joint_probability
from .model import estimate_probability
from .odds import american_to_probability, probability_to_american, devig_two_way
from .validation import validate_leg, verification_score


DEFAULT_POLICY = {
    "minimum_leg_probability": 0.55,
    "minimum_leg_lower_90": 0.40,
    "minimum_effective_samples": 8.0,
    "minimum_data_quality": 0.65,
    "minimum_ticket_edge": 0.04,
    "minimum_ticket_lower_edge": 0.0,
    "maximum_legs": 4,
    "reject_unverified_correlation": True,
    "reject_unverified_inputs": True,
}


def _ticket_market_probability(ticket: dict[str, Any]) -> tuple[float | None, dict[str, Any]]:
    market = ticket.get("market", {})
    odds = market.get("american_odds")
    if odds is None:
        return None, {"warning": "NO_TICKET_PRICE"}
    raw = american_to_probability(float(odds))
    opposite = market.get("opposite_american_odds")
    if opposite is None:
        return raw, {"raw_probability": raw, "warning": "PRICE_NOT_DEVIGGED"}
    details = devig_two_way(float(odds), float(opposite))
    return details["fair_probability"], details


def analyze_document(document: dict[str, Any]) -> dict[str, Any]:
    policy = {**DEFAULT_POLICY, **document.get("policy", {})}
    raw_legs = deepcopy(document.get("legs", []))
    leg_results: list[dict[str, Any]] = []
    probabilities: list[float] = []
    lower_probabilities: list[float] = []
    upper_probabilities: list[float] = []
    blockers: list[str] = []

    for index, leg in enumerate(raw_legs):
        issues = validate_leg(leg)
        try:
            estimate = estimate_probability(leg, seed=int(document.get("seed", 7)) + index)
            result = estimate.as_dict()
            probabilities.append(estimate.probability)
            lower_probabilities.append(estimate.lower_90)
            upper_probabilities.append(estimate.upper_90)
        except (ValueError, TypeError, KeyError) as exc:
            result = {"error": str(exc)}
            blockers.append(f"MODEL_FAILURE:{leg.get('id', index)}")
        score = verification_score(leg, issues)
        if issues and policy["reject_unverified_inputs"]:
            blockers.extend(f"{leg.get('id', index)}:{issue}" for issue in issues)
        if result.get("effective_samples", 0) < policy["minimum_effective_samples"]:
            blockers.append(f"{leg.get('id', index)}:LOW_EFFECTIVE_SAMPLE_SIZE")
        if float(leg.get("data_quality", 0.0)) < policy["minimum_data_quality"]:
            blockers.append(f"{leg.get('id', index)}:LOW_DATA_QUALITY")
        if result.get("probability", 0) < policy["minimum_leg_probability"]:
            blockers.append(f"{leg.get('id', index)}:LEG_PROBABILITY_BELOW_THRESHOLD")
        if result.get("lower_90", 0) < policy["minimum_leg_lower_90"]:
            blockers.append(f"{leg.get('id', index)}:LEG_DOWNSIDE_TOO_LOW")
        leg_results.append({
            "id": leg.get("id"),
            "event_id": leg.get("event_id"),
            "market": leg.get("market"),
            "line": leg.get("line"),
            "direction": leg.get("direction"),
            "verification_score": score,
            "verification_issues": issues,
            "estimate": result,
        })

    ticket = document.get("ticket", {})
    if len(raw_legs) > int(policy["maximum_legs"]):
        blockers.append("TOO_MANY_LEGS")
    if len(probabilities) != len(raw_legs) or not probabilities:
        return {
            "engine_version": "0.1.0",
            "decision": "REJECT",
            "blockers": sorted(set(blockers or ["NO_VALID_LEGS"])),
            "legs": leg_results,
        }

    correlation, correlation_warnings = build_correlation(raw_legs, ticket)
    if policy["reject_unverified_correlation"] and any(w.startswith("UNVERIFIED_SAME_EVENT") for w in correlation_warnings):
        blockers.append("UNVERIFIED_SAME_EVENT_CORRELATION")
    simulations = int(ticket.get("simulations", 250_000))
    seed = int(document.get("seed", 7)) + 10_000
    joint = joint_probability(probabilities, correlation, simulations, seed)
    joint_lower = joint_probability(lower_probabilities, correlation, simulations, seed + 1)
    joint_upper = joint_probability(upper_probabilities, correlation, simulations, seed + 2)
    market_probability, market_details = _ticket_market_probability(ticket)
    edge = None if market_probability is None else joint - market_probability
    lower_edge = None if market_probability is None else joint_lower - market_probability
    if market_probability is None:
        blockers.append("NO_COMPARABLE_MARKET_PRICE")
    else:
        if edge < policy["minimum_ticket_edge"]:
            blockers.append("INSUFFICIENT_TICKET_EDGE")
        if lower_edge < policy["minimum_ticket_lower_edge"]:
            blockers.append("DOWNSIDE_EDGE_NOT_POSITIVE")

    decision = "REJECT" if blockers else "QUALIFY"
    return {
        "engine_version": "0.1.0",
        "decision": decision,
        "blockers": sorted(set(blockers)),
        "ticket": {
            "leg_count": len(raw_legs),
            "model_probability": joint,
            "probability_interval_90": [joint_lower, joint_upper],
            "fair_american_odds": probability_to_american(joint),
            "market_probability": market_probability,
            "market": market_details,
            "edge": edge,
            "lower_edge": lower_edge,
            "correlation_warnings": correlation_warnings,
            "correlation_matrix": correlation.round(4).tolist(),
            "simulations": simulations,
        },
        "legs": leg_results,
        "policy": policy,
        "method_notes": [
            "Probabilities are distributions with uncertainty, not confidence labels.",
            "Same-event dependence requires measured or explicitly supplied correlations.",
            "Qualification requires both data quality and value at the offered price.",
            "A rejected over does not imply that the under qualifies.",
        ],
    }
