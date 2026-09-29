from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from app.schemas import CandidateInput
from app.services import espn_provider, readiness
from app.services.live_generic_slate import _odds_only_research


def _nfl_candidate(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="nfl-ml-1",
        event_id="evt-nfl-1",
        event_name="Cincinnati Bengals @ Cleveland Browns",
        sport="nfl",
        league="NFL",
        start_time=now,
        home_team="Cleveland Browns",
        away_team="Cincinnati Bengals",
        market_type="moneyline",
        selection="Cleveland Browns ML",
        line=None,
        american_odds=-120,
        estimated_probability=0.55,
        probability_source="model",
        variance=0.3,
        data_quality=0.7,
        data_source="FACT_CASCADE+THE_ODDS_API",
        source_timestamp=now,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "n/a",
            "lineup": "n/a",
            "weather": "confirmed",
            "venue": "confirmed",
            "bullpen": "n/a",
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
        thesis_key="nfl-cle-ml",
        script_key="nfl-cin-cle",
        missing_fields=[],
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_nfl_readiness_does_not_require_lineups_or_starters() -> None:
    candidate = _nfl_candidate()
    assert readiness.candidate_verification_gaps(candidate) == []
    assert readiness.candidate_readiness(candidate) == "VERIFIED"


def test_nfl_na_source_labels_do_not_block_or_count_as_unknown() -> None:
    candidate = _nfl_candidate(
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "n/a",
            "lineup": "n/a",
            "weather": "confirmed",
            "venue": "confirmed",
            "bullpen": "n/a",
        }
    )
    gaps = readiness.candidate_verification_gaps(candidate)
    assert not any(g.startswith("source:") for g in gaps)
    unknowns = sum(
        1
        for value in candidate.source_status.values()
        if str(value).lower() == "unknown"
    )
    assert unknowns == 0


def test_odds_only_research_marks_team_market_lineups_na() -> None:
    research = _odds_only_research([], home_team="Cleveland Browns", sport="nfl")
    assert research["source_status"]["starter"] == "n/a"
    assert research["source_status"]["lineup"] == "n/a"
    assert research["source_status"]["bullpen"] == "n/a"


def test_espn_form_backfills_prior_season_when_current_thin() -> None:
    current = [
        {
            "date": "2026-09-07",
            "win": True,
            "score_for": 24,
            "score_against": 17,
        }
    ]
    prior = [
        {
            "date": f"2025-12-{day:02d}",
            "win": day % 2 == 0,
            "score_for": 20 + day,
            "score_against": 18,
        }
        for day in range(1, 8)
    ]

    def fake_completed(*, path, team_id, slate_date, season=None):
        assert path
        assert team_id
        assert slate_date
        return list(prior if season == 2025 else current)

    with patch.object(
        espn_provider, "_completed_games_from_schedule", side_effect=fake_completed
    ):
        form = espn_provider.get_team_recent_form(
            "nfl", "5", date(2026, 9, 12), last_n=10
        )

    assert form["verified"] is True
    assert form["prior_season_backfill"] is True
    assert form["current_season_games"] == 1
    assert form["l5"]["games"] == 5
    assert form["l10"]["games"] == 8
    assert "prior-season backfill" in form["detail"]
