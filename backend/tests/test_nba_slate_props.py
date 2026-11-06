"""NBA regular-season Run slate must price player props, including late ET tip-offs."""

from __future__ import annotations

from datetime import date

from app.services import live_generic_slate


def _game(event_id: str, commence: str, home: str, away: str) -> dict:
    return {
        "id": event_id,
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": home, "price": -140},
                            {"name": away, "price": 120},
                        ],
                    }
                ],
            }
        ],
    }


def test_nba_run_slate_prices_player_props_including_late_tip(monkeypatch) -> None:
    games = [
        _game("evt-bos", "2026-10-20T23:00:00Z", "New York Knicks", "Philadelphia 76ers"),
        _game("evt-sas", "2026-10-21T01:30:00Z", "San Antonio Spurs", "Oklahoma City Thunder"),
    ]
    prop_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        live_generic_slate,
        "active_odds_keys_for_app_sport",
        lambda sport, **kwargs: ["basketball_nba"],
    )
    monkeypatch.setattr(live_generic_slate, "get_game_odds", lambda **kwargs: games)
    monkeypatch.setattr(
        live_generic_slate, "league_injuries", lambda sport: {"verified": False, "by_team": {}}
    )
    monkeypatch.setattr(
        live_generic_slate,
        "build_event_research",
        lambda **kwargs: live_generic_slate._odds_only_research(
            kwargs.get("bookmakers") or [],
            home_team=kwargs.get("home_team") or "",
            sport="nba",
        ),
    )

    def props(event_id, **kwargs):
        markets = str(kwargs.get("markets") or "")
        prop_calls.append((event_id, markets))
        if "player_points" not in markets:
            return {"bookmakers": []}
        home = "San Antonio Spurs" if event_id == "evt-sas" else "New York Knicks"
        away = "Oklahoma City Thunder" if event_id == "evt-sas" else "Philadelphia 76ers"
        player = "Victor Wembanyama" if event_id == "evt-sas" else "Jalen Brunson"
        return {
            "id": event_id,
            "home_team": home,
            "away_team": away,
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "player_points",
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": player,
                                    "price": -115,
                                    "point": 26.5,
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(live_generic_slate, "get_player_props", props)
    monkeypatch.setattr(
        live_generic_slate,
        "enrich_player_prop_candidates",
        lambda rows, **kwargs: rows,
    )
    monkeypatch.setattr(
        live_generic_slate,
        "schedule_background_prop_enrich",
        lambda *args, **kwargs: False,
    )

    candidates = live_generic_slate.live_generic_slate("nba", date(2026, 10, 20))
    priced_events = {event_id for event_id, markets in prop_calls if "player_points" in markets}
    assert priced_events == {"evt-bos", "evt-sas"}
    requested = " ".join(markets for _event_id, markets in prop_calls)
    for key in (
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        "player_points_rebounds_assists",
    ):
        assert key in requested
    points = [row for row in candidates if row.market_type == "player_points_over"]
    assert {row.selection.split(" Over ")[0] for row in points} == {
        "Jalen Brunson",
        "Victor Wembanyama",
    }
    assert all(row.sport == "nba" for row in points)
