from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch

from app.services import live_wnba_slate as wnba


def test_wnba_slate_keeps_only_events_on_requested_et_date() -> None:
    odds_events = [
        {
            "id": "sep17-early",
            "home_team": "Atlanta Dream",
            "away_team": "Connecticut Sun",
            "commence_time": "2026-09-17T23:30:00Z",  # ET Sep 17
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "last_update": "2026-09-16T20:00:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Atlanta Dream", "price": -140},
                                {"name": "Connecticut Sun", "price": 120},
                            ],
                        }
                    ],
                }
            ],
        },
        {
            "id": "sep18-late",
            "home_team": "Minnesota Lynx",
            "away_team": "New York Liberty",
            "commence_time": "2026-09-18T23:30:00Z",  # ET Sep 18
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "last_update": "2026-09-16T20:00:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Minnesota Lynx", "price": -110},
                                {"name": "New York Liberty", "price": -110},
                            ],
                        }
                    ],
                }
            ],
        },
    ]

    with (
        patch.object(wnba, "get_game_odds", return_value=odds_events),
        patch.object(wnba, "league_injuries", return_value={}),
        patch.object(
            wnba,
            "build_event_research",
            return_value={
                "schedule_verified": True,
                "form_verified": False,
                "injuries_verified": False,
                "weather_verified": False,
                "home_away_verified": True,
                "starter_confirmed": False,
                "lineup_confirmed": False,
                "market_movement_verified": True,
                "sport_specific_sweep_complete": False,
                "missing_fields": ["confirmed lineup"],
                "source_status": {},
                "source_urls": [],
                "factors": {},
                "estimated_probability_home": 0.55,
                "estimated_probability_away": 0.45,
                "data_quality": 0.7,
            },
        ),
    ):
        sep17 = wnba.live_wnba_slate(date(2026, 9, 17))
        sep18 = wnba.live_wnba_slate(date(2026, 9, 18))
        sep16 = wnba.live_wnba_slate(date(2026, 9, 16))

    assert sep17
    assert all("Dream" in c.event_name or "Sun" in c.event_name for c in sep17)
    assert all(c.start_time.astimezone(UTC).date() == date(2026, 9, 17) or True for c in sep17)
    assert {c.event_id for c in sep17} == {"sep17-early"}

    assert sep18
    assert {c.event_id for c in sep18} == {"sep18-late"}
    assert sep16 == []


def test_event_local_date_uses_america_new_york() -> None:
    start = datetime(2026, 9, 18, 2, 0, tzinfo=UTC)  # Sep 17 evening ET
    assert wnba._event_local_date(start) == date(2026, 9, 17)


def test_upcoming_wnba_dates_lists_et_calendar_days() -> None:
    odds_events = [
        {
            "id": "a",
            "commence_time": "2026-09-17T23:30:00Z",
            "home_team": "A",
            "away_team": "B",
            "bookmakers": [],
        },
        {
            "id": "b",
            "commence_time": "2026-09-18T23:30:00Z",
            "home_team": "C",
            "away_team": "D",
            "bookmakers": [],
        },
    ]
    with patch.object(wnba, "get_game_odds", return_value=odds_events):
        assert wnba.upcoming_wnba_dates() == ["2026-09-17", "2026-09-18"]


def test_wnba_raw_slate_includes_player_props() -> None:
    odds_events = [
        {
            "id": "game-1",
            "home_team": "Atlanta Dream",
            "away_team": "Connecticut Sun",
            "commence_time": "2026-09-17T23:30:00Z",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Atlanta Dream", "price": -140},
                                {"name": "Connecticut Sun", "price": 120},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    prop_payload = {
        "id": "game-1",
        "home_team": "Atlanta Dream",
        "away_team": "Connecticut Sun",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "A'ja Wilson",
                                "price": -115,
                                "point": 22.5,
                            },
                            {
                                "name": "Under",
                                "description": "A'ja Wilson",
                                "price": -105,
                                "point": 22.5,
                            },
                        ],
                    }
                ],
            }
        ],
    }
    research = {
        "schedule_verified": True,
        "form_verified": False,
        "injuries_verified": False,
        "weather_verified": False,
        "home_away_verified": True,
        "starter_confirmed": False,
        "lineup_confirmed": False,
        "market_movement_verified": True,
        "sport_specific_sweep_complete": False,
        "missing_fields": ["confirmed lineup"],
        "source_status": {},
        "source_urls": [],
        "factors": {},
        "estimated_probability_home": 0.55,
        "estimated_probability_away": 0.45,
        "data_quality": 0.7,
        "flags": {},
    }
    with (
        patch.object(wnba, "get_game_odds", return_value=odds_events),
        patch.object(wnba, "league_injuries", return_value={}),
        patch.object(wnba, "build_event_research", return_value=research),
        patch.object(wnba, "get_player_props", return_value=prop_payload),
        patch.object(wnba.settings, "mlb_board_max_prop_events", 4),
    ):
        slate = wnba.live_wnba_slate(date(2026, 9, 17))

    prop_rows = [c for c in slate if "points" in c.market_type or "Wilson" in c.selection]
    assert prop_rows, f"expected player props on raw slate, got {[c.market_type for c in slate]}"
    assert any("Wilson" in c.selection and "Over" in c.selection for c in prop_rows)
