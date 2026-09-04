from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.core.database import SessionLocal
from app.models import Recommendation, Ticket, TicketLeg, User
from app.services import settlement


def _feed(*, home_runs: int = 5, away_runs: int = 3, abstract: str = "Final") -> dict:
    return {
        "gameData": {
            "status": {"abstractGameState": abstract, "detailedState": abstract},
            "teams": {
                "home": {"name": "Home Club", "id": 10},
                "away": {"name": "Away Club", "id": 20},
            },
        },
        "liveData": {
            "linescore": {
                "teams": {
                    "home": {"runs": home_runs},
                    "away": {"runs": away_runs},
                }
            },
            "boxscore": {
                "teams": {
                    "home": {
                        "players": {
                            "ID1001": {
                                "person": {"id": 1001, "fullName": "Ace Pitcher"},
                                "stats": {"pitching": {"strikeOuts": 8, "inningsPitched": "6.0"}},
                            }
                        }
                    },
                    "away": {"players": {}},
                }
            },
        },
    }


def test_final_box_and_market_outcomes() -> None:
    box = settlement._final_box(_feed(home_runs=6, away_runs=2))
    assert box is not None
    assert box["total_runs"] == 8
    assert "Home Club" in box["final_score"]

    ml = SimpleNamespace(
        market_type="moneyline",
        selection="Home Club ML",
        line=None,
        snapshot={"home_team": "Home Club", "away_team": "Away Club"},
        player_key=None,
    )
    assert settlement._derive_outcome(ml, box)["outcome"] == "WIN"

    total = SimpleNamespace(
        market_type="game_total_over",
        selection="Over 7.5 runs",
        line=Decimal("7.5"),
        snapshot={},
        player_key=None,
    )
    assert settlement._derive_outcome(total, box)["outcome"] == "WIN"

    under = SimpleNamespace(
        market_type="game_total_under",
        selection="Under 7.5 runs",
        line=Decimal("7.5"),
        snapshot={},
        player_key=None,
    )
    assert settlement._derive_outcome(under, box)["outcome"] == "LOSS"

    rl = SimpleNamespace(
        market_type="run_line",
        selection="Home Club -1.5",
        line=Decimal("-1.5"),
        snapshot={"home_team": "Home Club"},
        player_key=None,
    )
    assert settlement._derive_outcome(rl, box)["outcome"] == "WIN"

    k = SimpleNamespace(
        market_type="pitcher_strikeouts",
        selection="Ace Pitcher Over 6.5 strikeouts",
        line=Decimal("6.5"),
        snapshot={},
        player_key="mlb-pitcher-1001",
    )
    assert settlement._derive_outcome(k, box)["outcome"] == "WIN"


def _recommendation(user_id: str, **overrides: object) -> Recommendation:
    base = {
        "analysis_id": "analysis-1",
        "created_by_user_id": user_id,
        "candidate_id": "mlb-ml-home-55555",
        "event_id": "evt-1",
        "event_name": "Away Club @ Home Club",
        "sport": "mlb",
        "league": "MLB",
        "slate_date": date.today(),
        "market_type": "moneyline",
        "selection": "Home Club ML",
        "line": None,
        "american_odds": -120,
        "estimated_probability": Decimal("0.550000"),
        "implied_probability": Decimal("0.545455"),
        "adjusted_probability": Decimal("0.550000"),
        "edge": Decimal("0.010000"),
        "expected_value": Decimal("0.020000"),
        "confidence_score": 72,
        "ywp_rating": Decimal("7.20"),
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
        "thesis_key": "thesis-home",
        "script_key": "script-home",
        "data_source": "MLB_STATS_API+THE_ODDS_API",
        "source_timestamp": datetime.now(timezone.utc),
        "model_version": "test",
        "protocol_version": "test",
        "input_hash": "abc",
        "snapshot": {
            "game_pk": 55555,
            "home_team": "Home Club",
            "away_team": "Away Club",
        },
    }
    base.update(overrides)
    return Recommendation(**base)  # type: ignore[arg-type]


def test_settle_user_placed_tickets_grades_finals(monkeypatch) -> None:
    db = SessionLocal()
    try:
        user = User(
            email="settle@example.com",
            password_hash="x",
            name="Settle",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        recommendation = _recommendation(user.id)
        db.add(recommendation)
        db.flush()
        ticket = Ticket(
            user_id=user.id,
            ticket_type="custom",
            label="Custom 1-leg",
            sport="mlb",
            slate_date=date.today(),
            status="placed",
            stake=Decimal("10.00"),
            potential_payout=Decimal("18.33"),
            confidence_score=72,
            risk="medium",
            intentional_correlation=False,
            intentional_thesis_exposure=False,
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=recommendation.id,
                position=1,
                action="follow",
                selection=recommendation.selection,
                american_odds=recommendation.american_odds,
                thesis_key=recommendation.thesis_key,
                script_key=recommendation.script_key,
                status="placed",
            )
        )
        db.commit()

        monkeypatch.setattr(
            settlement, "get_live_feed", lambda game_pk: _feed(home_runs=4, away_runs=1)
        )

        items = settlement.settle_user_placed_tickets(db, user.id)
        statuses = {item.status for item in items}
        assert "graded" in statuses
        assert "ticket_settled" in statuses

        db.refresh(recommendation)
        db.refresh(ticket)
        assert recommendation.outcome == "WIN"
        assert recommendation.result is not None
        assert recommendation.result.final_score is not None
        assert ticket.status == "settled"
    finally:
        db.close()


def test_settle_skips_non_final_games(monkeypatch) -> None:
    db = SessionLocal()
    try:
        user = User(
            email="pending-settle@example.com",
            password_hash="x",
            name="Pending",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        recommendation = _recommendation(
            user.id,
            analysis_id="analysis-2",
            candidate_id="mlb-ou-66666",
            event_id="evt-2",
            market_type="game_total_over",
            selection="Over 7.5 runs",
            line=Decimal("7.5"),
            american_odds=-110,
            thesis_key="thesis-total",
            script_key="script-total",
            input_hash="def",
            snapshot={"game_pk": 66666},
        )
        db.add(recommendation)
        db.flush()
        ticket = Ticket(
            user_id=user.id,
            ticket_type="custom",
            label="Custom 1-leg",
            sport="mlb",
            slate_date=date.today(),
            status="placed",
            stake=Decimal("10.00"),
            potential_payout=Decimal("19.09"),
            confidence_score=70,
            risk="medium",
            intentional_correlation=False,
            intentional_thesis_exposure=False,
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=recommendation.id,
                position=1,
                action="follow",
                selection=recommendation.selection,
                american_odds=recommendation.american_odds,
                thesis_key=recommendation.thesis_key,
                script_key=recommendation.script_key,
                status="placed",
            )
        )
        db.commit()

        monkeypatch.setattr(
            settlement,
            "get_live_feed",
            lambda game_pk: _feed(abstract="Live"),
        )
        items = settlement.settle_user_placed_tickets(db, user.id)
        assert any(item.status == "pending" for item in items)
        db.refresh(recommendation)
        assert recommendation.outcome is None
    finally:
        db.close()


def test_settle_board_grades_unlocked_play(monkeypatch) -> None:
    """Board PLAY/LEAN/WATCH train memory even when never locked into a ticket."""
    db = SessionLocal()
    try:
        user = User(
            email="board-settle@example.com",
            password_hash="x",
            name="Board",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        recommendation = _recommendation(
            user.id,
            analysis_id="analysis-board",
            candidate_id="mlb-ml-board-77777",
            event_id="evt-board",
            input_hash="board-hash",
            snapshot={
                "game_pk": 77777,
                "home_team": "Home Club",
                "away_team": "Away Club",
            },
        )
        db.add(recommendation)
        db.commit()

        monkeypatch.setattr(
            settlement, "get_live_feed", lambda game_pk: _feed(home_runs=5, away_runs=2)
        )

        items = settlement.settle_user_board_recommendations(db, user.id)
        assert any(item.status == "graded" for item in items)
        assert all(item.ticket_id == "" for item in items if item.status == "graded")

        db.refresh(recommendation)
        assert recommendation.outcome == "WIN"
        assert recommendation.result is not None
        assert "BOARD_SETTLED" in recommendation.result.root_cause_tags
        assert "NOT_LOCKED" in recommendation.result.root_cause_tags
        assert recommendation.result.stake == Decimal("0.00")
    finally:
        db.close()


def test_settle_user_day_includes_board_and_tickets(monkeypatch) -> None:
    db = SessionLocal()
    try:
        user = User(
            email="day-settle@example.com",
            password_hash="x",
            name="Day",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        locked = _recommendation(
            user.id,
            analysis_id="analysis-day-locked",
            candidate_id="mlb-ml-day-1",
            event_id="evt-day-1",
            input_hash="day-1",
            snapshot={
                "game_pk": 80001,
                "home_team": "Home Club",
                "away_team": "Away Club",
            },
        )
        unlocked = _recommendation(
            user.id,
            analysis_id="analysis-day-board",
            candidate_id="mlb-ml-day-2",
            event_id="evt-day-2",
            selection="Away Club ML",
            thesis_key="thesis-away",
            script_key="script-away",
            input_hash="day-2",
            snapshot={
                "game_pk": 80002,
                "home_team": "Home Club",
                "away_team": "Away Club",
            },
        )
        db.add_all([locked, unlocked])
        db.flush()
        ticket = Ticket(
            user_id=user.id,
            ticket_type="custom",
            label="Locked one",
            sport="mlb",
            slate_date=date.today(),
            status="placed",
            stake=Decimal("10.00"),
            potential_payout=Decimal("18.33"),
            confidence_score=72,
            risk="medium",
            intentional_correlation=False,
            intentional_thesis_exposure=False,
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=locked.id,
                position=1,
                action="follow",
                selection=locked.selection,
                american_odds=locked.american_odds,
                thesis_key=locked.thesis_key,
                script_key=locked.script_key,
                status="placed",
            )
        )
        db.commit()

        def _feed_for(game_pk: int) -> dict:
            if game_pk == 80001:
                return _feed(home_runs=4, away_runs=1)
            return _feed(home_runs=1, away_runs=6)

        monkeypatch.setattr(settlement, "get_live_feed", _feed_for)

        items = settlement.settle_user_day(db, user.id)
        statuses = [item.status for item in items]
        assert statuses.count("graded") >= 2
        assert "ticket_settled" in statuses

        db.refresh(locked)
        db.refresh(unlocked)
        db.refresh(ticket)
        assert locked.outcome == "WIN"
        assert unlocked.outcome == "WIN"
        assert ticket.status == "settled"
        assert "NOT_LOCKED" in unlocked.result.root_cause_tags
    finally:
        db.close()


def test_future_slate_board_picks_are_ignored(monkeypatch) -> None:
    db = SessionLocal()
    try:
        user = User(
            email="future-settle@example.com",
            password_hash="x",
            name="Future",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        from datetime import timedelta

        tomorrow = date.today() + timedelta(days=1)
        recommendation = _recommendation(
            user.id,
            analysis_id="analysis-future",
            candidate_id="mlb-ml-future-90001",
            event_id="evt-future",
            slate_date=tomorrow,
            input_hash="future-hash",
            snapshot={
                "game_pk": 90001,
                "home_team": "Home Club",
                "away_team": "Away Club",
            },
        )
        db.add(recommendation)
        db.commit()

        monkeypatch.setattr(
            settlement, "get_live_feed", lambda game_pk: _feed(abstract="Scheduled")
        )

        items = settlement.settle_user_day(db, user.id, as_of=date.today())
        assert items == []
        db.refresh(recommendation)
        assert recommendation.outcome is None
    finally:
        db.close()
