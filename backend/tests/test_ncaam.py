"""Men's college basketball is NCAAM on the slate and basketball_ncaab at the book."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.espn_provider import espn_path_for
from app.services.live_board import MAJOR_SPORTS, build_live_board
from app.services.lock_refresh import _odds_sport_key
from app.services.market_board import (
    _BOARD_MAX_PROP_EVENTS_BY_SPORT,
    _PERIOD_MARKETS_BY_SPORT,
    _PROP_MARKETS_BY_SPORT,
)
from app.services.odds_provider import (
    canonical_app_sport,
    odds_keys_for_app_sport,
    sport_public_label,
)


def test_ncaam_uses_mens_college_basketball() -> None:
    assert canonical_app_sport("ncaam") == "ncaab"
    assert canonical_app_sport("NCAAB") == "ncaab"
    assert odds_keys_for_app_sport("ncaam") == ["basketball_ncaab"]
    assert odds_keys_for_app_sport("ncaab") == ["basketball_ncaab"]
    assert espn_path_for("ncaam") == "basketball/mens-college-basketball"
    assert espn_path_for("ncaab") == "basketball/mens-college-basketball"
    assert sport_public_label("ncaab") == "NCAAM"
    assert sport_public_label("nba") == "NBA"


def test_ncaam_sheet_prices_player_props_and_halves() -> None:
    markets = _PROP_MARKETS_BY_SPORT["ncaab"]
    assert markets == _PROP_MARKETS_BY_SPORT["nba"]
    assert "player_points" in markets
    assert "player_rebounds" in markets
    assert "player_assists" in markets
    assert "player_threes" in markets
    assert "player_points_rebounds_assists" in markets
    assert _PERIOD_MARKETS_BY_SPORT["ncaab"] == "h2h_h1,spreads_h1,totals_h1"
    assert "totals_q1" not in _PERIOD_MARKETS_BY_SPORT["ncaab"]
    assert _BOARD_MAX_PROP_EVENTS_BY_SPORT["ncaab"] == 6


def test_ncaam_lock_refresh_uses_college_basketball_odds() -> None:
    assert _odds_sport_key("ncaab") == "basketball_ncaab"
    assert _odds_sport_key("ncaam") == "basketball_ncaab"


def test_catalog_labels_the_sport_ncaam(monkeypatch) -> None:
    from app.services import odds_provider as odds_mod

    monkeypatch.setattr(
        odds_mod,
        "in_season_odds_keys",
        lambda force_refresh=False: {"basketball_ncaab"},
    )
    monkeypatch.setattr(odds_mod, "odds_api_configured", lambda: True)
    rows = {row["key"]: row for row in odds_mod.build_app_sports_catalog()}
    assert rows["ncaab"]["label"] == "NCAAM"
    assert rows["ncaab"]["odds_key"] == "basketball_ncaab"
    assert rows["ncaab"]["in_season"] is True
    assert "ncaam" not in rows


def test_live_board_includes_a_mens_college_game(db_session) -> None:
    assert "ncaab" in MAJOR_SPORTS
    now = datetime.now(UTC)
    game = {
        "sport": "ncaab",
        "event_id": "duke-unc",
        "away_team": "Duke Blue Devils",
        "home_team": "North Carolina Tar Heels",
        "away_score": 40,
        "home_score": 38,
        "status": "LIVE",
        "detail": "1st 8:04",
        "start_time": "2026-11-02T23:00:00Z",
    }
    board = build_live_board(
        db_session,
        "user-1",
        now=now,
        espn_loader=lambda sport, _slate: [game] if sport == "ncaab" else [],
        mlb_loader=lambda _slate: [],
        players_loader=lambda _sport, _event: [],
        mlb_feed_loader=lambda _event: None,
    )
    assert board.live_count == 1
    assert board.games[0].sport == "ncaab"
    assert board.games[0].status == "LIVE"
    assert board.games[0].home_team == "North Carolina Tar Heels"
