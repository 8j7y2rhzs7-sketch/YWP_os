"""Bridge YWP OS recommendations into the vendored ywp_quant engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.services.ywp_quant.engine import analyze_document

# Board path uses fewer sims for latency; audit endpoint can raise this.
BOARD_SIMULATIONS = 20_000
AUDIT_SIMULATIONS = 100_000


_UNVERIFIED_REASON_CODES = {
    "VERIFICATION_GAP",
    "RESEARCH_INCOMPLETE",
    "DEMO_DATA",
    "NO_INDEPENDENT_PROBABILITY",
    "DATA_QUALITY_BAD",
    "STALE_DATA",
}


def _direction(market_type: str, selection: str) -> str:
    text = f"{market_type} {selection}".lower()
    if " under " in f" {text} " or text.endswith(" under") or "_under" in text:
        return "under"
    if "yes" in text and "no" not in text:
        return "yes"
    return "over"


def _market_has_point_line(market_type: str, selection: str) -> bool:
    text = f"{market_type} {selection}".lower()
    if any(token in text for token in ("moneyline", "money line", "h2h")):
        return False
    padded = f" {text} "
    return " ml " not in padded and not text.endswith(" ml")


def _reason_codes(item: Any, snap: dict[str, Any]) -> set[str]:
    codes = {str(code) for code in (getattr(item, "reason_codes", None) or [])}
    raw = snap.get("reason_codes") or []
    if isinstance(raw, list):
        codes.update(str(code) for code in raw)
    return codes


def leg_verification_state(item: Any) -> str:
    """Return verified, unverified, or unknown from the stored leg.

    Unknown means the recommendation has no OS verification payload (older
    fixtures). Explicit SKIP / PARTIAL / VERIFICATION_GAP must not be treated
    as confirmed inputs.
    """
    snap = getattr(item, "snapshot", None) or {}
    if not isinstance(snap, dict):
        snap = {}
    pipe = snap.get("pipeline") if isinstance(snap.get("pipeline"), dict) else {}
    stages = pipe.get("stages") if isinstance(pipe, dict) else {}
    verification = stages.get("verification") if isinstance(stages, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    readiness = str(
        verification.get("readiness")
        or verification.get("verification_status")
        or snap.get("readiness")
        or ""
    ).upper()
    stage_status = str(verification.get("status") or "").lower()
    decision = str(getattr(item, "decision", "") or "").upper()
    threshold = str(snap.get("pipeline_threshold") or "").lower()
    codes = _reason_codes(item, snap)
    source = str(snap.get("probability_source") or getattr(item, "data_source", "") or "").lower()
    # Local YWP_DEMO_MODE fixtures may still price. Production never treats DEMO as confirmed.
    local_demo_play = bool(
        settings.demo_mode
        and decision in {"PLAY", "LEAN"}
        and (readiness == "DEMO" or "demo" in source or "synthetic" in source)
    )
    unverified = (not local_demo_play) and (
        readiness in {"PARTIAL", "DEMO"}
        or (stage_status == "partial" and readiness != "DEMO")
        or bool(codes & _UNVERIFIED_REASON_CODES)
        or decision in {"SKIP", "REVIEW", "WAIT"}
        or threshold == "reject"
    )
    if unverified:
        return "unverified"
    if readiness in {"VERIFIED", "DOUBLE_CLEARED"} or stage_status == "ok":
        return "verified"
    return "unknown"


def leg_blocks_card_qualify(item: Any) -> bool:
    """Rejected or unverified legs cannot make a card qualify."""
    return leg_verification_state(item) == "unverified"


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
    line = 0.5 if line is None else float(line)

    source_ts = getattr(item, "source_timestamp", None) or snap.get("price_timestamp")
    if isinstance(source_ts, datetime):
        ts = source_ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
    elif source_ts:
        ts = str(source_ts)
    else:
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    original_line = getattr(item, "line", None)
    state = leg_verification_state(item)
    decision = str(getattr(item, "decision", "") or "").upper()
    mode = str(getattr(item, "mode", None) or snap.get("mode") or "pregame").lower()
    if state == "unverified":
        event_confirmed = False
        line_confirmed = False
        role_confirmed = False
        verification_status = "unverified"
    elif state == "verified":
        event_confirmed = True
        line_confirmed = original_line is not None or not _market_has_point_line(
            market_type, selection
        )
        role_confirmed = True
        verification_status = "live" if mode == "live" else "pregame"
    else:
        # No stored verification payload. Keep the previous bridge so older PLAY
        # fixtures still price. Explicit SKIP / PARTIAL / VERIFICATION_GAP does not
        # land here.
        role_confirmed = bool(
            snap.get("starter_confirmed")
            or snap.get("role_confirmed")
            or decision in {"PLAY", "LEAN"}
        )
        event_confirmed = bool(role_confirmed or decision in {"PLAY", "LEAN", ""})
        line_confirmed = event_confirmed
        verification_status = "pregame" if event_confirmed else "unverified"
    verification = {
        "status": verification_status,
        "event_confirmed": event_confirmed,
        "line_confirmed": line_confirmed,
        "role_confirmed": role_confirmed,
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
                else (1.0 if role_confirmed else 0.88)
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
            p = float(item.adjusted_probability)
        except (TypeError, ValueError):
            p = float(
                snap.get("model_probability")
                or snap.get("pipeline_distribution", {}).get("tail_probability")
                or 0.5
            )
        uncertainty = max(
            0.06, min(0.18, float(getattr(item, "miss_by_one_risk", 0.2) or 0.2) * 0.2 + 0.06)
        )
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
