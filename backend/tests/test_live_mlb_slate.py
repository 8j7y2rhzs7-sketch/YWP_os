from __future__ import annotations

from datetime import date

from app.services import live_mlb_slate as slate_module


def _form(team_id: int) -> dict[str, object]:
    summary = {
        "games": 10,
        "wins": 6,
        "losses": 4,
        "win_pct": 0.6,
        "avg_runs_for": 4.7,
        "avg_runs_against": 4.1,
        "run_diff_per_game": 0.6,
        "totals": [8, 9, 7, 10, 6, 11, 8, 9, 7, 8],
    }
    return {
        "verified": True,
        "l5": dict(summary),
        "l10": dict(summary),
        "games": [],
        "source_url": f"https://statsapi.mlb.com/team/{team_id}",
    }


def _research() -> dict[str, object]:
    side = {"lineup_confirmed": True, "lineup": [], "pitchers": [], "bullpen": []}
    availability = {
        "verified": True,
        "active": [],
        "injured": [],
        "unavailable": [],
        "source_url": "https://statsapi.mlb.com/roster",
    }
    bullpen = {
        "verified": True,
        "heavy_usage": False,
        "relievers": [],
        "source_url": "https://statsapi.mlb.com/bullpen",
    }
    return {
        "home_form": _form(10),
        "away_form": _form(20),
        "home_availability": dict(availability),
        "away_availability": dict(availability),
        "context": {
            "verified": True,
            "home": dict(side),
            "away": dict(side),
            "weather": {"verified": True, "condition": "Clear", "temperature_f": "72"},
            "venue": "Test Park",
            "park_verified": True,
            "umpire_verified": True,
            "officials": [{"name": "Crew Chief", "role": "Home Plate"}],
            "source_url": "https://statsapi.mlb.com/live",
            "gameday_url": "https://www.mlb.com/gameday/123",
        },
        "home_bullpen": dict(bullpen),
        "away_bullpen": dict(bullpen),
        "home_pitcher_log": [],
        "away_pitcher_log": [],
        "home_pitcher_l5": {"era": 3.5},
        "away_pitcher_l5": {"era": 4.5},
        "market_search": {"verified": True, "book_count": 2, "detail": "2 trusted quotes"},
        "searchers": {
            "umpires": {"verified": True, "source_url": "https://statsapi.mlb.com"},
            "park": {"verified": True, "source_url": "https://statsapi.mlb.com"},
            "weather_backup": {"verified": False},
        },
    }


def test_live_slate_uses_model_probability_and_real_market_price(monkeypatch) -> None:
    game = {
        "game_pk": 123,
        "game_date": "2026-09-03T23:00:00Z",
        "home_team": "Home Club",
        "home_id": 10,
        "home_pitcher": {"id": 100, "name": "Home Starter"},
        "away_team": "Away Club",
        "away_id": 20,
        "away_pitcher": {"id": 200, "name": "Away Starter"},
        "venue": "Test Park",
        "venue_id": 31,
        "officials": [
            {"official": {"id": 1, "fullName": "Plate Ump"}, "officialType": "Home Plate"}
        ],
        "weather": {"condition": "Clear", "temp": "72", "wind": "5 mph"},
        "mlb_game_url": "https://www.mlb.com/gameday/123",
    }
    event = {
        "id": "real-odds-event",
        "home_team": "Home Club",
        "away_team": "Away Club",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Home Club", "price": -125},
                            {"name": "Away Club", "price": 110},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -108, "point": 8.5},
                            {"name": "Under", "price": -112, "point": 8.5},
                        ],
                    },
                ],
            }
        ],
    }
    monkeypatch.setattr(slate_module, "get_schedule", lambda slate_date: [game])
    monkeypatch.setattr(slate_module, "get_game_odds", lambda **kwargs: [event])
    monkeypatch.setattr(slate_module, "_game_research", lambda game, slate_date: _research())
    monkeypatch.setattr(
        slate_module,
        "run_mlb_research_searchers",
        lambda **kwargs: {
            "umpires": {"verified": True, "source_id": "mlb_stats_api", "crew": []},
            "park": {"verified": True, "source_id": "mlb_stats_api", "venue": "Test Park"},
            "weather_backup": {"verified": False},
            "market": {"verified": True, "book_count": 2, "detail": "2 books"},
            "sources_used": ["mlb_stats_api", "the_odds_api"],
        },
    )
    monkeypatch.setattr(slate_module.settings, "mlb_props_enabled", False)

    candidates = slate_module.live_mlb_slate(date(2026, 9, 3))

    assert candidates
    assert all(candidate.probability_source == "model" for candidate in candidates)
    assert all(candidate.data_source == "MLB_STATS_API+THE_ODDS_API" for candidate in candidates)
    assert {candidate.american_odds for candidate in candidates} >= {-125, 110, -108, -112}
    assert not any(candidate.market_is_pitcher_strikeout_over for candidate in candidates)
    assert any("mlb.com/gameday/123" in url for url in candidates[0].source_urls)
    assert all(candidate.sport_specific_sweep_complete for candidate in candidates)
    assert all(candidate.market_movement_verified for candidate in candidates)
