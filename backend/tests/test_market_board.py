from __future__ import annotations

from datetime import UTC, date, datetime

from app.services import market_board as board_module


def test_flatten_game_markets_includes_both_sides() -> None:
    event = {
        "id": "evt-1",
        "home_team": "Home Club",
        "away_team": "Away Club",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Home Club", "price": -130},
                            {"name": "Away Club", "price": 110},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Home Club", "price": -110, "point": -1.5},
                            {"name": "Away Club", "price": -110, "point": 1.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -105, "point": 8.5},
                            {"name": "Under", "price": -115, "point": 8.5},
                        ],
                    },
                ],
            }
        ],
    }
    rows = board_module._flatten_game_markets(
        event=event,
        sport="mlb",
        start_time=datetime(2026, 9, 8, 23, 0, tzinfo=UTC),
        now=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    types = {row.market_type for row in rows}
    assert types == {"moneyline", "run_line", "game_total_over", "game_total_under"}
    assert len(rows) == 6
    assert all(row.probability_source == "market_implied" for row in rows)
    assert all(row.data_source == "THE_ODDS_API_BOARD" for row in rows)


def test_flatten_prop_markets_builds_hits_and_ks() -> None:
    event = {
        "id": "evt-2",
        "home_team": "Home Club",
        "away_team": "Away Club",
        "bookmakers": [
            {
                "key": "hardrockbet",
                "markets": [
                    {
                        "key": "pitcher_strikeouts",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "Ace Arm",
                                "price": -120,
                                "point": 6.5,
                            }
                        ],
                    },
                    {
                        "key": "batter_hits",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "Top Hitter",
                                "price": -115,
                                "point": 0.5,
                            }
                        ],
                    },
                ],
            }
        ],
    }
    rows = board_module._flatten_prop_markets(
        event=event,
        sport="mlb",
        start_time=datetime(2026, 9, 8, 23, 0, tzinfo=UTC),
        now=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    assert {row.market_type for row in rows} == {
        "player_strikeouts_over",
        "player_hits_over",
    }
    assert any(row.market_is_pitcher_strikeout_over for row in rows)
    assert any("Top Hitter" in row.selection for row in rows)


def test_build_market_board_overlays_model(monkeypatch) -> None:
    event = {
        "id": "evt-3",
        "commence_time": "2026-09-08T23:00:00Z",
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
                            {"name": "Away Club", "price": 105},
                        ],
                    }
                ],
            }
        ],
    }
    monkeypatch.setattr(board_module, "odds_api_configured", lambda: True)
    monkeypatch.setattr(board_module, "get_game_odds", lambda **kwargs: [event])
    monkeypatch.setattr(board_module, "get_player_props", lambda *args, **kwargs: None)

    model = board_module._board_candidate(
        sport="mlb",
        event_id="evt-3",
        event_name="Away Club @ Home Club",
        start_time=datetime(2026, 9, 8, 23, 0, tzinfo=UTC),
        home_team="Home Club",
        away_team="Away Club",
        market_type="moneyline",
        selection="Home Club ML",
        line=None,
        odds=-125,
        bookmaker="draftkings",
        now=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        player_key=None,
        market_is_pitcher_strikeout_over=False,
    )
    model = model.model_copy(
        update={
            "probability_source": "model",
            "estimated_probability": 0.61,
            "data_quality": 0.9,
            "independent_value_verified": True,
            "missing_fields": [],
            "sport_specific_sweep_complete": True,
            "lineup_confirmed": True,
            "current_form_verified": True,
            "l5_l10_verified": True,
            "injuries_verified": True,
            "weather_verified": True,
            "starter_confirmed": True,
            "motivation_rotation_verified": True,
            "home_away_verified": True,
        }
    )
    monkeypatch.setattr(board_module, "_load_model_slate", lambda sport, slate_date: [model])

    candidates, notice = board_module.build_market_board(
        "mlb",
        date(2026, 9, 8),
        include_props=False,
        overlay_model=True,
    )
    assert len(candidates) == 2
    home = next(row for row in candidates if "Home Club" in row.selection)
    away = next(row for row in candidates if "Away Club" in row.selection)
    assert home.probability_source == "model"
    assert home.estimated_probability == 0.61
    assert away.probability_source == "market_implied"
    assert "upgraded" in notice.lower()
