"""Marketing feed: scoped token auth + strict publication-eligible export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Recommendation, Ticket, TicketLeg, User


TOKEN = "marketing-test-token-please-rotate"


def _verified_snapshot(**extra: object) -> dict:
    base = {
        "schedule_verified": True,
        "probability_source": "model",
        "bookmaker": "hardrockbet",
        "bookmaker_label": "Hard Rock Bet",
        "home_team": "Home Club",
        "away_team": "Away Club",
        "start_time": (datetime.now(UTC) + timedelta(hours=3)).isoformat(),
        "readiness": "VERIFIED",
        "missing_fields": [],
    }
    base.update(extra)
    return base


def _recommendation(user_id: str, **overrides: object) -> Recommendation:
    now = datetime.now(UTC)
    base = {
        "analysis_id": "analysis-mkt",
        "created_by_user_id": user_id,
        "candidate_id": "mlb-ml-home-55555",
        "event_id": "evt-mkt-1",
        "event_name": "Away Club @ Home Club",
        "sport": "mlb",
        "league": "MLB",
        "slate_date": now.date(),
        "market_type": "moneyline",
        "selection": "Home Club ML",
        "line": None,
        "american_odds": -135,
        "estimated_probability": Decimal("0.580000"),
        "implied_probability": Decimal("0.574468"),
        "adjusted_probability": Decimal("0.580000"),
        "edge": Decimal("0.010000"),
        "expected_value": Decimal("0.020000"),
        "confidence_score": 84,
        "ywp_rating": Decimal("8.40"),
        "variance": Decimal("0.3000"),
        "data_quality": Decimal("0.9000"),
        "risk": "medium",
        "decision": "PLAY",
        "recommendation_tier": "PLAY",
        "rank": 1,
        "reason_codes": [],
        "reasoning_summary": "test",
        "warnings": [],
        "invalidation_conditions": [],
        "thesis_key": "thesis-mkt",
        "script_key": "script-mkt",
        "data_source": "MLB_STATS_API+THE_ODDS_API",
        "source_timestamp": now,
        "model_version": "test",
        "protocol_version": "test",
        "input_hash": "mkt-hash",
        "snapshot": _verified_snapshot(),
    }
    base.update(overrides)
    return Recommendation(**base)  # type: ignore[arg-type]


def _seed_ticket(db, *, eligible: bool = True, expires_in_hours: float = 2.0, **rec_overrides):
    user = User(
        email=f"mkt-{datetime.now(UTC).timestamp()}@ywp-os.com",
        password_hash=hash_password("x"),
        name="Marketing",
        timezone="America/New_York",
        role="admin",
        subscription_status="active",
    )
    db.add(user)
    db.flush()
    rec = _recommendation(user.id, **rec_overrides)
    db.add(rec)
    db.flush()
    ticket = Ticket(
        user_id=user.id,
        ticket_type="custom",
        label="Official Two-Pick Card",
        sport="mlb",
        slate_date=datetime.now(UTC).date(),
        status="locked",
        stake=Decimal("25.00"),
        potential_payout=Decimal("40.00"),
        confidence_score=84,
        risk="medium",
        intentional_correlation=False,
        intentional_thesis_exposure=False,
        publication_eligible=eligible,
        publication_eligible_at=datetime.now(UTC) if eligible else None,
        publication_expires_at=(
            datetime.now(UTC) + timedelta(hours=expires_in_hours) if eligible else None
        ),
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketLeg(
            ticket_id=ticket.id,
            recommendation_id=rec.id,
            position=1,
            action="follow",
            selection=rec.selection,
            american_odds=rec.american_odds,
            thesis_key=rec.thesis_key,
            script_key=rec.script_key,
            status="locked",
        )
    )
    db.commit()
    return user, ticket, rec


def test_marketing_feed_requires_token(client) -> None:
    settings.marketing_service_token = TOKEN
    response = client.get("/api/v1/marketing/approved-cards")
    assert response.status_code == 401


def test_marketing_feed_exports_verified_eligible_card(client) -> None:
    settings.marketing_service_token = TOKEN
    db = SessionLocal()
    try:
        _seed_ticket(db, eligible=True)
    finally:
        db.close()

    response = client.get(
        "/api/v1/marketing/approved-cards",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "generatedAt" in body
    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["status"] == "VERIFIED"
    assert card["publicationEligible"] is True
    assert card["demo"] is False
    assert card["dataQuality"] == "COMPLETE"
    assert card["ywpScore"] == 84
    assert card["modelProbability"] == 0.58
    assert card["sportsbook"] == "Hard Rock Bet"
    assert len(card["legs"]) == 1
    # No secret / PII / bankroll fields
    blob = response.text.casefold()
    for banned in ("password", "bankroll", "stake", "jwt", "odds_api", "email", "25.00"):
        assert banned not in blob


def test_marketing_feed_excludes_demo_and_stale_and_revoked(client) -> None:
    settings.marketing_service_token = TOKEN
    db = SessionLocal()
    try:
        _seed_ticket(
            db,
            eligible=True,
            data_source="YWP_DEMO_PROVIDER",
            snapshot=_verified_snapshot(probability_source="demo", readiness="DEMO"),
        )
        _seed_ticket(db, eligible=True, expires_in_hours=-1)
        _seed_ticket(db, eligible=False)
        _seed_ticket(
            db,
            eligible=True,
            decision="SKIP",
            snapshot=_verified_snapshot(readiness="VERIFIED"),
        )
        _seed_ticket(
            db,
            eligible=True,
            data_quality=Decimal("0.50"),
            snapshot=_verified_snapshot(missing_fields=["lineup"]),
        )
    finally:
        db.close()

    response = client.get(
        "/api/v1/marketing/approved-cards",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.json()["cards"] == []


def test_admin_can_rotate_marketing_token_and_read_feed(client) -> None:
    settings.marketing_service_token = None
    db = SessionLocal()
    try:
        user, ticket, _ = _seed_ticket(db, eligible=True)
        user.role = "admin"
        user.email = "mkt-rotate@ywp-os.com"
        user.password_hash = hash_password("StrongYwp!2026")
        user.subscription_status = "active"
        db.commit()
        ticket_id = ticket.id
    finally:
        db.close()

    # Unconfigured → 503
    assert client.get("/api/v1/marketing/approved-cards").status_code == 503

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "mkt-rotate@ywp-os.com", "password": "StrongYwp!2026"},
    )
    assert login.status_code == 200, login.text
    admin_token = login.json()["access_token"]
    rotated = client.post(
        "/api/v1/marketing/rotate-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rotated.status_code == 200, rotated.text
    mkt_token = rotated.json()["token"]
    assert len(mkt_token) >= 20

    response = client.get(
        "/api/v1/marketing/approved-cards",
        headers={"Authorization": f"Bearer {mkt_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["cards"]) == 1
    assert response.json()["cards"][0]["id"] == ticket_id


def test_admin_can_revoke_publication_eligibility(client) -> None:
    settings.marketing_service_token = TOKEN
    db = SessionLocal()
    try:
        user, ticket, _ = _seed_ticket(db, eligible=True)
        user.role = "admin"
        user.email = "mkt-admin@ywp-os.com"
        user.password_hash = hash_password("StrongYwp!2026")
        user.subscription_status = "active"
        db.commit()
        ticket_id = ticket.id
    finally:
        db.close()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "mkt-admin@ywp-os.com", "password": "StrongYwp!2026"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    revoke = client.post(
        f"/api/v1/marketing/tickets/{ticket_id}/publication-eligibility",
        headers={"Authorization": f"Bearer {token}"},
        json={"eligible": False},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["publication_eligible"] is False

    response = client.get(
        "/api/v1/marketing/approved-cards",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert all(card["id"] != ticket_id for card in response.json()["cards"])
