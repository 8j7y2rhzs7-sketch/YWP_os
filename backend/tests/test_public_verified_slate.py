"""Public schedule fallback when The Odds API is down."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.services import public_verified_slate as pvs


def test_fair_american_odds_favorites_and_dogs() -> None:
    assert pvs.fair_american_odds(0.75) < -100
    assert pvs.fair_american_odds(0.25) > 100
    assert pvs.fair_american_odds(0.5) in {-100, 100}


def test_odds_api_unavailable_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.odds_provider.odds_api_configured",
        lambda: False,
    )
    assert pvs.odds_api_unavailable() is True


def test_odds_api_unavailable_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.odds_provider.odds_api_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.odds_provider.get_last_fetch_status",
        lambda: {"status_code": 401, "error": "Unauthorized"},
    )
    assert pvs.odds_api_unavailable() is True


def test_public_verified_slate_builds_moneylines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tip = datetime.now(UTC) + timedelta(hours=3)
    monkeypatch.setattr(
        pvs,
        "get_scoreboard",
        lambda sport, slate_date, **_kwargs: [
            {
                "event_id": "espn-1",
                "home_team": "Boston Celtics",
                "away_team": "New York Knicks",
                "start_time": tip,
                "status": "pre",
            }
        ],
    )
    monkeypatch.setattr(
        pvs,
        "build_event_research",
        lambda **_kwargs: {
            "flags": {
                "schedule_verified": False,
                "current_form_verified": True,
                "injuries_verified": False,
                "lineup_confirmed": False,
                "starter_confirmed": False,
                "motivation_rotation_verified": False,
                "market_movement_verified": False,
                "sport_specific_sweep_complete": False,
            },
            "source_status": {"schedule": "unknown", "market": "unknown"},
            "home_form": {"l10_wins": 6, "l10_losses": 4},
            "away_form": {"l10_wins": 4, "l10_losses": 6},
            "projections": {
                "moneyline": {
                    "home": 0.58,
                    "away": 0.42,
                }
            },
        },
    )

    rows = pvs.public_verified_slate("nba", tip.date())
    assert len(rows) == 2
    assert {c.selection for c in rows} == {
        "Boston Celtics ML",
        "New York Knicks ML",
    }
    assert all(c.data_source == "PUBLIC_SCHEDULE_FALLBACK" for c in rows)
    assert all(c.market_status == "OPEN" for c in rows)
    assert all("PUBLIC_SCHEDULE_FALLBACK" in (c.reason_codes or []) for c in rows)
    assert "PUBLIC FALLBACK" in pvs.public_fallback_notice("nba", len(rows))


def test_public_verified_slate_skips_finals(monkeypatch: pytest.MonkeyPatch) -> None:
    tip = datetime.now(UTC) + timedelta(hours=2)
    monkeypatch.setattr(
        pvs,
        "get_scoreboard",
        lambda sport, slate_date, **_kwargs: [
            {
                "event_id": "done",
                "home_team": "A",
                "away_team": "B",
                "start_time": tip,
                "status": "STATUS_FINAL",
            }
        ],
    )
    assert pvs.public_verified_slate("nba", tip.date()) == []


def test_slate_endpoint_uses_public_fallback_when_odds_down(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.schemas import CandidateInput

    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "odds_api_key", "")

    tip = datetime.now(UTC) + timedelta(hours=4)
    seed = CandidateInput(
        candidate_id="pub-nba-ml-home-espn",
        event_id="espn-1",
        event_name="Away @ Home",
        sport="nba",
        league="NBA",
        market_type="moneyline",
        market_period="full_game",
        selection="Home ML",
        american_odds=-138,
        estimated_probability=0.58,
        start_time=tip,
        home_team="Home",
        away_team="Away",
        data_source="PUBLIC_SCHEDULE_FALLBACK",
        source_timestamp=datetime.now(UTC),
        probability_source="model",
        thesis_key="pub-thesis",
        script_key="pub-script",
        reason_codes=["PUBLIC_SCHEDULE_FALLBACK", "NO_SPORTSBOOK_PRICE"],
        reasoning=["fallback"],
        variance=0.2,
        data_quality=0.55,
        game_status="PRE_GAME",
        market_status="OPEN",
    )
    monkeypatch.setattr(
        "app.api.sports.public_verified_slate",
        lambda sport, slate_date: [seed],
    )
    monkeypatch.setattr("app.api.sports.odds_api_unavailable", lambda: True)
    monkeypatch.setattr("app.api.sports.odds_api_configured", lambda: False)
    monkeypatch.setattr(
        "app.api.sports.app_sport_in_season",
        lambda _sport: True,
    )

    response = client.get(
        "/api/v1/sports/slate",
        params={"sport": "nba", "date": tip.date().isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidates"]
    assert body["candidates"][0]["data_source"] == "PUBLIC_SCHEDULE_FALLBACK"
    assert "PUBLIC FALLBACK" in (body.get("notice") or "")
