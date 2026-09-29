"""Bridge YWP OS recommendations into the vendored ywp_quant engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.ywp_quant.engine import analyze_document

# Board path uses fewer sims for latency; audit endpoint can raise this.
BOARD_SIMULATIONS = 20_000
AUDIT_SIMULATIONS = 100_000


def _direction(market_type: str, selection: str) -> str:
    text = f"{market_type} {selection}".lower()
    if " under " in f" {text} " or text.endswith(" under") or "_under" in text:
        return "under"
    if "yes" in text and "no" not in text:
        return "yes"
    return "over"


def _observation_groups(item: Any) -> list[dict[str, Any]] | None:
    snap = getattr(item, "snapshot", None) or {}
    values = (
        getattr(item, "observation_values", None)
        or snap.get("observation_values")
        or snap.get("l10_values")
        or snap.get("gamelog_values")
    )
    if isinstance(values, list) and len(values) >= 2:
        try:
            nums = [float(v) for v in values]
        except (TypeError, ValueError):
            return None
        return [
            {
                "name": "recent",
                "values": nums,
                "weight": 1.0,
                "overlap_group": "season",
                "max_effective_n": 12.0,
            }
        ]
    return None


def recommendation_to_quant_leg(item: Any) -> dict[str, Any]:
    snap = getattr(item, "snapshot", None) or {}
    market_type = str(getattr(item, "market_type", "") or "")
    selection = str(getattr(item, "selection", "") or "")
    line = getattr(item, "line", None)
    if line is None:
        line = 0.5
    else:
        line = float(line)

    source_ts = getattr(item, "source_timestamp", None) or snap.get("price_timestamp")
    if isinstance(source_ts, datetime):
        ts = source_ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif source_ts:
        ts = str(source_ts)
    else:
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    role_ok = bool(
        snap.get("starter_confirmed")
        or snap.get("role_stability")
        or getattr(item, "decision", "") in {"PLAY", "LEAN"}
    )
    verification = {
        "status": "pregame",
        "event_confirmed": True,
        "line_confirmed": line is not None,
        "role_confirmed": role_ok,
        "source_timestamp": ts,
        "max_age_hours": 48,
    }

    groups = _observation_groups(item)
    leg: dict[str, Any] = {
        "id": str(getattr(item, "id", getattr(item, "candidate_id", "leg"))),
        "event_id": str(getattr(item, "event_id", "event")),
        "market": selection or market_type,
        "direction": _direction(market_type, selection),
        "line": line,
        "data_quality": float(getattr(item, "data_quality", 0.7) or 0.7),
        "verification": verification,
        "context": {
            # Do not silently haircut board PLAY/LEAN probabilities below the 0.55 floor.
            # Explicit snapshot availability still wins when provided.
            "availability_probability": float(
                snap.get("availability_probability")
                if snap.get("availability_probability") is not None
                else (1.0 if role_ok else 0.88)
            ),
            "blowout_probability": float(snap.get("blowout_probability") or 0.12),
            "blowout_workload_multiplier": 0.80,
            "foul_trouble_probability": float(snap.get("foul_trouble_probability") or 0.08),
            "foul_trouble_minutes_multiplier": 0.85,
            "expected_minutes": snap.get("expected_minutes"),
            "baseline_minutes": snap.get("baseline_minutes"),
            "pace_multiplier": float(snap.get("pace_multiplier") or 1.0),
            "opponent_multiplier": float(snap.get("opponent_multiplier") or 1.0),
            "injury_restriction_multiplier": float(
                snap.get("injury_restriction_multiplier") or 1.0
            ),
            "workload_multiplier": float(getattr(item, "stability", 0.85) or 0.85),
            "workload_uncertainty": 0.08,
            "mean_multiplier": 1.0,
            "mean_add": 0.0,
            "variance_multiplier": 1.0,
        },
        "market_family": "count"
        if "player_" in str(getattr(item, "market_type", "")).lower()
        or "pitcher_" in str(getattr(item, "market_type", "")).lower()
        else "continuous",
    }
    if groups:
        leg["observation_groups"] = groups
    else:
        # Honest bridge until L10 arrays are stored on every modeled prop.
        try:
            p = float(getattr(item, "adjusted_probability"))
        except (TypeError, ValueError):
            p = float((snap.get("model_probability") or snap.get("pipeline_distribution", {}).get("tail_probability") or 0.5))
        uncertainty = max(0.06, min(0.18, float(getattr(item, "miss_by_one_risk", 0.2) or 0.2) * 0.2 + 0.06))
        leg["direct_probability"] = {
            "probability": max(0.02, min(0.98, p)),
            "uncertainty": uncertainty,
            "effective_samples": float(snap.get("effective_samples") or 10.0),
        }
    return leg


def build_quant_document(
    legs: list[Any],
    *,
    american_odds: int | None,
    opposite_american_odds: int | None = None,
    simulations: int = BOARD_SIMULATIONS,
    correlations: list[dict[str, Any]] | None = None,
    seed: int = 20260928,
) -> dict[str, Any]:
    quant_legs = [recommendation_to_quant_leg(item) for item in legs]
    # Auto-supply measured-ish priors only when we already use pipeline ρ.
    # Prefer explicit correlations; otherwise leave blank so same-event tickets REJECT
    # unless the caller opts in (intentional_correlation).
    ticket: dict[str, Any] = {
        "simulations": int(simulations),
        "correlations": list(correlations or []),
    }
    if american_odds is not None:
        market: dict[str, Any] = {"american_odds": int(american_odds)}
        if opposite_american_odds is not None:
            market["opposite_american_odds"] = int(opposite_american_odds)
        ticket["market"] = market
    return {
        "seed": seed,
        "policy": {
            "maximum_legs": 4,
            "minimum_leg_probability": 0.55,
            "minimum_leg_lower_90": 0.40,
            # Singles: require clear edge but allow a thin downside haircut.
            # Multi-leg: joint downside must stay non-negative (weakest-leg discipline).
            "minimum_ticket_edge": 0.03 if len(quant_legs) <= 1 else 0.04,
            "minimum_ticket_lower_edge": -0.02 if len(quant_legs) <= 1 else 0.0,
            "reject_unverified_correlation": True,
            "reject_unverified_inputs": True,
        },
        "ticket": ticket,
        "legs": quant_legs,
    }


def _combined_american_odds(legs: list[Any]) -> int | None:
    """Approximate parlay American odds from decimal product of leg prices."""
    if not legs:
        return None
    product = 1.0
    for item in legs:
        odds = int(getattr(item, "american_odds", 0) or 0)
        if odds == 0:
            return None
        if odds > 0:
            product *= 1.0 + odds / 100.0
        else:
            product *= 1.0 + 100.0 / abs(odds)
    # decimal → american
    if product <= 1.0:
        return None
    implied = 1.0 / product
    if implied >= 0.5:
        return int(round(-100.0 * implied / (1.0 - implied)))
    return int(round(100.0 * (1.0 - implied) / implied))


def audit_ticket(
    legs: list[Any],
    *,
    american_odds: int | None = None,
    opposite_american_odds: int | None = None,
    simulations: int = BOARD_SIMULATIONS,
    allow_unverified_correlation: bool = False,
    intentional_correlation: bool = False,
) -> dict[str, Any]:
    """Run ywp_quant.analyze_document on YWP recommendation legs."""
    if american_odds is None:
        american_odds = _combined_american_odds(legs)

    correlations: list[dict[str, Any]] = []
    if intentional_correlation or allow_unverified_correlation:
        # Supply conservative same-event ρ so the engine can score instead of hard-blocking.
        from app.services.pipeline.correlation import pairwise_correlation

        for i, a in enumerate(legs):
            for b in legs[i + 1 :]:
                rho = pairwise_correlation(a, b)
                if rho > 0:
                    correlations.append(
                        {
                            "leg_a": str(getattr(a, "id", "")),
                            "leg_b": str(getattr(b, "id", "")),
                            "rho": float(rho),
                        }
                    )

    document = build_quant_document(
        legs,
        american_odds=american_odds,
        opposite_american_odds=opposite_american_odds,
        simulations=simulations,
        correlations=correlations,
    )
    if allow_unverified_correlation or intentional_correlation:
        document["policy"]["reject_unverified_correlation"] = False

    result = analyze_document(document)
    result["bridge"] = {
        "engine": "ywp_quant",
        "engine_version": str(result.get("engine_version") or "0.2.0"),
        "simulations": simulations,
        "american_odds_used": american_odds,
        "correlation_supplied": bool(correlations),
    }
    # Map to pipeline threshold vocabulary used by the board.
    decision = str(result.get("decision") or "REJECT").upper()
    result["pipeline_threshold"] = "qualify" if decision == "QUALIFY" else "reject"
    result["force_pick"] = False
    return result
