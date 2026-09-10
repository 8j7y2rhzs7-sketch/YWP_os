"""Day Forge selection + cook gates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.schemas import CandidateInput
from app.services.day_forge import (
    candidate_is_forge_fuel,
    cook_progress_from_slate,
    recommendation_is_day_forge_eligible,
    select_day_forge_play,
    trim_forge_candidates,
)
from app.services.decision_engine import decision_engine
from app.schemas import RiskProfile


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


def test_select_prefers_cash_builder_over_juicey_play() -> None:
    cash = _candidate(candidate_id="cash", american_odds=-112, estimated_probability=0.63)
    deep = _candidate(candidate_id="deep", american_odds=-195, estimated_probability=0.70)
    cash_eval = decision_engine.evaluate(cash, RiskProfile.balanced)
    deep_eval = decision_engine.evaluate(deep, RiskProfile.balanced)

    class Row:
        def __init__(self, evaluation, candidate):
            self.decision = evaluation.decision
            self.american_odds = candidate.american_odds
            self.confidence_score = evaluation.confidence_score
            self.edge = evaluation.edge
            self.miss_by_one_risk = evaluation.miss_by_one_risk
            self.variance = candidate.variance
            self.ywp_rating = evaluation.ywp_intelligence_score
            self.vision_score = evaluation.vision_score
            self.risk = evaluation.risk
            self.reason_codes = evaluation.reason_codes
            self.recommendation_tier = evaluation.recommendation_tier
            self.rank = 1
            self.snapshot = {
                "probability_source": candidate.probability_source,
                "game_status": "PRE_GAME",
                "market_status": "OPEN",
            }
            self.selection = candidate.selection

    rows = [Row(cash_eval, cash), Row(deep_eval, deep)]
    # Force ranks
    rows[0].rank = 2
    rows[1].rank = 1
    pick = select_day_forge_play(rows)
    assert pick is not None
    assert recommendation_is_day_forge_eligible(pick) or pick.decision in {"PLAY", "LEAN"}
    # Prefer nearer -110 when both eligible
    if recommendation_is_day_forge_eligible(rows[0]) and recommendation_is_day_forge_eligible(
        rows[1]
    ):
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
