from datetime import date

from app.schemas import RiskProfile
from app.services.decision_engine import DecisionEngine
from app.services.espn_schedule import espn_unpriced_schedule


def test_espn_schedule_lists_games_without_a_price(monkeypatch):
    monkeypatch.setattr(
        "app.services.espn_schedule.get_scoreboard",
        lambda sport, slate_date: [
            {
                "event_id": "401810001",
                "home_team": "Orlando Magic",
                "away_team": "Miami Heat",
                "start_time": "2026-10-16T23:00:00Z",
                "status": "STATUS_IN_PROGRESS",
                "completed": False,
                "source_url": "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
            },
            {
                "event_id": "401810002",
                "home_team": "Los Angeles Lakers",
                "away_team": "Denver Nuggets",
                "start_time": "2026-10-17T02:30:00Z",
                "status": "STATUS_SCHEDULED",
                "completed": False,
                "source_url": "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
            },
        ],
    )

    rows = espn_unpriced_schedule("nba", date(2026, 10, 16))

    assert [row.event_name for row in rows] == [
        "Miami Heat @ Orlando Magic",
        "Denver Nuggets @ Los Angeles Lakers",
    ]
    assert rows[0].game_status == "LIVE"
    assert rows[1].game_status == "PRE_GAME"
    assert all(row.american_odds == 0 for row in rows)
    assert all(row.market_type == "schedule" for row in rows)
    assert all(row.market_status == "SUSPENDED" for row in rows)
    assert all("NO_SPORTSBOOK_PRICE" in row.reason_codes for row in rows)

    decision = DecisionEngine().evaluate(rows[1], risk_profile=RiskProfile.balanced).decision
    assert decision == "SKIP"
