from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.schemas import CandidateInput
from app.services import decision_engine, readiness, sport_research


def _candidate(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="ncaaf-spread-1",
        event_id="evt-ncaaf-1",
        event_name="Richmond Spiders @ Delaware Blue Hens",
        sport="ncaaf",
        league="NCAAF",
        start_time=now,
        home_team="Delaware Blue Hens",
        away_team="Richmond Spiders",
        market_type="spread",
        selection="Richmond Spiders +33.5",
        line=Decimal("33.5"),
        american_odds=-110,
        estimated_probability=0.69,
        probability_source="model",
        variance=0.35,
        data_quality=0.72,
        data_source="FACT_CASCADE+THE_ODDS_API",
        source_timestamp=now,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "probable",
            "lineup": "probable",
            "weather": "confirmed",
            "venue": "confirmed",
        },
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=False,
        injuries_verified=True,
        weather_verified=True,
        starter_confirmed=False,
        motivation_rotation_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        thesis_key="ncaaf-richmond-spread",
        script_key="ncaaf-richmond-delaware",
        missing_fields=[],
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_ncaaf_readiness_does_not_require_lineups() -> None:
    candidate = _candidate()
    assert readiness.candidate_verification_gaps(candidate) == []
    assert readiness.candidate_readiness(candidate) == "VERIFIED"


def test_ncaaf_still_partial_without_form_or_injuries() -> None:
    candidate = _candidate(
        current_form_verified=False,
        l5_l10_verified=False,
        injuries_verified=False,
        sport_specific_sweep_complete=False,
        missing_fields=["current form / L5-L10", "injuries for both teams"],
    )
    gaps = readiness.candidate_verification_gaps(candidate)
    assert "current form" in gaps
    assert readiness.candidate_readiness(candidate) == "PARTIAL"


def test_mlb_still_requires_lineups_after_ncaaf_carve_out() -> None:
    candidate = _candidate(
        sport="mlb",
        league="MLB",
        lineup_confirmed=False,
        starter_confirmed=False,
        sport_specific_sweep_complete=False,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "unknown",
            "lineup": "unknown",
            "weather": "confirmed",
            "venue": "confirmed",
            "bullpen": "unknown",
        },
        missing_fields=["confirmed lineup"],
    )
    gaps = readiness.candidate_verification_gaps(candidate)
    assert "confirmed lineup" in gaps
    assert readiness.candidate_readiness(candidate) == "PARTIAL"


def test_build_verified_candidate_clears_ncaaf_sweep_without_lineups() -> None:
    research = {
        "espn_game": {
            "home_team": "Delaware Blue Hens",
            "away_team": "Richmond Spiders",
            "venue": "Delaware Stadium",
            "city": "Newark",
            "indoor": False,
            "source_url": "https://example.test/ncaaf",
        },
        "home_form": {
            "verified": True,
            "l10": {"win_pct": 0.4, "avg_for": 24, "avg_against": 31},
            "l5": {"win_pct": 0.4},
            "source_url": "https://example.test/home",
        },
        "away_form": {
            "verified": True,
            "l10": {"win_pct": 0.6, "avg_for": 28, "avg_against": 22},
            "l5": {"win_pct": 0.6},
            "source_url": "https://example.test/away",
        },
        "injuries": {"verified": True, "home_out": 0, "away_out": 0},
        "weather": {"verified": True, "detail": "clear"},
        "market": {"verified": True},
        "flags": {
            "schedule_verified": True,
            "current_form_verified": True,
            "l5_l10_verified": True,
            "lineup_confirmed": False,
            "injuries_verified": True,
            "weather_verified": True,
            "starter_confirmed": False,
            "motivation_rotation_verified": True,
            "home_away_verified": True,
            "market_movement_verified": True,
            "sport_specific_sweep_complete": True,
        },
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "probable",
            "lineup": "probable",
            "weather": "confirmed",
        },
        "source_urls": ["https://example.test/ncaaf"],
    }
    candidate = sport_research.build_verified_candidate(
        sport="ncaaf",
        league="NCAAF",
        candidate_id="ncaaf-richmond-spread",
        event_id="evt",
        event_name="Richmond Spiders @ Delaware Blue Hens",
        home_team="Delaware Blue Hens",
        away_team="Richmond Spiders",
        start_time=datetime.now(UTC),
        market_type="spread",
        selection="Richmond Spiders +33.5",
        odds=-110,
        line=Decimal("33.5"),
        thesis_key="thesis-richmond",
        script_key="script-richmond",
        reason_codes=["CURRENT_FORM"],
        reasoning=["test"],
        research=research,
    )
    assert candidate.lineup_confirmed is False
    assert candidate.sport_specific_sweep_complete is True
    assert float(candidate.data_quality) >= 0.65
    assert readiness.candidate_readiness(candidate) == "VERIFIED"
    evaluation = decision_engine.DecisionEngine().evaluate(candidate)
    assert "RESEARCH_INCOMPLETE" not in evaluation.reason_codes
    assert evaluation.decision != "SKIP" or "MISSING_DATA" not in evaluation.reason_codes
