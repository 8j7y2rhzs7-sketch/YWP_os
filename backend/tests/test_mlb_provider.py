from __future__ import annotations

from datetime import date

from app.services import mlb_provider


def test_recent_form_parses_official_final_scores(monkeypatch) -> None:
    games = []
    for index in range(6):
        home_score = 5 if index < 4 else 2
        away_score = 3
        games.append(
            {
                "gamePk": 100 + index,
                "gameDate": f"2026-08-{20 + index:02d}T23:00:00Z",
                "status": {"abstractGameState": "Final"},
                "teams": {
                    "home": {"team": {"id": 10, "name": "Home"}, "score": home_score},
                    "away": {"team": {"id": 20, "name": "Away"}, "score": away_score},
                },
            }
        )
    monkeypatch.setattr(
        mlb_provider,
        "_get_sync",
        lambda *args, **kwargs: {"dates": [{"games": games}]},
    )

    form = mlb_provider.get_team_recent_form(10, date(2026, 9, 3))

    assert form["verified"] is True
    assert form["l10"]["games"] == 6
    assert form["l10"]["wins"] == 4
    assert form["l10"]["losses"] == 2
    assert "teamId=10" in form["source_url"]


def test_roster_status_identifies_injured_players(monkeypatch) -> None:
    monkeypatch.setattr(
        mlb_provider,
        "_get_sync",
        lambda *args, **kwargs: {
            "roster": [
                {
                    "person": {"id": 1, "fullName": "Active Player"},
                    "position": {"abbreviation": "SS"},
                    "status": {"code": "A", "description": "Active"},
                },
                {
                    "person": {"id": 2, "fullName": "Injured Player"},
                    "position": {"abbreviation": "P"},
                    "status": {"code": "D15", "description": "15-Day Injured List"},
                },
            ]
        },
    )

    availability = mlb_provider.get_team_availability(10)

    assert availability["verified"] is True
    assert [item["id"] for item in availability["active"]] == [1]
    assert [item["id"] for item in availability["injured"]] == [2]


def test_pitcher_workload_converts_baseball_innings_notation() -> None:
    stats = mlb_provider.pitcher_k_stats([{"strikeouts": 7, "innings_pitched": "5.2"}])

    assert stats["avg_ip"] == 5.67
