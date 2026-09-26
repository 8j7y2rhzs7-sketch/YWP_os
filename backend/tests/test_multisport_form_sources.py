from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch

from app.services import espn_provider, readiness, sport_research
from app.services.live_generic_slate import _odds_only_research
from app.services.odds_provider import get_team_recent_form_from_scores


def _team_market_research(*, sweep_complete: bool = True) -> dict:
    return {
        "espn_game": {
            "home_team": "Home Club",
            "away_team": "Away Club",
            "venue": "Arena",
            "source_url": "https://example.test",
        },
        "home_form": {
            "verified": True,
            "l10": {"win_pct": 0.6, "avg_for": 100, "avg_against": 95},
            "l5": {"win_pct": 0.6},
            "source_url": "https://example.test/home",
        },
        "away_form": {
            "verified": True,
            "l10": {"win_pct": 0.4, "avg_for": 95, "avg_against": 100},
            "l5": {"win_pct": 0.4},
            "source_url": "https://example.test/away",
        },
        "injuries": {"verified": True, "home_out": 0, "away_out": 1},
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
            "sport_specific_sweep_complete": sweep_complete,
        },
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "n/a",
            "lineup": "n/a",
            "weather": "n/a",
            "venue": "confirmed",
            "bullpen": "n/a",
        },
        "source_urls": ["https://example.test"],
    }


def test_nba_verified_without_lineups_when_sweep_clears() -> None:
    candidate = sport_research.build_verified_candidate(
        sport="nba",
        league="NBA",
        candidate_id="nba-ml-home-1",
        event_id="evt-nba-1",
        event_name="Away Club @ Home Club",
        home_team="Home Club",
        away_team="Away Club",
        start_time=datetime.now(UTC),
        market_type="moneyline",
        selection="Home Club ML",
        odds=-130,
        line=None,
        thesis_key="thesis-home-ml",
        script_key="script-home-control",
        reason_codes=["CURRENT_FORM"],
        reasoning=["test"],
        research=_team_market_research(sweep_complete=True),
    )
    assert candidate.lineup_confirmed is False
    assert candidate.sport_specific_sweep_complete is True
    assert "confirmed lineup/starters" not in candidate.missing_fields
    assert "confirmed starters/roles" not in candidate.missing_fields
    assert readiness.candidate_readiness(candidate) == "VERIFIED"
    assert readiness.candidate_verification_gaps(candidate) == []


def test_mlb_full_game_clears_without_batting_orders() -> None:
    """ML/run-line/totals must not hard-block when battingOrder is not posted yet."""
    candidate = sport_research.build_verified_candidate(
        sport="mlb",
        league="MLB",
        candidate_id="mlb-ml-home-1",
        event_id="evt-mlb-1",
        event_name="Away Club @ Home Club",
        home_team="Home Club",
        away_team="Away Club",
        start_time=datetime.now(UTC),
        market_type="moneyline",
        selection="Home Club ML",
        odds=-130,
        line=None,
        thesis_key="thesis-home-ml",
        script_key="script-home-control",
        reason_codes=["CURRENT_FORM"],
        reasoning=["test"],
        research=_team_market_research(sweep_complete=True),
    )
    # build_verified_candidate still leaves lineup false for MLB research stubs
    candidate = candidate.model_copy(
        update={
            "lineup_confirmed": False,
            "starter_confirmed": True,
            "injuries_verified": True,
            "weather_verified": True,
            "motivation_rotation_verified": True,
            "market_movement_verified": True,
            "sport_specific_sweep_complete": True,
            "current_form_verified": True,
            "l5_l10_verified": True,
            "home_away_verified": True,
            "schedule_verified": True,
            "universe_scan_complete": True,
            "missing_fields": [],
            "source_status": {
                "schedule": "confirmed",
                "market": "confirmed",
                "current_form": "confirmed",
                "injuries": "confirmed",
                "starter": "confirmed",
                "lineup": "probable",
                "weather": "confirmed",
                "bullpen": "confirmed",
            },
        }
    )
    assert readiness.is_mlb_team_market(candidate) is True
    assert readiness.candidate_readiness(candidate) == "VERIFIED"
    assert not any("lineup" in gap.lower() for gap in readiness.candidate_verification_gaps(candidate))


def test_mlb_player_props_still_require_lineups() -> None:
    candidate = sport_research.build_verified_candidate(
        sport="mlb",
        league="MLB",
        candidate_id="mlb-prop-1",
        event_id="evt-mlb-1",
        event_name="Away Club @ Home Club",
        home_team="Home Club",
        away_team="Away Club",
        start_time=datetime.now(UTC),
        market_type="player_hits_over",
        selection="Star Batter Over 0.5 hits",
        odds=-110,
        line=0.5,
        thesis_key="thesis-hits",
        script_key="script-hits",
        reason_codes=["CURRENT_FORM"],
        reasoning=["test"],
        research=_team_market_research(sweep_complete=True),
    )
    candidate = candidate.model_copy(
        update={
            "lineup_confirmed": False,
            "missing_fields": ["confirmed batting orders"],
            "sport_specific_sweep_complete": False,
        }
    )
    gaps = readiness.candidate_verification_gaps(candidate)
    assert any("lineup" in gap.lower() or "batting" in gap.lower() for gap in gaps)
    assert readiness.candidate_readiness(candidate) == "PARTIAL"


def test_odds_only_research_marks_indoor_weather_na() -> None:
    research = _odds_only_research([], home_team="Boston Celtics", sport="nba")
    assert research["source_status"]["weather"] == "n/a"
    assert research["flags"]["weather_verified"] is True
    assert research["source_status"]["starter"] == "n/a"


def test_espn_early_season_threshold_covers_nba(monkeypatch) -> None:
    games = [
        {
            "date": f"2026-04-{day:02d}",
            "win": True,
            "score_for": 110,
            "score_against": 100,
        }
        for day in range(1, 4)
    ]

    def fake_completed(*, path, team_id, slate_date, season=None):
        return list(games) if season is None else []

    monkeypatch.setattr(espn_provider, "_completed_games_from_schedule", fake_completed)
    form = espn_provider.get_team_recent_form("nba", "13", date(2026, 10, 20))
    assert form["verified"] is True
    assert form["l5"]["games"] == 3


def test_odds_scores_form_verifies_with_three_games() -> None:
    scores = [
        {
            "completed": True,
            "commence_time": f"2026-09-{10 + i:02d}T00:00:00Z",
            "home_team": "Boston Celtics",
            "away_team": "New York Knicks",
            "scores": [
                {"name": "Boston Celtics", "score": "110"},
                {"name": "New York Knicks", "score": "100"},
            ],
        }
        for i in range(3)
    ]
    with patch("app.services.odds_provider.get_scores", return_value=scores):
        form = get_team_recent_form_from_scores(
            "nba", "Boston Celtics", date(2026, 9, 13)
        )
    assert form["verified"] is True
    assert form["l5"]["games"] == 3
