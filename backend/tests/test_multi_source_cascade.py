from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services import live_generic_slate


def test_live_generic_keeps_plays_when_espn_research_fails(monkeypatch) -> None:
    event = {
        "id": "evt-soccer-1",
        "commence_time": "2026-09-04T23:00:00Z",
        "home_team": "Home FC",
        "away_team": "Away FC",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Home FC", "price": -120},
                            {"name": "Away FC", "price": 100},
                            {"name": "Draw", "price": 240},
                        ],
                    }
                ],
            }
        ],
    }

    monkeypatch.setattr(
        live_generic_slate,
        "active_odds_keys_for_app_sport",
        lambda sport, **kwargs: ["soccer_epl"],
    )
    monkeypatch.setattr(live_generic_slate, "get_game_odds", lambda **kwargs: [event])
    monkeypatch.setattr(live_generic_slate, "league_injuries", lambda sport: {"verified": False, "by_team": {}})

    def boom(**kwargs):
        raise RuntimeError("espn 403")

    monkeypatch.setattr(live_generic_slate, "build_event_research", boom)

    candidates = live_generic_slate.live_generic_slate("soccer", date(2026, 9, 4))
    assert candidates
    assert any(item.selection.endswith("ML") for item in candidates)
    assert any("Draw" in item.selection for item in candidates)
    assert any(item.league == "EPL" for item in candidates)


def test_soccer_slate_merges_epl_and_la_liga(monkeypatch) -> None:
    def odds_for(**kwargs):
        sport = kwargs.get("sport")
        if sport == "soccer_epl":
            return [
                {
                    "id": "evt-liv",
                    "commence_time": "2026-09-04T15:00:00Z",
                    "home_team": "Liverpool",
                    "away_team": "Arsenal",
                    "bookmakers": [
                        {
                            "key": "draftkings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Liverpool", "price": -140},
                                        {"name": "Arsenal", "price": 320},
                                        {"name": "Draw", "price": 260},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        if sport == "soccer_spain_la_liga":
            return [
                {
                    "id": "evt-bar",
                    "commence_time": "2026-09-04T19:00:00Z",
                    "home_team": "Barcelona",
                    "away_team": "Sevilla",
                    "bookmakers": [
                        {
                            "key": "draftkings",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Barcelona", "price": -180},
                                        {"name": "Sevilla", "price": 450},
                                        {"name": "Draw", "price": 300},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        return []

    monkeypatch.setattr(
        live_generic_slate,
        "active_odds_keys_for_app_sport",
        lambda sport, **kwargs: ["soccer_epl", "soccer_spain_la_liga"],
    )
    monkeypatch.setattr(live_generic_slate, "get_game_odds", odds_for)
    monkeypatch.setattr(
        live_generic_slate, "league_injuries", lambda sport: {"verified": False, "by_team": {}}
    )
    monkeypatch.setattr(
        live_generic_slate,
        "build_event_research",
        lambda **kwargs: live_generic_slate._odds_only_research(
            kwargs["bookmakers"], home_team=kwargs["home_team"]
        ),
    )

    candidates = live_generic_slate.live_generic_slate("soccer", date(2026, 9, 4))
    names = " ".join(item.event_name for item in candidates)
    assert "Liverpool" in names
    assert "Barcelona" in names
    assert any(item.league == "EPL" for item in candidates)
    assert any(item.league == "La Liga" for item in candidates)


def test_upcoming_odds_dates_lists_nearest(monkeypatch) -> None:
    monkeypatch.setattr(
        live_generic_slate,
        "get_game_odds",
        lambda **kwargs: [
            {"commence_time": "2026-09-05T08:00:00Z"},
            {"commence_time": "2026-09-05T10:00:00Z"},
            {"commence_time": "2026-09-06T08:00:00Z"},
        ],
    )
    assert live_generic_slate.upcoming_odds_dates("kbo") == ["2026-09-05", "2026-09-06"]


def test_trusted_sources_include_nhl_and_odds_schedule() -> None:
    from app.services.trusted_sources import sources_for, trusted_sources_manifest

    ids = {item["id"] for item in trusted_sources_manifest()["sources"]}
    assert "nhl_web_api" in ids
    assert any(item["id"] == "the_odds_api" for item in sources_for("schedule", "kbo"))
