"""Lock Check must refresh live provider state when the client sends updates=[]."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas import CurrentStateUpdate, LockCheckRequest
from app.services.lock_check import run_lock_check
from app.services.lock_refresh import (
    ensure_lock_updates,
    fetch_recommendation_lock_update,
)


def _recommendation(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = {
        "id": "rec-over-1",
        "candidate_id": "mlb-over-776543",
        "event_id": "odds-event-1",
        "event_name": "Away @ Home",
        "sport": "mlb",
        "selection": "Over 7.5 runs",
        "market_type": "game_total_over",
        "line": Decimal("7.5"),
        "american_odds": -105,
        "edge": Decimal("0.08"),
        "confidence_score": 90,
        "data_quality": Decimal("0.88"),
        "data_source": "MLB_STATS_API+THE_ODDS_API",
        "reason_codes": ["INDEPENDENT_MODEL"],
        "snapshot": {
            "candidate_id": "mlb-over-776543",
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
            "lineup_confirmed": True,
            "market_is_pitcher_strikeout_over": False,
        },
        "source_timestamp": now,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _ticket(recommendation: SimpleNamespace) -> SimpleNamespace:
    leg = SimpleNamespace(
        action="follow",
        recommendation=recommendation,
        thesis_key="thesis-over",
        script_key="script-runs",
    )
    return SimpleNamespace(
        id="ticket-1",
        user_id="user-1",
        ticket_type="max_bet",
        stake=Decimal("10.00"),
        confidence_score=90,
        intentional_correlation=False,
        intentional_thesis_exposure=False,
        override_acknowledged=False,
        legs=[leg],
        status="draft",
        last_lock_status=None,
        last_lock_expires_at=None,
    )


def test_ensure_lock_updates_fetches_when_client_sends_empty() -> None:
    rec = _recommendation()
    ticket = _ticket(rec)
    fake = CurrentStateUpdate(
        recommendation_id=rec.id,
        source_timestamp=datetime.now(UTC),
        current_odds=-108,
        market_available=True,
        data_quality=0.88,
        game_status="PRE_GAME",
        market_status="OPEN",
        notes=["Price refreshed from draftkings."],
    )
    with patch(
        "app.services.lock_refresh.fetch_recommendation_lock_update",
        return_value=fake,
    ):
        merged = ensure_lock_updates(ticket, [])
    assert len(merged) == 1
    assert merged[0].current_odds == -108
    assert "refreshed" in " ".join(merged[0].notes).lower()


def test_mlb_fetch_builds_update_from_providers() -> None:
    rec = _recommendation()
    with (
        patch("app.services.lock_refresh.get_game_context", return_value={
            "status": "Preview",
            "detailed_status": "Pre-Game",
            "home": {"lineup_confirmed": True},
            "away": {"lineup_confirmed": True},
            "weather": {"verified": True, "condition": "Clear"},
        }),
        patch("app.services.lock_refresh.odds_api_configured", return_value=True),
        patch(
            "app.services.lock_refresh.get_event_odds",
            return_value={
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "price": -110, "point": 7.5},
                                    {"name": "Under", "price": -110, "point": 7.5},
                                ],
                            }
                        ],
                    }
                ]
            },
        ),
    ):
        update = fetch_recommendation_lock_update(rec)
    assert update is not None
    assert update.recommendation_id == rec.id
    assert update.current_odds == -110
    assert update.market_available is True
    assert update.game_status == "PRE_GAME"
    assert update.data_quality and update.data_quality >= 0.7


def test_run_lock_check_empty_updates_uses_server_refresh(db_session=None) -> None:
    """Empty client updates must not SKIP solely for missing snapshot."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from app.core.database import Base
    from app.models import (
        BankrollAccount,
        Recommendation,
        Ticket,
        TicketLeg,
        User,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine)()

    user = User(
        email="lock@ywp.test",
        password_hash="x",
        name="Lock",
        timezone="UTC",
    )
    session.add(user)
    session.flush()
    session.add(
        BankrollAccount(
            user_id=user.id,
            balance=Decimal("1000.00"),
            currency="USD",
            max_stake_pct=Decimal("0.05"),
        )
    )

    now = datetime.now(UTC)
    rec = Recommendation(
        analysis_id="a1",
        created_by_user_id=user.id,
        candidate_id="mlb-over-776543",
        event_id="odds-event-1",
        event_name="Away @ Home",
        sport="mlb",
        league="MLB",
        slate_date=now.date(),
        mode="pregame",
        market_type="game_total_over",
        market_period="full_game",
        selection="Over 7.5 runs",
        line=Decimal("7.5"),
        american_odds=-105,
        estimated_probability=Decimal("0.58"),
        implied_probability=Decimal("0.512"),
        adjusted_probability=Decimal("0.58"),
        edge=Decimal("0.068"),
        expected_value=Decimal("0.05"),
        confidence_score=90,
        ywp_rating=Decimal("8.50"),
        vision_score=Decimal("7.50"),
        miss_by_one_risk=Decimal("0.20"),
        reliability=Decimal("0.90"),
        stability=Decimal("0.85"),
        variance=Decimal("0.30"),
        data_quality=Decimal("0.88"),
        risk="medium",
        risk_tier="Moderate",
        variance_rating="Medium",
        edge_class="Strong",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.01"),
        decision="PLAY",
        recommendation_tier="core_parlay",
        rank=1,
        reason_codes=["INDEPENDENT_MODEL"],
        reasoning_summary="Model edge",
        warnings=[],
        thesis_key="thesis-over",
        script_key="script-runs",
        data_source="MLB_STATS_API+THE_ODDS_API",
        source_timestamp=now,
        model_version="test",
        protocol_version="test",
        input_hash="abc",
        snapshot={
            "candidate_id": "mlb-over-776543",
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
            "lineup_confirmed": True,
        },
    )
    session.add(rec)
    session.flush()

    ticket = Ticket(
        user_id=user.id,
        sport="mlb",
        ticket_type="max_bet",
        label="Max Bet",
        slate_date=now.date(),
        status="draft",
        stake=Decimal("10.00"),
        potential_payout=Decimal("19.05"),
        confidence_score=90,
        risk="medium",
        intentional_correlation=False,
        intentional_thesis_exposure=False,
        override_acknowledged=False,
    )
    session.add(ticket)
    session.flush()
    session.add(
        TicketLeg(
            ticket_id=ticket.id,
            recommendation_id=rec.id,
            position=1,
            selection=rec.selection,
            action="follow",
            american_odds=-105,
            thesis_key="thesis-over",
            script_key="script-runs",
            status="draft",
        )
    )
    session.commit()

    loaded = session.get(Ticket, ticket.id)
    assert loaded is not None
    # Re-load with relationship
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models import Ticket as TicketModel

    loaded = session.scalar(
        select(TicketModel)
        .options(selectinload(TicketModel.legs).selectinload(TicketLeg.recommendation))
        .where(TicketModel.id == ticket.id)
    )
    assert loaded is not None

    fake = CurrentStateUpdate(
        recommendation_id=rec.id,
        source_timestamp=datetime.now(UTC),
        current_odds=-108,
        market_available=True,
        data_quality=0.88,
        game_status="PRE_GAME",
        market_status="OPEN",
        notes=["Price refreshed from draftkings."],
    )
    with patch(
        "app.services.lock_refresh.fetch_recommendation_lock_update",
        return_value=fake,
    ):
        result = run_lock_check(
            session,
            loaded,
            user.id,
            LockCheckRequest(updates=[]),
        )

    assert result.lock_status == "LOCKED"
    assert result.checks["data_quality"] == "PASS"
    assert not any(
        "No fresh provider snapshot was supplied" in note
        for leg in result.leg_results
        for note in leg.get("changes_detected", [])
    )
    session.close()
