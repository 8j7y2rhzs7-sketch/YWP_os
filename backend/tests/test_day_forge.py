"""Day Forge selection + cook gates."""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import CandidateInput
from app.services.day_forge import (
    candidate_is_forge_fuel,
    cook_progress_from_slate,
    day_forge_sport_queue,
    recommendation_is_day_forge_eligible,
    resolve_day_forge_sport,
    select_day_forge_play,
    trim_forge_candidates,
)


def _candidate(**changes) -> CandidateInput:
    data = {
        "candidate_id": "forge-1",
        "event_id": "event-1",
        "event_name": "Forge Event",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "market_type": "moneyline",
        "selection": "Metro ML",
        "line": None,
        "american_odds": -125,
        "estimated_probability": 0.64,
        "probability_source": "demo",
        "variance": 0.28,
        "data_quality": 0.92,
        "data_source": "TEST",
        "source_timestamp": datetime.now(UTC),
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "lineup": "confirmed",
            "injuries": "confirmed",
        },
        "schedule_verified": True,
        "universe_scan_complete": True,
        "current_form_verified": True,
        "l5_l10_verified": True,
        "lineup_confirmed": True,
        "injuries_verified": True,
        "weather_verified": True,
        "starter_confirmed": True,
        "motivation_rotation_verified": True,
        "home_away_verified": True,
        "market_movement_verified": True,
        "sport_specific_sweep_complete": True,
        "recent_hit_rate": 0.7,
        "average_cushion": 1.6,
        "matchup_score": 0.8,
        "script_alignment": 0.8,
        "multiple_paths_score": 0.8,
        "role_stability": 0.8,
        "ain_checks": {
            "recent_form_l5_l10": True,
            "situational_angles": True,
            "h2h_context": True,
        },
        "thesis_key": "metro-ml",
        "script_key": "script-ml",
    }
    data.update(changes)
    return CandidateInput(**data)


def test_rejects_heavy_juice_and_lottery_odds() -> None:
    juice = _candidate(american_odds=-1400, candidate_id="juice")
    lottery = _candidate(american_odds=+320, candidate_id="lotto")
    cash = _candidate(american_odds=-118, candidate_id="cash")
    assert candidate_is_forge_fuel(juice) is False
    assert candidate_is_forge_fuel(lottery) is False
    assert candidate_is_forge_fuel(cash) is True


def test_cook_progress_stays_cooking_until_fuel() -> None:
    thin = [_candidate(candidate_id="only-one", american_odds=-115)]
    cook = cook_progress_from_slate(thin)
    # demo_mode allows grading with 1 forgeable
    assert cook.forgeable_count >= 1
    assert cook.phase in {"grading", "gathering_heat"}


def test_empty_slate_stays_cooking_not_unavailable() -> None:
    cook = cook_progress_from_slate([])
    assert cook.status == "cooking"
    assert cook.phase == "waiting_slate"
    assert cook.progress >= 0.08
    assert "empty_slate" in cook.cook_reasons


def test_sport_queue_prefers_catalog_key_and_priority() -> None:
    catalog = [
        {"key": "mlb", "in_season": True},
        {"key": "nfl", "in_season": True},
        {"key": "wnba", "in_season": False},
    ]
    queue = day_forge_sport_queue(catalog)
    assert queue[0] == "nfl"
    assert "mlb" in queue
    assert "wnba" not in queue
    assert resolve_day_forge_sport(catalog) == "nfl"
    assert resolve_day_forge_sport(catalog, "mlb") == "mlb"
    assert day_forge_sport_queue(catalog, "mlb")[0] == "mlb"


def test_sport_queue_uses_key_not_missing_id_field() -> None:
    # Regression: catalog rows use `key`, not `id`/`sport`.
    catalog = [{"key": "nba", "in_season": True}]
    assert resolve_day_forge_sport(catalog) == "nba"
    assert day_forge_sport_queue(catalog) == ["nba"]


def test_select_prefers_cash_builder_over_juicey_play() -> None:
    class Row:
        def __init__(self, *, decision, odds, confidence, edge, miss, ywp, tier, rank, source="demo"):
            self.decision = decision
            self.american_odds = odds
            self.confidence_score = confidence
            self.edge = edge
            self.miss_by_one_risk = miss
            self.variance = 0.28
            self.ywp_rating = ywp
            self.vision_score = 0.8
            self.risk = "medium"
            self.reason_codes = []
            self.recommendation_tier = tier
            self.rank = rank
            self.snapshot = {
                "probability_source": source,
                "game_status": "PRE_GAME",
                "market_status": "OPEN",
            }
            self.selection = "Metro ML"

    cash = Row(
        decision="PLAY",
        odds=-112,
        confidence=90,
        edge=0.06,
        miss=0.2,
        ywp=7.2,
        tier="cash_builder",
        rank=2,
    )
    deep = Row(
        decision="PLAY",
        odds=-195,
        confidence=92,
        edge=0.07,
        miss=0.22,
        ywp=7.4,
        tier="aggressive",
        rank=1,
    )
    assert recommendation_is_day_forge_eligible(cash)
    assert recommendation_is_day_forge_eligible(deep)
    pick = select_day_forge_play([cash, deep])
    assert pick is not None
    assert pick.american_odds == -112


def test_trim_caps_forge_candidates() -> None:
    rows = [
        _candidate(candidate_id=f"c-{i}", american_odds=-110 - (i % 40), data_quality=0.7 + (i % 20) / 100)
        for i in range(60)
    ]
    trimmed = trim_forge_candidates(rows)
    assert len(trimmed) <= 48
    assert all(candidate_is_forge_fuel(c) for c in trimmed)


def test_day_forge_endpoint_demo(client, auth_headers) -> None:
    response = client.get("/api/v1/sports/day-forge?sport=mlb", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["engine"] == "YWP Day Forge"
    assert body["status"] in {"cooking", "ready", "pass", "unavailable"}
    assert 0.0 <= body["progress"] <= 1.0
    if body["status"] == "ready":
        assert body["play"] is not None
        odds = body["play"]["american_odds"]
        assert -200 <= odds <= 150
        assert odds > -300


def test_day_forge_endpoint_cascades_past_503(client, auth_headers, monkeypatch) -> None:
    """When the preferred sport's slate is offline, cascade to the next sport."""
    from fastapi import HTTPException, status

    from app.api import sports as sports_api
    from app.schemas import SlateResponse

    calls: list[str] = []

    def fake_slate(user, sport_name: str, slate_date):
        calls.append(sport_name)
        if sport_name == "mlb":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No verified live slate is available.",
            )
        return SlateResponse(
            sport=sport_name,
            date=slate_date,
            mode="demo",
            readiness="DEMO",
            notice="test",
            verification_summary={},
            candidates=[_candidate(sport=sport_name, candidate_id=f"{sport_name}-1")],
        )

    monkeypatch.setattr(sports_api, "slate", fake_slate)
    # MLB ranks above WNBA in the forge priority list — MLB 503 should fall through.
    monkeypatch.setattr(
        sports_api,
        "build_app_sports_catalog",
        lambda: [
            {"key": "mlb", "in_season": True},
            {"key": "wnba", "in_season": True},
        ],
    )

    response = client.get("/api/v1/sports/day-forge", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert calls[0] == "mlb"
    assert "wnba" in calls
    assert body["sport"] == "wnba"
    assert body["status"] in {"cooking", "ready", "pass"}
    assert body["status"] != "unavailable"
    assert body["progress"] > 0.05


def test_day_forge_all_slates_offline_stays_cooking(client, auth_headers, monkeypatch) -> None:
    from fastapi import HTTPException, status

    from app.api import sports as sports_api

    def fake_slate(user, sport_name: str, slate_date):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No verified live slate is available.",
        )

    monkeypatch.setattr(sports_api, "slate", fake_slate)
    monkeypatch.setattr(
        sports_api,
        "build_app_sports_catalog",
        lambda: [{"key": "mlb", "in_season": True}],
    )

    response = client.get("/api/v1/sports/day-forge", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cooking"
    assert body["phase"] == "waiting_slate"
    assert body["progress"] >= 0.08
    assert "slate_unavailable" in body["cook_reasons"]
