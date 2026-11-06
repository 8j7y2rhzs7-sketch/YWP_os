"""NBA player logs must use the season that is actually being played."""

from __future__ import annotations

from datetime import date

from app.services.player_prop_research import (
    _games_for_current_log,
    _stat_series,
    espn_player_season,
)


def test_november_nba_slate_requests_the_season_that_ends_next_year() -> None:
    assert espn_player_season("nba", date(2026, 11, 6)) == 2027
    assert espn_player_season("nba", date(2026, 10, 21)) == 2027
    assert espn_player_season("nba", date(2026, 5, 31)) == 2026
    assert espn_player_season("nba", date(2027, 1, 15)) == 2027
    assert espn_player_season("wnba", date(2026, 11, 6)) == 2026


def test_preseason_does_not_pad_a_regular_season_log() -> None:
    games = [
        {"points": 42, "totalRebounds": 4, "season_phase": "2026-27 Regular Season"},
        {"points": 17, "totalRebounds": 1, "season_phase": "2026-27 Preseason"},
    ]
    kept = _games_for_current_log(games)
    assert _stat_series(kept, "pr") == [46.0]


def test_preseason_only_log_is_kept_when_nothing_else_exists() -> None:
    games = [{"points": 15, "totalRebounds": 0, "season_phase": "Preseason"}]
    assert _games_for_current_log(games) == games
