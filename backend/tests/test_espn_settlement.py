"""ESPN auto-settlement unlocks Hive learning for WNBA/NBA/NFL props."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services import settlement


def test_espn_player_prop_grades_from_boxscore(monkeypatch) -> None:
    game = {
        "event_id": "401857206",
        "home_team": "New York Liberty",
        "away_team": "Atlanta Dream",
        "home_score": 84,
        "away_score": 95,
        "completed": True,
        "status": "STATUS_FINAL",
    }
    players = [
        {"name": "Kiki Rice", "PTS": 12, "REB": 2, "AST": 4, "PRA": 18, "3PT": 1},
        {"name": "Angel Reese", "PTS": 18, "REB": 10, "AST": 2, "PRA": 30, "3PT": 0},
    ]
    monkeypatch.setattr(
        "app.services.espn_provider.match_odds_event_to_espn",
        lambda *args, **kwargs: game,
    )
    monkeypatch.setattr(
        "app.services.espn_provider.get_event_summary",
        lambda *args, **kwargs: {"boxscore": {}},
    )
    monkeypatch.setattr(
        "app.services.espn_provider.parse_boxscore_player_stats",
        lambda summary: players,
    )

    rec = SimpleNamespace(
        id="rec-1",
        result=None,
        outcome=None,
        sport="wnba",
        data_source="THE_ODDS_API",
        slate_date=date(2026, 9, 21),
        event_name="Atlanta Dream @ New York Liberty",
        market_type="player_rebounds",
        selection="Kiki Rice Under 3.5 rebounds",
        line=Decimal("3.5"),
        american_odds=114,
        snapshot={"home_team": "New York Liberty", "away_team": "Atlanta Dream"},
        home_team="New York Liberty",
        away_team="Atlanta Dream",
    )

    monkeypatch.setattr(
        settlement,
        "_persist_auto_grade",
        lambda db, recommendation, **kw: {
            "status": "graded",
            "outcome": kw["derived"]["outcome"],
            "final_score": kw["derived"].get("final_score"),
            "actual_value": kw["derived"].get("actual_value"),
            "detail": kw["derived"].get("detail"),
        },
    )

    out = settlement._grade_espn_recommendation(
        db=None,  # type: ignore[arg-type]
        recommendation=rec,  # type: ignore[arg-type]
        stake=Decimal("0"),
    )
    assert out["status"] == "graded"
    assert out["outcome"] == "WIN"  # 2 reb under 3.5
    assert out["actual_value"] == Decimal("2")


def test_espn_pending_when_game_not_final(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.espn_provider.match_odds_event_to_espn",
        lambda *args, **kwargs: {
            "event_id": "1",
            "completed": False,
            "status": "STATUS_IN_PROGRESS",
            "home_team": "Chicago Sky",
            "away_team": "Toronto Tempo",
            "home_score": 40,
            "away_score": 38,
        },
    )
    rec = SimpleNamespace(
        id="rec-2",
        result=None,
        outcome=None,
        sport="wnba",
        data_source="THE_ODDS_API",
        slate_date=date(2026, 9, 22),
        event_name="Toronto Tempo @ Chicago Sky",
        market_type="moneyline",
        selection="Chicago Sky ML",
        line=None,
        american_odds=-120,
        snapshot={"home_team": "Chicago Sky", "away_team": "Toronto Tempo"},
        home_team="Chicago Sky",
        away_team="Toronto Tempo",
    )
    out = settlement._grade_espn_recommendation(
        db=None,  # type: ignore[arg-type]
        recommendation=rec,  # type: ignore[arg-type]
        stake=Decimal("0"),
    )
    assert out["status"] == "pending"


def test_player_name_parser() -> None:
    assert settlement._player_name_from_selection("Kiki Rice Under 3.5 rebounds") == "Kiki Rice"
    assert settlement._player_name_from_selection("Angel Reese Over 9.5 rebounds") == "Angel Reese"
