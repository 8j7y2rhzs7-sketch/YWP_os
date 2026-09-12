from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.schemas import CandidateInput
from app.services import kbo_provider, readiness, sport_research


def _candidate(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="kbo-ml-1",
        event_id="evt-kbo-1",
        event_name="SSG Landers @ Doosan Bears",
        sport="kbo",
        league="KBO",
        start_time=now,
        home_team="Doosan Bears",
        away_team="SSG Landers",
        market_type="moneyline",
        selection="Doosan Bears ML",
        line=None,
        american_odds=-140,
        estimated_probability=0.58,
        probability_source="model",
        variance=0.35,
        data_quality=0.7,
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
            "bullpen": "probable",
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
        thesis_key="kbo-doosan-ml",
        script_key="kbo-ssg-doosan",
        missing_fields=[],
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_kbo_readiness_does_not_require_lineups_or_bullpen() -> None:
    candidate = _candidate()
    assert readiness.candidate_verification_gaps(candidate) == []
    assert readiness.candidate_readiness(candidate) == "VERIFIED"


def test_mlb_still_requires_lineups(monkeypatch) -> None:
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


def test_kbo_form_from_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        kbo_provider,
        "get_scores",
        lambda **kwargs: [
            {
                "completed": True,
                "commence_time": "2026-09-08T10:00:00Z",
                "home_team": "Doosan Bears",
                "away_team": "LG Twins",
                "scores": [
                    {"name": "Doosan Bears", "score": "5"},
                    {"name": "LG Twins", "score": "2"},
                ],
            }
        ],
    )
    # Patch through the module used by get_team_recent_form
    monkeypatch.setattr(
        "app.services.kbo_provider.get_scores",
        lambda sport, days_from=3: [
            {
                "completed": True,
                "commence_time": "2026-09-08T10:00:00Z",
                "home_team": "Doosan Bears",
                "away_team": "LG Twins",
                "scores": [
                    {"name": "Doosan Bears", "score": "5"},
                    {"name": "LG Twins", "score": "2"},
                ],
            }
        ],
    )
    form = kbo_provider.get_team_recent_form("Doosan Bears", date(2026, 9, 9))
    assert form["verified"] is True
    assert form["l5"]["wins"] == 1


def test_kbo_research_can_clear_sweep(monkeypatch) -> None:
    monkeypatch.setattr(
        sport_research,
        "match_schedule_game",
        lambda *args, **kwargs: {
            "home_team": "Doosan Bears",
            "away_team": "SSG Landers",
            "venue": "Seoul ballpark",
            "city": "Seoul",
            "country": "KR",
            "indoor": False,
            "source_url": "https://the-odds-api.com/",
        },
    )
    monkeypatch.setattr(
        sport_research,
        "team_recent_form",
        lambda *args, **kwargs: {
            "verified": True,
            "l5": {"games": 2, "wins": 1, "losses": 1, "win_pct": 0.5, "avg_for": 4.0, "avg_against": 3.5, "totals": []},
            "l10": {"games": 2, "wins": 1, "losses": 1, "win_pct": 0.5, "avg_for": 4.0, "avg_against": 3.5, "totals": []},
            "source_url": "https://the-odds-api.com/",
        },
    )
    monkeypatch.setattr(
        sport_research,
        "league_injuries",
        lambda sport: {
            "verified": True,
            "by_team": {},
            "policy": "unsupported_feed_assumed_clear",
            "detail": "policy",
            "source_id": "the_odds_api_kbo",
        },
    )
    monkeypatch.setattr(
        sport_research,
        "search_venue_weather",
        lambda **kwargs: {"verified": True, "source_url": "https://open-meteo.com/"},
    )
    monkeypatch.setattr(
        sport_research,
        "search_market_consensus",
        lambda *args, **kwargs: {"verified": True, "book_count": 2, "detail": "2 books"},
    )
    monkeypatch.setattr(sport_research, "injuries_for_teams", lambda *a, **k: {"verified": False})

    research = sport_research.build_event_research(
        sport="kbo",
        slate_date=date(2026, 9, 9),
        home_team="Doosan Bears",
        away_team="SSG Landers",
        bookmakers=[
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Doosan Bears", "price": -140},
                            {"name": "SSG Landers", "price": 120},
                        ],
                    }
                ],
            }
        ],
    )
    flags = research["flags"]
    assert flags["schedule_verified"] is True
    assert flags["current_form_verified"] is True
    assert flags["injuries_verified"] is True
    assert flags["weather_verified"] is True
    assert flags["market_movement_verified"] is True
    assert flags["sport_specific_sweep_complete"] is True
    assert research["source_status"]["bullpen"] == "probable"

    candidate = sport_research.build_verified_candidate(
        sport="kbo",
        league="KBO",
        candidate_id="kbo-1",
        event_id="evt-1",
        event_name="SSG Landers @ Doosan Bears",
        home_team="Doosan Bears",
        away_team="SSG Landers",
        start_time=datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
        market_type="moneyline",
        selection="Doosan Bears ML",
        odds=-140,
        line=None,
        thesis_key="kbo-ml",
        script_key="kbo-game",
        reason_codes=["MATCHUP_EDGE"],
        reasoning=["test"],
        research=research,
    )
    assert readiness.candidate_readiness(candidate) == "VERIFIED"
