"""Audit regression expectations, 2026-09-04.

These assertions intentionally expose the documented expectations in 3.3.3 and 3.3.4. They run only
against the isolated database configured by tests/conftest.py. No live account,
provider request, or production database is used.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import ModelWeight, Ticket, TicketLeg, User
from app.services import settlement
from app.services.learning import performance
from app.services.sport_model import project_matchup
from test_settlement import _feed, _recommendation


def test_easier_spread_cannot_lower_cover_probability():
    form = {
        "verified": True,
        "l5": {"win_pct": 0.5},
        "l10": {"win_pct": 0.5, "avg_for": 80, "avg_against": 80},
    }

    def probability(line):
        return project_matchup(
            home_form=form,
            away_form=form,
            market_type="spread",
            selection="Home Club",
            is_home_selection=True,
            line=line,
        ).win_probability

    harder, neutral, easier = [probability(line) for line in (-5.5, 0, 5.5)]
    print(f"Cover probabilities: -5.5={harder:.6f}; 0={neutral:.6f}; +5.5={easier:.6f}")
    assert harder <= neutral <= easier, "Giving a team points must not lower cover probability"


def test_analyze_rejects_candidates_from_a_different_slate_date(client, auth_headers):
    loaded_date = date(2026, 9, 3)
    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": loaded_date.isoformat()},
        headers=auth_headers,
    )
    assert slate.status_code == 200
    response = client.post(
        "/api/v1/sports/analyze",
        json={
            "sport": "mlb",
            "date": (loaded_date + timedelta(days=7)).isoformat(),
            "mode": "pregame",
            "candidates": slate.json()["candidates"],
        },
        headers=auth_headers,
    )
    print(f"Loaded Sept 3; submitted Sept 10 with unchanged candidates: HTTP {response.status_code}")
    assert response.status_code in {409, 422}, "Reject a date that does not match loaded events"


def test_settled_two_leg_ticket_preserves_wager_profit(monkeypatch):
    monkeypatch.setattr(settlement, "get_live_feed", lambda game_pk: _feed())
    with SessionLocal() as db:
        user = User(
            email="audit-parlay@example.com",
            password_hash="unused",
            name="Audit",
            timezone="America/New_York",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        picks = [
            _recommendation(
                user.id,
                candidate_id=f"audit-home-{n}",
                event_id=f"audit-event-{n}",
                american_odds=100,
                snapshot={"game_pk": 55555 + n, "home_team": "Home Club", "away_team": "Away Club"},
            )
            for n in (1, 2)
        ]
        db.add_all(picks)
        db.flush()
        ticket = Ticket(
            user_id=user.id,
            ticket_type="custom",
            label="Audit two-leg +100/+100",
            sport="mlb",
            slate_date=date.today(),
            status="placed",
            stake=Decimal("10.00"),
            potential_payout=Decimal("40.00"),
            confidence_score=72,
            risk="medium",
            intentional_correlation=False,
            intentional_thesis_exposure=False,
        )
        db.add(ticket)
        db.flush()
        for position, pick in enumerate(picks, 1):
            db.add(TicketLeg(
                ticket_id=ticket.id,
                recommendation_id=pick.id,
                position=position,
                action="follow",
                selection=pick.selection,
                american_odds=100,
                thesis_key=pick.thesis_key,
                script_key=pick.script_key,
                status="placed",
            ))
        db.commit()
        settlement.settle_user_placed_tickets(db, user.id)
        db.refresh(ticket)
        assert ticket.status == "settled"
        assert all(pick.outcome == "WIN" for pick in picks)
        report = performance(db, user.id)
        print(f"$10 two-leg winner / $40 return: P&L={report.profit_loss}; ROI={report.roi}")
        assert report.profit_loss == Decimal("30.00"), "Ticket-level P&L must include the settled parlay"


def test_required_learning_approval_does_not_activate_external_log_weights(client, auth_headers, monkeypatch):
    # Split policy (YWP-10): micro-updates are gated by learning_allow_micro_updates;
    # learning_requires_human_approval remains for large structural proposals.
    monkeypatch.setattr(settings, "learning_allow_micro_updates", False)
    monkeypatch.setattr(settings, "learning_requires_human_approval", True)
    response = client.post(
        "/api/v1/sports/log-external",
        headers=auth_headers,
        json={
            "sport": "mlb",
            "league": "MLB",
            "slate_date": "2026-09-03",
            "event_name": "Audit Away @ Audit Home",
            "market_type": "player_strikeouts_over",
            "selection": "Audit Pitcher Over 4.5 Strikeouts",
            "line": "4.5",
            "american_odds": -140,
            "outcome": "WIN",
            "actual_value": "7",
            "stake": "0.00",
            "profit_loss": "0.00",
            "process_grade": "C",
            "variance_grade": "MEDIUM",
        },
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        weights = list(db.scalars(select(ModelWeight).where(ModelWeight.is_active.is_(True))))
        print("Active weights after one external result with micro disabled:", [
            {"sport": w.sport, "feature": w.feature_name, "weight": str(w.weight), "samples": w.sample_size}
            for w in weights
        ])
        assert weights == [], "Logging a result must honor the configured micro-learning gate"
