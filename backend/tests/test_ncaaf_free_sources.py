from __future__ import annotations

from datetime import date

from app.services import cfbd_provider, espn_provider, facts_cascade
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


def test_espn_name_overlap_ignores_weak_state_token() -> None:
    # "State" alone must not glue Michigan State to Ohio State.
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
    # Exact / strong match still works.
    matched = espn_provider.injuries_for_teams(
        feed, "Michigan State Spartans", "Ohio State Buckeyes"
    )
    assert matched["verified"] is True
    assert matched["home_out"] == 1
    # Weak shared "State" must not falsely match an unrelated club.
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
            "l5": {"games": 5, "wins": 3, "losses": 2, "win_pct": 0.6, "avg_for": 24, "avg_against": 20, "totals": []},
            "l10": {"games": 5, "wins": 3, "losses": 2, "win_pct": 0.6, "avg_for": 24, "avg_against": 20, "totals": []},
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
