"""Leg hit rate and ticket hit rate must stay separate metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.core.database import SessionLocal
from app.models import Result, Ticket, TicketLeg, User
from app.services.learning import performance
from test_settlement import _recommendation


def test_performance_splits_leg_hit_rate_from_ticket_hit_rate() -> None:
    with SessionLocal() as db:
        user = User(
            email="packaging@example.com",
            password_hash="x",
            name="Packaging",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()

        winners = [
            _recommendation(
                user.id,
                candidate_id=f"win-{index}",
                event_id=f"evt-win-{index}",
                thesis_key=f"thesis-win-{index}",
                script_key=f"script-win-{index}",
                selection=f"Winner {index}",
            )
            for index in range(3)
        ]
        loser = _recommendation(
            user.id,
            candidate_id="loss-1",
            event_id="evt-loss-1",
            thesis_key="thesis-loss-1",
            script_key="script-loss-1",
            selection="Loser",
        )
        db.add_all([*winners, loser])
        db.flush()

        for pick in winners:
            pick.outcome = "WIN"
            db.add(
                Result(
                    recommendation_id=pick.id,
                    outcome="WIN",
                    stake=Decimal("0.00"),
                    profit_loss=Decimal("0.00"),
                    process_grade="A",
                    variance_grade="LOW",
                    root_cause_tags=["BOARD_GRADED"],
                )
            )
        loser.outcome = "LOSS"
        db.add(
            Result(
                recommendation_id=loser.id,
                outcome="LOSS",
                stake=Decimal("0.00"),
                profit_loss=Decimal("0.00"),
                process_grade="B",
                variance_grade="MED",
                root_cause_tags=["BOARD_GRADED"],
            )
        )

        # One win + one loss on the ticket => ticket LOSS while legs are 75%.
        ticket = Ticket(
            user_id=user.id,
            ticket_type="core_parlay",
            label="Core Parlay",
            sport="mlb",
            slate_date=date.today(),
            status="settled",
            stake=Decimal("10.00"),
            potential_payout=Decimal("26.00"),
            combined_decimal_odds=Decimal("2.6000"),
            risk="medium",
            confidence_score=80,
            intentional_correlation=False,
            intentional_thesis_exposure=False,
            settled_outcome="LOSS",
            settled_payout=Decimal("0.00"),
            settled_profit_loss=Decimal("-10.00"),
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=winners[0].id,
                position=1,
                action="follow",
                selection=winners[0].selection,
                american_odds=-120,
                thesis_key=winners[0].thesis_key,
                script_key=winners[0].script_key,
                status="settled",
            )
        )
        db.add(
            TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=loser.id,
                position=2,
                action="follow",
                selection=loser.selection,
                american_odds=-120,
                thesis_key=loser.thesis_key,
                script_key=loser.script_key,
                status="settled",
            )
        )
        db.commit()

        report = performance(db, user.id)

    assert report.leg_settled == 4
    assert report.leg_wins == 3
    assert report.leg_losses == 1
    assert report.leg_win_rate == 0.75
    assert report.win_rate == 0.75

    assert report.ticket_settled == 1
    assert report.ticket_wins == 0
    assert report.ticket_losses == 1
    assert report.ticket_win_rate == 0.0
    assert report.packaging_gap == 0.75

    assert report.locked_leg_settled == 2
    assert report.locked_leg_wins == 1
    assert report.locked_leg_losses == 1
    assert report.locked_leg_win_rate == 0.5

    assert report.by_ticket_type
    assert report.by_ticket_type[0]["ticket_type"] == "core_parlay"
    assert report.packaging_note
    assert "leg" in report.packaging_note.lower()
