"""Live board reads scores and tracks plays. It does not price or grade."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.models import DayPrepPlay
from app.services.day_prep import slate_date_for
from app.services.live_board import build_live_board


def _games():
    return [
        {
            "sport": "nba",
            "event_id": "final-1",
            "away_team": "Miami Heat",
            "home_team": "Chicago Bulls",
            "away_score": 101,
            "home_score": 99,
            "status": "FINAL",
            "detail": "Final",
            "start_time": "2026-10-24T23:00:00Z",
        },
        {
            "sport": "nba",
            "event_id": "live-1",
            "away_team": "Boston Celtics",
            "home_team": "New York Knicks",
            "away_score": 80,
            "home_score": 88,
            "status": "LIVE",
            "detail": "Q3 4:12",
            "start_time": "2026-10-24T23:30:00Z",
        },
        {
            "sport": "nfl",
            "event_id": "pre-1",
            "away_team": "Buffalo Bills",
            "home_team": "Kansas City Chiefs",
            "away_score": None,
            "home_score": None,
            "status": "PRE",
            "detail": "Not started",
            "start_time": "2026-10-25T00:20:00Z",
        },
    ]


def _play(line_actual: int) -> dict:
    return {"name": "Jalen Brunson", "PTS": line_actual}


def test_live_games_lead_and_a_short_prop_is_behind(db_session, monkeypatch) -> None:
    calls = {"players": 0, "odds": 0}

    def players(_sport: str, _event_id: str):
        calls["players"] += 1
        return [_play(18)]

    def odds(*_args, **_kwargs):
        calls["odds"] += 1
        raise AssertionError("live board spent odds")

    monkeypatch.setattr("app.services.odds_provider.get_odds", odds, raising=False)
    now = datetime.now(UTC)
    db_session.add(
        DayPrepPlay(
            slate_date=slate_date_for(now),
            sport="nba",
            decision="PLAY",
            rank=1,
            event_id="odds-nba",
            selection="Jalen Brunson Over 24.5",
            market_type="player_points",
            payload={
                "line": 24.5,
                "event_name": "Boston Celtics at New York Knicks",
            },
        )
    )
    db_session.commit()

    board = build_live_board(
        db_session,
        "user-1",
        now=now,
        espn_loader=lambda sport, _slate: [game for game in _games() if game["sport"] == sport],
        mlb_loader=lambda _slate: [],
        players_loader=players,
        mlb_feed_loader=lambda _event: None,
    )

    assert [game.status for game in board.games[:3]] == ["LIVE", "PRE", "FINAL"]
    assert board.live_count == 1
    assert board.plays[0].pace == "behind"
    assert board.plays[0].source == "board"
    assert board.plays[0].actual == 18
    assert calls["players"] == 1
    assert calls["odds"] == 0
    assert "not a wager" in board.notice.lower()


def test_a_prop_over_the_number_is_cashing_and_final_is_cashed(db_session) -> None:
    now = datetime.now(UTC)
    slate = slate_date_for(now)
    db_session.add(
        DayPrepPlay(
            slate_date=slate,
            sport="nba",
            decision="PLAY",
            rank=1,
            event_id="odds-nba",
            selection="Jalen Brunson Over 24.5",
            market_type="player_points",
            payload={
                "line": 24.5,
                "event_name": "Boston Celtics at New York Knicks",
            },
        )
    )
    db_session.commit()
    live = [game for game in _games() if game["status"] == "LIVE"]

    cashing = build_live_board(
        db_session,
        "user-1",
        now=now,
        espn_loader=lambda _sport, _slate: live,
        mlb_loader=lambda _slate: [],
        players_loader=lambda _sport, _event: [_play(26)],
        mlb_feed_loader=lambda _event: None,
    )
    assert cashing.plays[0].pace == "cashing"

    final = [{**live[0], "status": "FINAL", "detail": "Final"}]
    cashed = build_live_board(
        db_session,
        "user-1",
        now=now,
        espn_loader=lambda _sport, _slate: final,
        mlb_loader=lambda _slate: [],
        players_loader=lambda _sport, _event: [_play(30)],
        mlb_feed_loader=lambda _event: None,
    )
    assert cashed.plays[0].pace == "cashed"


def test_a_game_that_has_not_started_does_not_fetch_a_box(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        DayPrepPlay(
            slate_date=slate_date_for(now),
            sport="nfl",
            decision="LEAN",
            rank=1,
            event_id="nfl-1",
            selection="Patrick Mahomes Over 1.5 passing touchdowns",
            market_type="player_pass_tds",
            payload={
                "line": 1.5,
                "event_name": "Buffalo Bills at Kansas City Chiefs",
            },
        )
    )
    db_session.commit()

    def players(*_args, **_kwargs):
        raise AssertionError("box score fetched before tip")

    board = build_live_board(
        db_session,
        "user-1",
        now=now,
        espn_loader=lambda _sport, _slate: [game for game in _games() if game["status"] == "PRE"],
        mlb_loader=lambda _slate: [],
        players_loader=players,
        mlb_feed_loader=lambda _event: None,
    )
    assert board.plays[0].pace == "waiting"
    assert board.live_count == 0


def test_live_requires_login(client: TestClient) -> None:
    assert client.get("/api/v1/live").status_code == 401


def test_live_endpoint_does_not_call_odds(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.services.live_board._default_espn", lambda _sport, _slate: [])
    monkeypatch.setattr("app.services.live_board._default_mlb", lambda _slate: [])

    def odds(*_args, **_kwargs):
        raise AssertionError("live endpoint spent odds")

    monkeypatch.setattr("app.services.odds_provider.get_odds", odds, raising=False)
    response = client.get("/api/v1/live", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["games"] == []
    assert body["plays"] == []
    assert body["live_count"] == 0
