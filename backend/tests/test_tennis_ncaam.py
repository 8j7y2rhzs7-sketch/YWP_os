"""Tennis tournament discovery and NCAAM men's college basketball labels."""

from __future__ import annotations

from app.services.espn_provider import espn_path_for
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
    tennis_league_label,
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
    assert _PERIOD_MARKETS_BY_SPORT["ncaab"] == "h2h_h1,spreads_h1,totals_h1"
    assert "totals_q1" not in _PERIOD_MARKETS_BY_SPORT["ncaab"]
    assert _BOARD_MAX_PROP_EVENTS_BY_SPORT["ncaab"] == 6
    assert _odds_sport_key("ncaab") == "basketball_ncaab"
    assert _odds_sport_key("ncaam") == "basketball_ncaab"


def test_tennis_discovers_active_tournaments(monkeypatch) -> None:
    from app.services import odds_provider as odds_mod

    monkeypatch.setattr(
        odds_mod,
        "in_season_odds_keys",
        lambda force_refresh=False: {
            "tennis_wta_finals",
            "tennis_atp_vienna_open",
            "basketball_nba",
        },
    )
    monkeypatch.setattr(odds_mod, "odds_api_configured", lambda: True)
    keys = odds_mod.active_odds_keys_for_app_sport("tennis")
    assert keys == ["tennis_atp_vienna_open", "tennis_wta_finals"]
    assert tennis_league_label("tennis_wta_finals") == "WTA Finals"
    assert sport_public_label("tennis") == "TENNIS"
    assert espn_path_for("tennis") == "tennis/atp"

    rows = {row["key"]: row for row in odds_mod.build_app_sports_catalog()}
    assert rows["tennis"]["label"] == "TENNIS"
    assert rows["tennis"]["in_season"] is True
    assert rows["ncaab"]["label"] == "NCAAM"
