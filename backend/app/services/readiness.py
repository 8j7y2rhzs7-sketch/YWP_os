from __future__ import annotations

from typing import Literal

from app.schemas import CandidateInput

Readiness = Literal["DEMO", "PARTIAL", "VERIFIED"]


COMMON_REQUIRED_CHECKS: tuple[tuple[str, str], ...] = (
    ("schedule_verified", "schedule"),
    ("universe_scan_complete", "full slate/player universe"),
    ("current_form_verified", "current form"),
    ("l5_l10_verified", "actual L5/L10"),
    ("lineup_confirmed", "confirmed lineup"),
    ("injuries_verified", "injuries/rest"),
    ("starter_confirmed", "starter/role"),
    ("motivation_rotation_verified", "motivation/rotation/workload"),
    ("home_away_verified", "home/away/travel"),
    ("market_movement_verified", "current market/line movement"),
    ("sport_specific_sweep_complete", "sport-specific strict-mode sweep"),
)

# KBO has no certified lineup/bullpen JSON feed (ESPN baseball/kbo unsupported).
# Full-game markets verify on Odds schedule/scores + weather + price consensus.
KBO_REQUIRED_CHECKS: tuple[tuple[str, str], ...] = (
    ("schedule_verified", "schedule"),
    ("universe_scan_complete", "full slate/player universe"),
    ("current_form_verified", "current form"),
    ("l5_l10_verified", "actual L5/L10"),
    ("injuries_verified", "injuries/rest"),
    ("home_away_verified", "home/away/travel"),
    ("market_movement_verified", "current market/line movement"),
    ("sport_specific_sweep_complete", "sport-specific strict-mode sweep"),
    ("weather_verified", "weather/venue conditions"),
)


def candidate_verification_gaps(candidate: CandidateInput) -> list[str]:
    sport_l = candidate.sport.lower()
    required = KBO_REQUIRED_CHECKS if sport_l == "kbo" else COMMON_REQUIRED_CHECKS
    gaps = [label for field, label in required if not bool(getattr(candidate, field))]

    if sport_l != "kbo" and sport_l in {"mlb", "nfl", "ncaaf", "soccer", "mls", "epl"} and not candidate.weather_verified:
        gaps.append("weather/venue conditions")

    # Only unknown labels on hard research channels block readiness.
    # "probable" / "n/a" are allowed while certified feeds catch up or are unsupported.
    hard_source_keys = {
        "schedule",
        "market",
        "current_form",
        "injuries",
        "starter",
    }
    # Bullpen is MLB-only until a certified KBO bullpen source exists.
    if sport_l in {"mlb", "baseball"}:
        hard_source_keys.add("bullpen")

    unknown_sources = [
        label
        for label, state in candidate.source_status.items()
        if state == "unknown" and label in hard_source_keys
    ]
    # KBO: starter/lineup sources are explicitly n/a — never treat as unknown blockers.
    if sport_l == "kbo":
        unknown_sources = [label for label in unknown_sources if label not in {"starter", "lineup", "bullpen"}]

    gaps.extend(f"source:{label}" for label in unknown_sources)

    if candidate.probability_source == "market_implied":
        gaps.append("independent model probability")

    if candidate.probability_source == "demo":
        gaps.append("real provider inputs")

    return list(dict.fromkeys([*candidate.missing_fields, *gaps]))


def candidate_readiness(candidate: CandidateInput) -> Readiness:
    source = candidate.data_source.upper()
    if candidate.probability_source == "demo" or "DEMO" in source or "SYNTHETIC" in source:
        return "DEMO"
    return "PARTIAL" if candidate_verification_gaps(candidate) else "VERIFIED"


def slate_readiness(candidates: list[CandidateInput]) -> Readiness:
    states = [candidate_readiness(candidate) for candidate in candidates]
    if not states or all(state == "DEMO" for state in states):
        return "DEMO"
    return "VERIFIED" if all(state == "VERIFIED" for state in states) else "PARTIAL"


def verification_summary(candidates: list[CandidateInput]) -> dict[str, object]:
    states = [candidate_readiness(candidate) for candidate in candidates]
    gap_map = {
        candidate.candidate_id: candidate_verification_gaps(candidate)
        for candidate in candidates
        if candidate_readiness(candidate) == "PARTIAL"
    }
    return {
        "readiness": slate_readiness(candidates),
        "candidate_count": len(candidates),
        "verified_count": states.count("VERIFIED"),
        "partial_count": states.count("PARTIAL"),
        "demo_count": states.count("DEMO"),
        "gaps_by_candidate": gap_map,
    }
