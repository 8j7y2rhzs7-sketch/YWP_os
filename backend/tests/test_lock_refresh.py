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


def test_wnba_points_prop_lock_refresh_uses_player_props_endpoint() -> None:
    rec = _recommendation(
        id="rec-wnba-pts",
        sport="wnba",
        selection="Georgia Amoore Over 8.5 points",
        market_type="player_points_over",
        line=Decimal("8.5"),
        event_id="wnba-event-1",
        data_source="THE_ODDS_API+ESPN_PLAYER_PROP_MODEL",
    )
    props_payload = {
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "Georgia Amoore",
                                "price": -115,
                                "point": 8.5,
                            },
                            {
                                "name": "Under",
                                "description": "Georgia Amoore",
                                "price": -105,
                                "point": 8.5,
                            },
                        ],
                    }
                ],
            }
        ]
    }
    with (
        patch("app.services.lock_refresh.odds_api_configured", return_value=True),
        patch(
            "app.services.lock_refresh.get_player_props",
            return_value=props_payload,
        ) as props_mock,
        patch(
            "app.services.lock_refresh.get_event_odds",
            side_effect=AssertionError("event odds must not be used for player props"),
        ),
    ):
        update = fetch_recommendation_lock_update(rec)
    assert update is not None
    assert update.market_available is True
    assert update.market_status == "OPEN"
    assert update.current_odds == -115
    props_mock.assert_called()
    assert props_mock.call_args.kwargs.get("markets") == "player_points" or (
        len(props_mock.call_args.args) >= 1
    )


def test_wnba_double_double_lock_refresh_allows_yes_no_without_point() -> None:
    rec = _recommendation(
        id="rec-wnba-dd",
        sport="wnba",
        selection="Kiki Iriafen Double Double",
        market_type="player_double_double_yes",
        line=None,
        event_id="wnba-event-2",
        data_source="THE_ODDS_API+ESPN_PLAYER_PROP_MODEL",
    )
    props_payload = {
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "player_double_double",
                        "outcomes": [
                            {
                                "name": "Yes",
                                "description": "Kiki Iriafen",
                                "price": 240,
                                "point": None,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with (
        patch("app.services.lock_refresh.odds_api_configured", return_value=True),
        patch(
            "app.services.lock_refresh.get_player_props",
            return_value=props_payload,
        ),
    ):
        update = fetch_recommendation_lock_update(rec)
    assert update is not None
    assert update.market_available is True
    assert update.current_odds == 240
    assert update.market_status == "OPEN"


def test_mlb_hrr_and_total_bases_map_to_odds_api_batter_keys() -> None:
    """Board market_types player_hrr / player_total_bases must hit Odds batter_* keys."""
    from app.services.lock_refresh import _odds_api_player_market_key

    assert _odds_api_player_market_key("player_hrr_over") == "batter_hits_runs_rbis"
    assert _odds_api_player_market_key("player_total_bases_over") == "batter_total_bases"
    assert _odds_api_player_market_key("player_hits_over") == "batter_hits"
    assert _odds_api_player_market_key("player_rbi_under") == "batter_rbis"


def test_mlb_hrr_lock_refresh_uses_batter_hits_runs_rbis_market() -> None:
    rec = _recommendation(
        id="rec-mlb-hrr",
        sport="mlb",
        selection="Hao-Yu Lee Over 1.5 hits+runs+RBIs",
        market_type="player_hrr_over",
        line=Decimal("1.5"),
        event_id="mlb-odds-event-1",
        data_source="MLB_STATS_API+THE_ODDS_API",
        snapshot={
            "game_pk": 776543,
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
            "home_team": "Home",
            "away_team": "Away",
        },
    )
    props_payload = {
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "batter_hits_runs_rbis",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "Hao-Yu Lee",
                                "price": -120,
                                "point": 1.5,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with (
        patch("app.services.lock_refresh.odds_api_configured", return_value=True),
        patch(
            "app.services.lock_refresh.get_game_context",
            return_value={
                "status": "Preview",
                "detailed_status": "Pre-Game",
                "home": {"lineup_confirmed": False},
                "away": {"lineup_confirmed": False},
                "weather": {},
            },
        ),
        patch(
            "app.services.lock_refresh.get_player_props",
            return_value=props_payload,
        ) as props_mock,
    ):
        update = fetch_recommendation_lock_update(rec)
    assert update is not None
    assert update.market_available is True
    assert update.market_status == "OPEN"
    assert update.current_odds == -120
    assert props_mock.call_args.kwargs.get("markets") == "batter_hits_runs_rbis"
    assert not any("CLOSED" in n for n in (update.notes or []))


def test_mlb_prop_refresh_miss_keeps_pregame_open_with_ticket_odds() -> None:
    """Provider miss must not force CLOSED/SKIP while the game is still Pre-Game."""
    rec = _recommendation(
        id="rec-mlb-tb",
        sport="mlb",
        selection="Brandon Lowe Over 0.5 total bases",
        market_type="player_total_bases_over",
        line=Decimal("0.5"),
        american_odds=-110,
        event_id="mlb-odds-event-2",
        data_source="MLB_STATS_API+THE_ODDS_API",
        snapshot={
            "game_pk": 776544,
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
        },
    )
    with (
        patch("app.services.lock_refresh.odds_api_configured", return_value=True),
        patch(
            "app.services.lock_refresh.get_game_context",
            return_value={
                "status": "Preview",
                "detailed_status": "Pre-Game",
                "home": {},
                "away": {},
                "weather": {},
            },
        ),
        patch("app.services.lock_refresh.get_player_props", return_value=None),
    ):
        update = fetch_recommendation_lock_update(rec)
    assert update is not None
    assert update.market_available is True
    assert update.market_status == "OPEN"
    assert update.current_odds == -110
    assert any("using ticket odds" in n for n in (update.notes or []))


def test_lock_check_warns_instead_of_skip_when_prop_uses_ticket_odds() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from app.core.database import Base
    from app.models import BankrollAccount, Recommendation, Ticket, TicketLeg, User

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine)()

    user = User(
        email="prop-warn@ywp.test",
        password_hash="x",
        name="PropWarn",
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
        analysis_id="a-prop",
        created_by_user_id=user.id,
        candidate_id="mlb-hrr-1",
        event_id="odds-event-prop",
        event_name="Away @ Home",
        sport="mlb",
        league="MLB",
        slate_date=now.date(),
        mode="pregame",
        market_type="player_hrr_over",
        market_period="full_game",
        selection="Hao-Yu Lee Over 1.5 hits+runs+RBIs",
        line=Decimal("1.5"),
        american_odds=-115,
        estimated_probability=Decimal("0.55"),
        implied_probability=Decimal("0.535"),
        adjusted_probability=Decimal("0.55"),
        edge=Decimal("0.015"),
        expected_value=Decimal("0.02"),
        confidence_score=80,
        ywp_rating=Decimal("7.50"),
        vision_score=Decimal("7.00"),
        miss_by_one_risk=Decimal("0.25"),
        reliability=Decimal("0.80"),
        stability=Decimal("0.80"),
        variance=Decimal("0.35"),
        data_quality=Decimal("0.85"),
        risk="medium",
        risk_tier="Moderate",
        variance_rating="Medium",
        edge_class="Slight",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.01"),
        decision="PLAY",
        recommendation_tier="core_parlay",
        rank=1,
        reason_codes=["INDEPENDENT_MODEL"],
        reasoning_summary="Model edge",
        warnings=[],
        invalidation_conditions=[],
        thesis_key="thesis-hrr",
        script_key="script-hrr",
        data_source="MLB_STATS_API+THE_ODDS_API",
        source_timestamp=now,
        model_version="test",
        protocol_version="test",
        input_hash="hash-prop",
        snapshot={
            "game_pk": 776543,
            "game_status": "PRE_GAME",
            "market_status": "OPEN",
        },
    )
    session.add(rec)
    session.flush()
    ticket = Ticket(
        user_id=user.id,
        ticket_type="custom",
        label="Prop ticket",
        sport="mlb",
        slate_date=now.date(),
        status="draft",
        stake=Decimal("10.00"),
        potential_payout=Decimal("18.00"),
        confidence_score=80,
        risk="medium",
        intentional_correlation=False,
        intentional_thesis_exposure=False,
    )
    session.add(ticket)
    session.flush()
    session.add(
        TicketLeg(
            ticket_id=ticket.id,
            recommendation_id=rec.id,
            position=1,
            action="follow",
            selection=rec.selection,
            american_odds=rec.american_odds,
            thesis_key=rec.thesis_key,
            script_key=rec.script_key,
            status="draft",
        )
    )
    session.commit()

    ticket = session.get(Ticket, ticket.id)
    assert ticket is not None
    # Reload legs
    _ = ticket.legs

    update = CurrentStateUpdate(
        recommendation_id=rec.id,
        source_timestamp=now,
        current_odds=-115,
        market_available=True,
        data_quality=0.85,
        game_status="PRE_GAME",
        market_status="OPEN",
        notes=[
            "MLB live feed refreshed (Pre-Game).",
            "Player prop market could not be refreshed (batter_hits_runs_rbis); using ticket odds.",
            "Verify the live sportsbook price before locking.",
        ],
    )
    result = run_lock_check(
        session,
        ticket,
        user.id,
        LockCheckRequest(updates=[update]),
    )
    assert result.lock_status == "WARNING"
    assert result.lock_status != "SKIP"
    legs = result.leg_results or []
    assert legs and legs[0]["status"] == "WARNING"
    session.close()
