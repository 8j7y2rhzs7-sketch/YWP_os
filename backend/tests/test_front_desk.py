"""Front desk reads the board and open tickets. It does not pull or spend."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import DayPrepDay, DayPrepPlay, Ticket, User
from app.services.day_prep import slate_date_for
from app.services.front_desk import DeskTicket, compose_front_desk

BANNED = ("guaranteed", "can't lose", "cant lose", "sure thing", "free money", "can't miss")


def _compose(**overrides):
    now = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)
    payload = {
        "ready_status": "idle",
        "approved_plays": 0,
        "pull2_at": None,
        "binding_sport": None,
        "ticket": None,
        "open_tickets": 0,
        "now": now,
    }
    payload.update(overrides)
    return compose_front_desk(**payload)


def _blob(body: dict) -> str:
    return " ".join(
        [
            body["headline"],
            body["detail"],
            body["notice"],
            body["primary"]["label"],
            *(beat["text"] for beat in body["beats"]),
        ]
    ).lower()


def test_copy_does_not_promise_an_outcome() -> None:
    now = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)
    ticket = DeskTicket("tix-1", "draft", None, None)
    locked = DeskTicket("tix-2", "locked", "LOCKED", now + timedelta(minutes=20))
    warned = DeskTicket("tix-3", "draft", "WARNING", None)
    placed = DeskTicket("tix-4", "placed", "LOCKED", now + timedelta(minutes=20))
    cases = [
        _compose(),
        _compose(ready_status="scheduled", pull2_at=now, binding_sport="nba"),
        _compose(ready_status="pricing"),
        _compose(ready_status="waiting_for_prices"),
        _compose(ready_status="missed"),
        _compose(ready_status="no_games"),
        _compose(ready_status="priced", approved_plays=2),
        _compose(ready_status="priced", approved_plays=0),
        _compose(ready_status="priced", approved_plays=3, ticket=ticket, open_tickets=1),
        _compose(ticket=locked, open_tickets=1),
        _compose(ticket=warned, open_tickets=1),
        _compose(ticket=placed, open_tickets=1, approved_plays=1, ready_status="priced"),
    ]
    for desk in cases:
        body = desk.model_dump(mode="json")
        text = _blob(body)
        for phrase in BANNED:
            assert phrase not in text
        assert "lock check" in body["notice"].lower()
        assert [beat["phase"] for beat in body["beats"]] == ["done", "now", "later"]


def test_draft_ticket_beats_a_priced_ready_list() -> None:
    desk = _compose(
        ready_status="priced",
        approved_plays=4,
        ticket=DeskTicket("ticket-9", "draft", None, None),
        open_tickets=1,
    )
    assert desk.primary.route == "/ticket/ticket-9"
    assert desk.primary.label == "OPEN TICKET"
    assert desk.secondary is None
    assert desk.approved_plays == 4


def test_fresh_lock_leaves_placement_with_the_user() -> None:
    now = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)
    desk = _compose(
        now=now,
        ticket=DeskTicket("ticket-9", "locked", "LOCKED", now + timedelta(minutes=15)),
        open_tickets=1,
    )
    assert desk.primary.route == "/ticket/ticket-9"
    assert "Placement stays with you" in desk.headline


def test_expired_lock_sends_them_back_to_the_ticket() -> None:
    now = datetime(2026, 10, 24, 18, 0, tzinfo=UTC)
    desk = _compose(
        now=now,
        ticket=DeskTicket("ticket-9", "draft", "LOCKED", now - timedelta(minutes=1)),
        open_tickets=1,
    )
    assert desk.primary.route == "/ticket/ticket-9"
    assert "expired" in desk.headline.lower()


def test_priced_plays_with_no_ticket_open_the_ready_list() -> None:
    desk = _compose(ready_status="priced", approved_plays=2)
    assert desk.primary.route == "/ready"
    assert desk.primary.label == "OPEN READY PLAYS"
    assert "2 approved plays" in desk.headline


def test_scheduled_board_names_the_pull_time() -> None:
    pull2 = datetime(2026, 10, 24, 22, 15, tzinfo=UTC)
    desk = _compose(ready_status="scheduled", pull2_at=pull2, binding_sport="nba")
    assert desk.primary.route == "/ready"
    assert "6:15 PM ET" in desk.detail
    assert "NBA" in desk.detail


def test_missed_window_routes_to_the_slate() -> None:
    desk = _compose(ready_status="missed")
    assert desk.primary.route == "/(tabs)/slate"
    assert desk.primary.label == "RUN TODAY'S SLATE"


def test_priced_pass_offers_another_look_without_inventing_plays() -> None:
    desk = _compose(ready_status="priced", approved_plays=0)
    assert desk.approved_plays == 0
    assert desk.primary.route == "/(tabs)/slate"
    assert desk.secondary is not None
    assert desk.secondary.route == "/ready"
    assert "pass" in desk.headline.lower()


def _user(db_session) -> User:
    user = db_session.scalar(select(User).where(User.email == "owner@ywp-os.com"))
    assert user is not None
    return user


def _ticket(user_id: str, **overrides) -> Ticket:
    now = datetime.now(UTC)
    payload = {
        "user_id": user_id,
        "ticket_type": "custom",
        "label": "Night card",
        "slate_date": now.date(),
        "risk": "medium",
        "confidence_score": 70,
        "status": "draft",
    }
    payload.update(overrides)
    return Ticket(**payload)


def test_desk_requires_login(client: TestClient) -> None:
    assert client.get("/api/v1/desk").status_code == 401


def test_empty_day_does_not_call_espn_or_kick_prep(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "app.services.day_prep.kick_day_prep",
        lambda *args, **kwargs: calls.append("kick"),
    )
    monkeypatch.setattr(
        "app.services.day_prep.ready_board_for_user",
        lambda *args, **kwargs: calls.append("board"),
    )
    monkeypatch.setattr(
        "app.services.espn_provider.get_scoreboard",
        lambda *args, **kwargs: calls.append("espn"),
    )

    response = client.get("/api/v1/desk", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bot"] == "front_desk"
    assert body["ready_status"] == "idle"
    assert body["approved_plays"] == 0
    assert body["open_tickets"] == 0
    assert body["primary"]["route"] == "/ready"
    assert calls == []


def test_get_desk_draft_beats_priced_plays(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    user = _user(db_session)
    now = datetime.now(UTC)
    slate = slate_date_for(now)
    db_session.add(
        DayPrepDay(
            slate_date=slate,
            status="priced",
            notice="Prices are in.",
            priced_pulled_at=now,
        )
    )
    db_session.add(
        DayPrepPlay(
            slate_date=slate,
            sport="nba",
            decision="PLAY",
            rank=1,
            event_id="nba-1",
            selection="Jalen Brunson Over 25.5",
            market_type="player_points",
            payload={},
        )
    )
    ticket = _ticket(user.id, updated_at=now)
    db_session.add(ticket)
    db_session.commit()

    response = client.get("/api/v1/desk", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ready_status"] == "priced"
    assert body["approved_plays"] == 1
    assert body["open_tickets"] == 1
    assert body["primary"]["route"] == f"/ticket/{ticket.id}"


def test_get_desk_uses_the_newest_unsettled_ticket(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    user = _user(db_session)
    now = datetime.now(UTC)
    older = _ticket(
        user.id,
        label="Older",
        status="placed",
        updated_at=now - timedelta(hours=2),
    )
    newer = _ticket(
        user.id,
        label="Newer",
        status="draft",
        updated_at=now,
    )
    settled = _ticket(
        user.id,
        label="Settled",
        status="placed",
        settled_at=now,
        updated_at=now + timedelta(minutes=5),
    )
    db_session.add_all([older, newer, settled])
    db_session.commit()

    response = client.get("/api/v1/desk", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["open_tickets"] == 2
    assert body["primary"]["route"] == f"/ticket/{newer.id}"
    assert "newest of 2" in body["detail"]
