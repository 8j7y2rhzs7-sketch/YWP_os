from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import LearningEvent, Recommendation, Ticket, TicketLeg, User
from app.services.eod_quality import run_eod_quality_pass


def _recommendation(user_id: str, **overrides: object) -> Recommendation:
    base = {
        "analysis_id": "analysis-eod",
        "created_by_user_id": user_id,
        "candidate_id": "mlb-ml-home-eod",
        "event_id": "evt-eod",
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
        "recommendation_tier": "core_parlay",
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
        "input_hash": "eod-abc",
        "snapshot": {
            "game_pk": 55555,
            "home_team": "Home Club",
            "away_team": "Away Club",
        },
        "outcome": "WIN",
    }
    base.update(overrides)
    return Recommendation(**base)  # type: ignore[arg-type]


def test_eod_quality_flags_missed_winner_and_packaging_gap() -> None:
    db = SessionLocal()
    try:
        user = User(
            email="eod@example.com",
            password_hash="x",
            name="EOD",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()

        locked_win = _recommendation(
            user.id,
            selection="Locked Winner",
            outcome="WIN",
            candidate_id="locked-win",
            event_id="evt-locked",
            thesis_key="thesis-locked",
            script_key="script-locked",
            input_hash="locked-win",
        )
        locked_loss = _recommendation(
            user.id,
            selection="Locked Loser",
            outcome="LOSS",
            decision="PLAY",
            candidate_id="locked-loss",
            event_id="evt-locked-loss",
            thesis_key="thesis-locked-loss",
            script_key="script-locked-loss",
            input_hash="locked-loss",
        )
        missed = _recommendation(
            user.id,
            selection="Missed Board Winner",
            outcome="WIN",
            decision="LEAN",
            candidate_id="missed-win",
            event_id="evt-missed",
            thesis_key="thesis-missed",
            script_key="script-missed",
            input_hash="missed-win",
        )
        good_dodge = _recommendation(
            user.id,
            selection="Skipped Loser",
            outcome="LOSS",
            decision="SKIP",
            candidate_id="skip-loss",
            event_id="evt-skip-loss",
            thesis_key="thesis-skip-loss",
            script_key="script-skip-loss",
            input_hash="skip-loss",
            data_source="THE_ODDS_API_BOARD",
            reason_codes=["SPORTSBOOK_MENU"],
            snapshot={"data_source": "THE_ODDS_API_BOARD", "reason_codes": ["SPORTSBOOK_MENU"]},
        )
        false_skip = _recommendation(
            user.id,
            selection="Skipped Winner",
            outcome="WIN",
            decision="SKIP",
            candidate_id="skip-win",
            event_id="evt-skip-win",
            thesis_key="thesis-skip-win",
            script_key="script-skip-win",
            input_hash="skip-win",
            data_source="THE_ODDS_API_BOARD",
            reason_codes=["SPORTSBOOK_MENU"],
            snapshot={"data_source": "THE_ODDS_API_BOARD", "reason_codes": ["SPORTSBOOK_MENU"]},
        )
        db.add_all([locked_win, locked_loss, missed, good_dodge, false_skip])
        db.flush()

        ticket = Ticket(
            user_id=user.id,
            ticket_type="custom",
            label="EOD locked",
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
        for position, rec in enumerate((locked_win, locked_loss), start=1):
            db.add(
                TicketLeg(
                    ticket_id=ticket.id,
                    recommendation_id=rec.id,
                    position=position,
                    action="follow",
                    selection=rec.selection,
                    american_odds=rec.american_odds,
                    thesis_key=rec.thesis_key,
                    script_key=rec.script_key,
                    status="placed",
                )
            )
        db.flush()

        report = run_eod_quality_pass(db, user.id, slate_date=date.today())
        db.commit()

        assert report.locked_wins == 1
        assert report.locked_losses == 1
        assert report.locked_hit_rate == 0.5
        assert len(report.missed_winners) == 1
        assert report.missed_winners[0].selection == "Missed Board Winner"
        assert len(report.good_dodges) == 1
        assert len(report.false_skips) == 1
        assert report.uncalled_play_lean_hit_rate == 1.0
        assert report.packaging_gap == 0.5
        assert "Missed 1 PLAY/LEAN winner" in " ".join(report.lessons)
        assert report.to_dict()["slate_date"] == date.today().isoformat()

        events = list(
            db.scalars(
                select(LearningEvent).where(
                    LearningEvent.event_type.in_(
                        (
                            "EOD_QUALITY_PASS",
                            "EOD_MISSED_WINNER",
                            "EOD_FALSE_SKIP",
                            "EOD_GOOD_DODGE",
                        )
                    )
                )
            ).all()
        )
        types = {event.event_type for event in events}
        assert "EOD_QUALITY_PASS" in types
        assert "EOD_MISSED_WINNER" in types
        assert "EOD_FALSE_SKIP" in types
        assert "EOD_GOOD_DODGE" in types

        # Idempotent refresh of the day summary.
        again = run_eod_quality_pass(db, user.id, slate_date=date.today())
        db.commit()
        assert again.missed_winners[0].selection == "Missed Board Winner"
        pass_events = list(
            db.scalars(
                select(LearningEvent).where(LearningEvent.event_type == "EOD_QUALITY_PASS")
            ).all()
        )
        assert len(pass_events) == 1
        assert pass_events[0].analysis.get("refreshed") is True
    finally:
        db.close()
