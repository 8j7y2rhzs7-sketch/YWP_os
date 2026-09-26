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


def test_overlay_selected_with_model_preserves_sheet_provenance(monkeypatch) -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    board_leg = board_module._board_candidate(
        sport="mlb",
        event_id="evt-sel",
        event_name="Away Club @ Home Club",
        start_time=datetime(2026, 9, 8, 23, 0, tzinfo=UTC),
        home_team="Home Club",
        away_team="Away Club",
        market_type="moneyline",
        selection="Home Club ML",
        line=None,
        odds=-120,
        bookmaker="draftkings",
        now=now,
        player_key=None,
        market_is_pitcher_strikeout_over=False,
    )
    model = board_leg.model_copy(
        update={
            "probability_source": "model",
            "estimated_probability": 0.62,
            "data_quality": 0.91,
            "data_source": "MLB_STATS_API+THE_ODDS_API",
            "reason_codes": ["MODEL"],
            "independent_value_verified": True,
            "missing_fields": [],
        }
    )
    monkeypatch.setattr(board_module, "_load_model_slate", lambda sport, slate_date: [model])

    upgraded, count = board_module.overlay_selected_with_model(
        "mlb", date(2026, 9, 8), [board_leg]
    )
    assert count == 1
    assert upgraded[0].probability_source == "model"
    assert upgraded[0].estimated_probability == 0.62
    assert upgraded[0].data_source == "THE_ODDS_API_BOARD"
    assert "SPORTSBOOK_MENU" in upgraded[0].reason_codes
    assert upgraded[0].candidate_id == board_leg.candidate_id


def test_ncaaf_prop_markets_configured() -> None:
    markets = board_module._PROP_MARKETS_BY_SPORT["ncaaf"]
    assert "player_pass_yds" in markets
    assert "player_rush_yds" in markets
    assert "player_reception_yds" in markets
    assert "player_anytime_td" in markets
    assert "player_kicking_points" in markets
    assert "player_pass_rush_yds" in markets
    assert "player_pass_yds_q1" in markets
    assert "ncaaf" in board_module._PERIOD_MARKETS_BY_SPORT
    assert "h2h_h1" in board_module._PERIOD_MARKETS_BY_SPORT["ncaaf"]
    assert "totals_q1" in board_module._PERIOD_MARKETS_BY_SPORT["ncaaf"]


def test_flatten_ncaaf_props_and_anytime_td() -> None:
    event = {
        "id": "evt-ncaaf-props",
        "home_team": "Alabama Crimson Tide",
        "away_team": "Georgia Bulldogs",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "player_pass_yds",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "QB One",
                                "price": -115,
                                "point": 249.5,
                            },
                            {
                                "name": "Under",
                                "description": "QB One",
                                "price": -105,
                                "point": 249.5,
                            },
                        ],
                    },
                    {
                        "key": "player_anytime_td",
                        "outcomes": [
                            {
                                "name": "Yes",
                                "description": "Star Back",
                                "price": -140,
                            },
                            {
                                "name": "No",
                                "description": "Star Back",
                                "price": 110,
                            },
                        ],
                    },
                    {
                        "key": "player_kicking_points",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "Kicker A",
                                "price": -110,
                                "point": 7.5,
                            }
                        ],
                    },
                ],
            }
        ],
    }
    rows = board_module._flatten_prop_markets(
        event=event,
        sport="ncaaf",
        start_time=datetime(2026, 9, 12, 19, 0, tzinfo=UTC),
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )
    types = {row.market_type for row in rows}
    assert "player_pass_yds_over" in types
    assert "player_pass_yds_under" in types
    assert "player_anytime_td_yes" in types
    assert "player_kick_pts_over" in types
    assert not any(row.market_type.endswith("_no") for row in rows)
    assert any("Anytime TD" in row.selection for row in rows)
    assert any("pass yards" in row.selection for row in rows)


def test_flatten_ncaaf_period_markets() -> None:
    event = {
        "id": "evt-ncaaf-period",
        "home_team": "Ohio State",
        "away_team": "Michigan",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "h2h_h1",
                        "outcomes": [
                            {"name": "Ohio State", "price": -150},
                            {"name": "Michigan", "price": 130},
                        ],
                    },
                    {
                        "key": "spreads_q1",
                        "outcomes": [
                            {"name": "Ohio State", "price": -110, "point": -2.5},
                            {"name": "Michigan", "price": -110, "point": 2.5},
                        ],
                    },
                    {
                        "key": "totals_h1",
                        "outcomes": [
                            {"name": "Over", "price": -105, "point": 27.5},
                            {"name": "Under", "price": -115, "point": 27.5},
                        ],
                    },
                ],
            }
        ],
    }
    rows = board_module._flatten_period_markets(
        event=event,
        sport="ncaaf",
        start_time=datetime(2026, 9, 12, 19, 0, tzinfo=UTC),
        now=datetime(2026, 9, 12, 12, 0, tzinfo=UTC),
    )
    assert {row.market_period for row in rows} <= {"1h", "1q"}
    assert any(row.market_period == "1h" and row.market_type == "moneyline" for row in rows)
    assert any(row.market_period == "1q" and row.market_type == "spread" for row in rows)
    assert any("(1H)" in row.selection for row in rows)
    assert any("(1Q)" in row.selection for row in rows)


def test_build_ncaaf_board_fetches_props_and_periods(monkeypatch) -> None:
    event = {
        "id": "evt-ncaaf-board",
        "commence_time": "2026-09-12T19:00:00Z",
        "home_team": "Alabama Crimson Tide",
        "away_team": "Georgia Bulldogs",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Alabama Crimson Tide", "price": -160},
                            {"name": "Georgia Bulldogs", "price": 140},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Alabama Crimson Tide", "price": -110, "point": -7.5},
                            {"name": "Georgia Bulldogs", "price": -110, "point": 7.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -110, "point": 52.5},
                            {"name": "Under", "price": -110, "point": 52.5},
                        ],
                    },
                ],
            }
        ],
    }

    def fake_props(event_id, sport="americanfootball_ncaaf", markets=""):
        keys = {part.strip() for part in markets.split(",") if part.strip()}
        if keys & {"player_pass_yds", "player_anytime_td", "player_rush_yds"}:
            return {
                "id": event_id,
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "player_pass_yds",
                                "outcomes": [
                                    {
                                        "name": "Over",
                                        "description": "QB One",
                                        "price": -115,
                                        "point": 250.5,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        if keys & {"h2h_h1", "spreads_h1", "totals_h1", "h2h_q1"}:
            return {
                "id": event_id,
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "h2h_h1",
                                "outcomes": [
                                    {"name": "Alabama Crimson Tide", "price": -140},
                                    {"name": "Georgia Bulldogs", "price": 120},
                                ],
                            }
                        ],
                    }
                ],
            }
        return None

    monkeypatch.setattr(board_module, "odds_api_configured", lambda: True)
    monkeypatch.setattr(board_module, "get_game_odds", lambda **kwargs: [event])
    monkeypatch.setattr(board_module, "get_player_props", fake_props)
    monkeypatch.setattr(board_module, "_load_model_slate", lambda sport, slate_date: [])
    monkeypatch.setattr(board_module, "get_last_fetch_status", lambda: {})

    candidates, notice = board_module.build_market_board(
        "ncaaf",
        date(2026, 9, 12),
        include_props=True,
        overlay_model=False,
    )
    assert any(c.market_type == "spread" and c.market_period == "full_game" for c in candidates)
    assert any(c.market_type == "player_pass_yds_over" for c in candidates)
    assert any(c.market_period == "1h" and c.market_type == "moneyline" for c in candidates)
    assert "props priced" in notice.lower()
    assert "1h/1q" in notice.lower()


def test_overlay_selected_soft_fails(monkeypatch) -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    board_leg = board_module._board_candidate(
        sport="mlb",
        event_id="evt-fail",
        event_name="Away Club @ Home Club",
        start_time=datetime(2026, 9, 8, 23, 0, tzinfo=UTC),
        home_team="Home Club",
        away_team="Away Club",
        market_type="moneyline",
        selection="Home Club ML",
        line=None,
        odds=-120,
        bookmaker="draftkings",
        now=now,
        player_key=None,
        market_is_pitcher_strikeout_over=False,
    )

    def _boom(sport, slate_date):
        raise RuntimeError("model timeout")

    monkeypatch.setattr(board_module, "_overlay_model_candidates", _boom)
    upgraded, count = board_module.overlay_selected_with_model(
        "mlb", date(2026, 9, 8), [board_leg]
    )
    assert count == 0
    assert upgraded[0].probability_source == "market_implied"
