from __future__ import annotations

from datetime import date

from app.services import cfbd_provider, espn_provider, facts_cascade, ncaa_provider
from app.services import research_searchers
from app.services.trusted_sources import sources_for, trusted_sources_manifest


def test_trusted_sources_include_validated_free_providers() -> None:
    ids = {item["id"] for item in trusted_sources_manifest()["sources"]}
    for required in {
        "college_football_data",
        "balldontlie",
        "football_data_org",
        "nba_stats_cdn",
        "ncaa_data_api",
        "nws_weather_gov",
        "open_meteo",
        "espn_site_api",
        "nhl_web_api",
        "mlb_stats_api",
        "the_odds_api",
    }:
        assert required in ids

    ncaaf_form = {item["id"] for item in sources_for("form", "ncaaf")}
    assert "college_football_data" in ncaaf_form
    assert "espn_site_api" in ncaaf_form

    ncaaf_schedule = {item["id"] for item in sources_for("schedule", "ncaaf")}
    assert "ncaa_data_api" in ncaaf_schedule
    assert "college_football_data" in ncaaf_schedule

    ncaaf_weather = {item["id"] for item in sources_for("weather", "ncaaf")}
    assert "nws_weather_gov" in ncaaf_weather
    assert "open_meteo" in ncaaf_weather

    ncaa_meta = next(s for s in trusted_sources_manifest()["sources"] if s["id"] == "ncaa_data_api")
    nws_meta = next(s for s in trusted_sources_manifest()["sources"] if s["id"] == "nws_weather_gov")
    assert ncaa_meta["tier"] == "secondary"
    assert nws_meta["tier"] == "secondary"


def test_espn_name_overlap_ignores_weak_state_token() -> None:
    assert espn_provider._name_overlap("Michigan State Spartans", "Ohio State Buckeyes") == 0
    assert espn_provider._name_overlap("Richmond Spiders", "Richmond Spiders") >= 2
    assert espn_provider._name_overlap("Alabama Crimson Tide", "Alabama") >= 1


def test_espn_injury_lookup_requires_real_identity() -> None:
    feed = {
        "verified": True,
        "by_team": {
            "Michigan State Spartans": [{"status": "Out", "name": "QB"}],
            "Ohio State Buckeyes": [],
        },
    }
    matched = espn_provider.injuries_for_teams(
        feed, "Michigan State Spartans", "Ohio State Buckeyes"
    )
    assert matched["verified"] is True
    assert matched["home_out"] == 1
    weak = espn_provider.injuries_for_teams(feed, "Penn State Nittany Lions", "Ohio State Buckeyes")
    assert weak["home_matched"] is False


def test_cfbd_form_builds_from_completed_games(monkeypatch) -> None:
    monkeypatch.setattr(cfbd_provider, "cfbd_configured", lambda: True)
    monkeypatch.setattr(
        cfbd_provider,
        "resolve_team_name",
        lambda label, year=None: "Richmond",
    )
    monkeypatch.setattr(
        cfbd_provider,
        "get_games",
        lambda **kwargs: [
            {
                "completed": True,
                "startDate": "2026-09-01T00:00:00.000Z",
                "homeTeam": "Richmond",
                "awayTeam": "Maine",
                "homePoints": 31,
                "awayPoints": 10,
            },
            {
                "completed": True,
                "startDate": "2026-09-08T00:00:00.000Z",
                "homeTeam": "Delaware",
                "awayTeam": "Richmond",
                "homePoints": 14,
                "awayPoints": 24,
            },
            {
                "completed": True,
                "startDate": "2026-08-25T00:00:00.000Z",
                "homeTeam": "Richmond",
                "awayTeam": "VMI",
                "homePoints": 28,
                "awayPoints": 7,
            },
            {
                "completed": True,
                "startDate": "2026-08-18T00:00:00.000Z",
                "homeTeam": "Richmond",
                "awayTeam": "Bryant",
                "homePoints": 21,
                "awayPoints": 17,
            },
            {
                "completed": True,
                "startDate": "2026-08-11T00:00:00.000Z",
                "homeTeam": "Towson",
                "awayTeam": "Richmond",
                "homePoints": 20,
                "awayPoints": 27,
            },
        ],
    )
    form = cfbd_provider.get_team_recent_form("Richmond Spiders", date(2026, 9, 11))
    assert form["verified"] is True
    assert form["source_id"] == "college_football_data"
    assert form["l5"]["games"] == 5
    assert form["l5"]["wins"] == 5


def test_facts_cascade_falls_back_to_cfbd_form(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.facts_cascade.espn_provider.get_team_recent_form",
        lambda *args, **kwargs: {"verified": False, "source_id": "espn_site_api"},
    )
    monkeypatch.setattr(
        "app.services.facts_cascade.cfbd_provider.get_team_recent_form",
        lambda *args, **kwargs: {
            "verified": True,
            "source_id": "college_football_data",
            "l5": {
                "games": 5,
                "wins": 3,
                "losses": 2,
                "win_pct": 0.6,
                "avg_for": 24,
                "avg_against": 20,
                "totals": [],
            },
            "l10": {
                "games": 5,
                "wins": 3,
                "losses": 2,
                "win_pct": 0.6,
                "avg_for": 24,
                "avg_against": 20,
                "totals": [],
            },
            "games": [],
        },
    )
    form = facts_cascade.team_recent_form(
        "ncaaf",
        None,
        date(2026, 9, 11),
        team_name="Richmond Spiders",
    )
    assert form["verified"] is True
    assert form["source_id"] == "college_football_data"


def test_ncaa_scoreboard_match_from_fixture(monkeypatch) -> None:
    monkeypatch.setattr(
        ncaa_provider,
        "get_fbs_scoreboard",
        lambda **kwargs: [
            {
                "sport": "ncaaf",
                "event_id": "41996",
                "name": "NC State @ Wake Forest",
                "start_time": "2025-09-11T23:30:00+00:00",
                "start_date": "2025-09-11",
                "home_team": "Wake Forest",
                "away_team": "NC State",
                "year": 2025,
                "week": 3,
                "source_id": "ncaa_data_api",
            }
        ],
    )
    matched = ncaa_provider.match_odds_event_to_ncaa(
        date(2025, 9, 11),
        home_team="Wake Forest Demon Deacons",
        away_team="NC State Wolfpack",
    )
    assert matched is not None
    assert matched["source_id"] == "ncaa_data_api"
    assert matched["home_team"] == "Wake Forest"


def test_facts_cascade_falls_back_to_ncaa_schedule(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.facts_cascade.espn_provider.match_odds_event_to_espn",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.facts_cascade.cfbd_provider.match_odds_event_to_cfbd",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.facts_cascade.ncaa_provider.match_odds_event_to_ncaa",
        lambda *args, **kwargs: {
            "source_id": "ncaa_data_api",
            "home_team": "Wake Forest",
            "away_team": "NC State",
            "start_date": "2025-09-11",
        },
    )
    game = facts_cascade.match_schedule_game(
        "ncaaf",
        date(2025, 9, 11),
        home_team="Wake Forest Demon Deacons",
        away_team="NC State Wolfpack",
    )
    assert game is not None
    assert game["source_id"] == "ncaa_data_api"


def test_venue_weather_falls_back_to_nws(monkeypatch) -> None:
    monkeypatch.setattr(
        research_searchers,
        "search_open_meteo_weather",
        lambda **kwargs: {"verified": False, "source_id": "open_meteo", "trusted": True},
    )
    monkeypatch.setattr(
        research_searchers,
        "search_nws_weather",
        lambda **kwargs: {
            "verified": True,
            "source_id": "nws_weather_gov",
            "trusted": True,
            "condition": "Clear",
            "temperature_c": 21.0,
        },
    )
    weather = research_searchers.search_venue_weather(
        latitude=33.2, longitude=-87.5, slate_date=date(2026, 9, 12)
    )
    assert weather["verified"] is True
    assert weather["source_id"] == "nws_weather_gov"
