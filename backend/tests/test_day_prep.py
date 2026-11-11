"""Day prep: free schedule first, one learned priced pull, ready cross parlays."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.models import DayPrepLead, DayPrepPlay, Recommendation, User
from app.schemas import CandidateInput
from app.services.day_prep import (
    DEFAULT_LEAD_MINUTES,
    ScheduledGame,
    advance_day_prep,
    binding_pull_time,
    coverage,
    learn_next_lead,
    slate_date_for,
)


def test_lead_waits_when_the_board_was_thin_and_starts_earlier_when_it_was_full() -> None:
    assert learn_next_lead(75, 0.2, 90) == 60
    assert learn_next_lead(30, 0.2, 30) == 30
    assert learn_next_lead(75, 0.9, 28) == 85
    assert learn_next_lead(75, 0.9, 75) == 75
    assert learn_next_lead(180, 1.0, 10) == 180
    assert learn_next_lead(20, 0.0, 10) == 25


def test_one_priced_pull_uses_the_earliest_start() -> None:
    slate = datetime(2026, 10, 24, 16, 0, tzinfo=UTC)
    early = ScheduledGame(
        sport="nfl",
        event_id="nfl-1",
        event_name="Bills at Chiefs",
        home_team="Kansas City Chiefs",
        away_team="Buffalo Bills",
        commence_time=slate + timedelta(hours=2),
    )
    late = ScheduledGame(
        sport="nba",
        event_id="nba-1",
        event_name="Celtics at Knicks",
        home_team="New York Knicks",
        away_team="Boston Celtics",
        commence_time=slate + timedelta(hours=8),
    )
    pull2, lead, sport = binding_pull_time(
        [late, early],
        {"nfl": 60, "nba": 90},
        slate_date_for(slate),
    )
    assert sport == "nfl"
    assert lead == 60
    assert pull2 == early.commence_time - timedelta(minutes=60)


def test_props_missing_keeps_completeness_low() -> None:
    game = ScheduledGame(
        sport="nba",
        event_id="nba-1",
        event_name="Boston Celtics at New York Knicks",
        home_team="New York Knicks",
        away_team="Boston Celtics",
        commence_time=datetime(2026, 10, 24, 23, 0, tzinfo=UTC),
    )
    priced = _candidate(event_name=game.event_name, market_type="moneyline")
    props = _candidate(
        candidate_id="prop-1",
        event_name=game.event_name,
        market_type="player_points",
        selection="Jalen Brunson Over 25.5",
    )
    assert coverage([game], [priced]) < 0.5
    assert coverage([game], [priced, props]) == 1.0
    assert coverage([game], []) == 0.0


def test_schedule_pull_does_not_price(db_session) -> None:
    now = datetime(2026, 10, 24, 16, 0, tzinfo=UTC)
    priced_calls: list[str] = []
    game = _game(now + timedelta(hours=6))

    result = advance_day_prep(
        db_session,
        now=now,
        schedule_loader=lambda _slate: [game, _game(now + timedelta(hours=7), event_id="nba-2")],
        slate_loader=lambda sport, _slate: priced_calls.append(sport) or [],
        grader=lambda _db, _rows: [],
    )

    assert priced_calls == []
    assert result["status"] == "scheduled"
    assert result["lead_minutes"] == DEFAULT_LEAD_MINUTES
    assert result["binding_sport"] == "nba"


def test_priced_pull_is_once_per_sport_and_learns_an_earlier_lead(db_session) -> None:
    now = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    commence = now + timedelta(minutes=30)
    game = _game(commence)
    calls: list[str] = []

    def slate(sport: str, _slate) -> list[CandidateInput]:
        calls.append(sport)
        return [
            _candidate(event_name=game.event_name, market_type="player_points"),
            _candidate(
                candidate_id="ml-1",
                event_name=game.event_name,
                market_type="moneyline",
                selection="New York Knicks ML",
            ),
        ]

    first = advance_day_prep(
        db_session,
        now=now,
        schedule_loader=lambda _slate: [game, _game(commence, event_id="nba-2")],
        slate_loader=slate,
        grader=lambda _db, _rows: [_play_payload("nba", "Brunson Over 25.5")],
    )
    assert calls == ["nba"]
    assert first["status"] == "priced"
    lead = db_session.scalar(select(DayPrepLead).where(DayPrepLead.sport == "nba"))
    assert lead is not None
    assert lead.lead_minutes == DEFAULT_LEAD_MINUTES + 10
    assert lead.samples == 1

    calls.clear()
    second = advance_day_prep(
        db_session,
        now=now + timedelta(minutes=5),
        schedule_loader=lambda _slate: [_ for _ in ()],
        slate_loader=slate,
        grader=lambda _db, _rows: [],
    )
    assert calls == []
    assert second["status"] == "priced"


def test_missed_window_does_not_spend(db_session) -> None:
    now = datetime(2026, 10, 24, 23, 30, tzinfo=UTC)
    calls: list[str] = []
    result = advance_day_prep(
        db_session,
        now=now,
        schedule_loader=lambda _slate: [_game(now - timedelta(hours=1))],
        slate_loader=lambda sport, _slate: calls.append(sport) or [],
        grader=lambda _db, _rows: [],
    )
    assert calls == []
    assert result["status"] == "missed"


def test_ready_board_copies_plays_and_recommends_a_cross_parlay(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    user = db_session.scalar(select(User).where(User.email == "owner@ywp-os.com"))
    assert user is not None
    now = datetime.now(UTC)
    slate = slate_date_for(now)
    nba = _game(now + timedelta(minutes=40))
    mlb = ScheduledGame(
        sport="mlb",
        event_id="mlb-1",
        event_name="Tampa Bay Rays at Cleveland Guardians",
        home_team="Cleveland Guardians",
        away_team="Tampa Bay Rays",
        commence_time=now + timedelta(minutes=70),
    )

    def slate_loader(sport: str, _slate_date):
        if sport == "nba":
            return [_candidate(event_name=nba.event_name, market_type="player_points")]
        return [
            _candidate(
                candidate_id="mlb-hit",
                event_id="odds-mlb",
                event_name=mlb.event_name,
                sport="mlb",
                league="MLB",
                market_type="player_hits",
                selection="Yandy Diaz Over 0.5 hits",
                thesis_key="diaz-hits",
                script_key="script-diaz",
            )
        ]

    advance_day_prep(
        db_session,
        now=now,
        schedule_loader=lambda _slate: [nba, mlb],
        slate_loader=slate_loader,
        grader=lambda _db, _rows: [
            _play_payload(
                "nba",
                "Jalen Brunson Over 25.5",
                event_id="odds-nba",
                thesis="brunson",
                slate_date=slate.isoformat(),
            ),
            _play_payload(
                "mlb",
                "Yandy Diaz Over 0.5 hits",
                event_id="odds-mlb",
                thesis="diaz",
                market_type="player_hits",
                slate_date=slate.isoformat(),
            ),
        ],
    )
    db_session.commit()

    response = client.get("/api/v1/sports/ready-board", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "priced"
    assert body["slate_date"] == slate.isoformat()
    assert len(body["plays"]) == 2
    assert {item["sport"] for item in body["plays"]} == {"nba", "mlb"}
    assert "cross_2" in body["cross_parlays"]
    legs = {leg["sport"] for leg in body["cross_parlays"]["cross_2"]["legs"]}
    assert legs == {"nba", "mlb"}
    assert body["cards"]["max_bet"]["legs"]
    analysis_id = body["analysis_id"]
    owned = db_session.scalars(
        select(Recommendation).where(Recommendation.analysis_id == analysis_id)
    ).all()
    assert owned
    assert {row.created_by_user_id for row in owned} == {user.id}
    stored = db_session.scalars(select(DayPrepPlay)).all()
    assert stored
    assert all(row.decision == "PLAY" for row in stored)

    again = client.get("/api/v1/sports/ready-board", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["analysis_id"] == analysis_id


def test_day_prep_tick_rejects_a_bad_token(client: TestClient, monkeypatch) -> None:
    called = {"count": 0}

    def _fake(_db):
        called["count"] += 1
        return {"status": "scheduled", "notice": "test"}

    monkeypatch.setattr("app.api.day_prep.advance_day_prep", _fake)
    monkeypatch.setattr(settings, "day_prep_token", "prep-token-value")
    rejected = client.post(
        "/api/v1/sports/day-prep/tick",
        headers={"X-YWP-Day-Prep-Token": "nope"},
    )
    assert rejected.status_code == 401
    assert called["count"] == 0
    missing = client.post("/api/v1/sports/day-prep/tick")
    assert missing.status_code == 401
    accepted = client.post(
        "/api/v1/sports/day-prep/tick",
        headers={"X-YWP-Day-Prep-Token": "prep-token-value"},
        params={"wait": "true"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "scheduled"
    assert called["count"] == 1


def _game(commence: datetime, event_id: str = "nba-1") -> ScheduledGame:
    return ScheduledGame(
        sport="nba",
        event_id=event_id,
        event_name="Boston Celtics at New York Knicks",
        home_team="New York Knicks",
        away_team="Boston Celtics",
        commence_time=commence,
    )


def _candidate(**changes) -> CandidateInput:
    now = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)
    data = {
        "candidate_id": "nba-1",
        "event_id": "odds-nba",
        "event_name": "Boston Celtics at New York Knicks",
        "sport": "nba",
        "league": "NBA",
        "start_time": now,
        "market_type": "player_points",
        "selection": "Jalen Brunson Over 25.5",
        "american_odds": -115,
        "estimated_probability": 0.58,
        "probability_source": "model",
        "variance": 0.3,
        "data_quality": 0.86,
        "data_source": "TEST",
        "source_timestamp": now,
        "thesis_key": "brunson-pts",
        "script_key": "script-brunson",
    }
    data.update(changes)
    return CandidateInput(**data)


def _play_payload(
    sport: str,
    selection: str,
    *,
    event_id: str = "odds-nba",
    thesis: str = "play",
    market_type: str = "player_points",
    slate_date: str = "2026-10-24",
) -> dict:
    now = datetime.now(UTC) - timedelta(minutes=5)
    event_name = (
        "Boston Celtics at New York Knicks"
        if sport == "nba"
        else "Tampa Bay Rays at Cleveland Guardians"
    )
    return {
        "candidate_id": f"{sport}-{thesis}",
        "event_id": event_id,
        "event_name": event_name,
        "sport": sport,
        "league": sport.upper(),
        "slate_date": slate_date,
        "mode": "pregame",
        "market_type": market_type,
        "market_period": "full_game",
        "selection": selection,
        "line": "25.5",
        "american_odds": -115,
        "estimated_probability": 0.58,
        "implied_probability": 0.53,
        "adjusted_probability": 0.58,
        "edge": 0.05,
        "expected_value": 0.04,
        "confidence_score": 90,
        "ywp_rating": 8.3,
        "vision_score": 7.4,
        "miss_by_one_risk": 0.2,
        "reliability": 0.8,
        "stability": 0.8,
        "variance": 0.28,
        "data_quality": 0.86,
        "risk": "medium",
        "risk_tier": "Moderate",
        "variance_rating": "Medium",
        "edge_class": "Moderate",
        "expected_value_label": "Positive",
        "suggested_stake_pct": 0.01,
        "decision": "PLAY",
        "recommendation_tier": "core_parlay",
        "rank": 1 if sport == "nba" else 2,
        "reason_codes": ["DAY_PREP"],
        "reasoning_summary": "Approved before the app was opened.",
        "warnings": [],
        "safer_alternative": None,
        "higher_upside": None,
        "invalidation_conditions": [],
        "live_trigger": None,
        "hedge": None,
        "quick_cash": False,
        "chain_reaction_key": None,
        "thesis_key": f"thesis-{thesis}",
        "script_key": f"script-{thesis}",
        "player_key": thesis,
        "data_source": "TEST",
        "source_timestamp": now.isoformat(),
        "model_version": "ywp-sports-v3.1.0",
        "protocol_version": "2026.09.03",
        "input_hash": f"hash-{thesis}",
        "snapshot": {
            "probability_source": "model",
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
            "home_team": "New York Knicks" if sport == "nba" else "Cleveland Guardians",
            "away_team": "Boston Celtics" if sport == "nba" else "Tampa Bay Rays",
            "start_time": now.isoformat(),
        },
    }
