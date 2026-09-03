"""Protocol health must not fail a two-sided slate for weak-side AIN scores."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.schemas import CandidateInput
from app.services.protocols import run_protocol_health_check


def _candidate(**overrides: object) -> CandidateInput:
    base: dict[str, object] = {
        "candidate_id": "cand-home-ml",
        "event_id": "evt-away-at-home",
        "event_name": "Away @ Home",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "market_type": "moneyline",
        "market_period": "full_game",
        "selection": "Home ML",
        "american_odds": -110,
        "estimated_probability": 0.55,
        "probability_source": "model",
        "variance": 0.2,
        "data_quality": 0.9,
        "data_source": "MLB_STATS_API+THE_ODDS_API",
        "source_timestamp": datetime.now(UTC),
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "confirmed",
            "bullpen": "confirmed",
        },
        "schedule_verified": True,
        "universe_scan_complete": True,
        "current_form_verified": True,
        "l5_l10_verified": True,
        "lineup_confirmed": True,
        "injuries_verified": True,
        "weather_verified": True,
        "starter_confirmed": True,
        "motivation_rotation_verified": True,
        "home_away_verified": True,
        "market_movement_verified": True,
        "sport_specific_sweep_complete": True,
        "game_status": "PRE_GAME",
        "market_status": "OPEN",
        "matchup_score": 0.55,
        "script_alignment": 0.55,
        "multiple_paths_score": 0.7,
        "miss_by_one_count_l10": 2,
        "recent_hit_rate": 0.5,
        "average_cushion": 1.0,
        "ain_checks": {
            "recent_form_l5_l10": True,
            "situational_angles": True,
            "h2h_context": None,
        },
        "thesis_key": "thesis-home",
        "script_key": "script-home",
    }
    base.update(overrides)
    return CandidateInput.model_validate(base)


def test_two_sided_slate_does_not_fail_matchup_or_pace_ain() -> None:
    """Weak side of a market scores <0.5 by design; slate health must still clear."""
    db = SessionLocal()
    try:
        strong = _candidate(
            candidate_id="strong",
            selection="Home ML",
            matchup_score=0.62,
            script_alignment=0.62,
            thesis_key="thesis-home",
            script_key="script-home",
        )
        weak = _candidate(
            candidate_id="weak",
            selection="Away ML",
            estimated_probability=0.38,
            american_odds=150,
            matchup_score=0.38,
            script_alignment=0.38,
            thesis_key="thesis-away",
            script_key="script-away",
        )

        run = run_protocol_health_check(
            db,
            analysis_id="ain-fix",
            user_id=None,
            sport="mlb",
            candidates=[strong, weak],
        )
        by_key = {item["key"]: item["status"] for item in run.checks}
        assert by_key["matchup_edge"] == "PASS"
        assert by_key["pace_or_tempo"] == "PASS"
        assert run.status != "FAILED"
        assert by_key["matchup_edge"] != "FAIL"
        assert by_key["pace_or_tempo"] != "FAIL"
    finally:
        db.close()
