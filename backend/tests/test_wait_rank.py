"""WAIT grades must sort and survive analyze — they used to crash rank()."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.schemas import CandidateInput, SlateResponse
from app.services.decision_engine import decision_engine
from app.services.marketing_feed import _leg_status
from app.services.pipeline.threshold import map_decision_threshold
from app.services.readiness import candidate_readiness
from app.services.ticket_builder import build_cards


def _candidate(**changes) -> CandidateInput:
    data = {
        "candidate_id": "rank-base",
        "event_id": "event-rank-base",
        "event_name": "Away @ Home",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "market_type": "moneyline",
        "selection": "Home ML",
        "american_odds": -110,
        "estimated_probability": 0.58,
        "probability_source": "model",
        "variance": 0.22,
        "data_quality": 0.9,
        "data_source": "TEST",
        "source_timestamp": datetime.now(UTC),
        "source_status": {"market": "confirmed", "schedule": "confirmed"},
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
        "thesis_key": "thesis-rank-base",
        "script_key": "script-rank-base",
        "game_status": "PRE_GAME",
        "market_status": "OPEN",
    }
    data.update(changes)
    return CandidateInput(**data)


def test_rank_orders_wait_and_unknown_without_crashing() -> None:
    """Reproduce the production KeyError: rank() indexed decisions with no WAIT key."""
    specs = [
        ("SKIP", 60, 0.01),
        ("PLAY", 92, 0.06),
        ("WAIT", 72, 0.05),
        ("NOT_A_REAL_GRADE", 99, 0.20),
        ("REVIEW", 80, 0.04),
        ("LEAN", 82, 0.04),
        ("WATCH", 74, 0.03),
    ]
    evaluations = []
    for index, (decision, confidence, edge) in enumerate(specs):
        evaluated = decision_engine.evaluate(
            _candidate(
                candidate_id=f"rank-{index}",
                event_id=f"event-rank-{index}",
                thesis_key=f"thesis-rank-{index}",
                script_key=f"script-rank-{index}",
                # Unique probabilities so the slate-integrity gate does not rewrite them.
                estimated_probability=0.52 + index * 0.02,
            )
        )
        evaluations.append(
            replace(evaluated, decision=decision, confidence_score=confidence, edge=edge)
        )

    ranked = decision_engine.rank(evaluations)
    assert [item.decision for item in ranked] == [
        "PLAY",
        "LEAN",
        "WATCH",
        "REVIEW",
        "WAIT",
        "SKIP",
        "NOT_A_REAL_GRADE",
    ]


def _partial_mlb_moneyline(**changes) -> CandidateInput:
    """Game-level MLB moneyline with an unknown bullpen — the live PARTIAL gap."""
    zone = ZoneInfo("America/New_York")
    start = datetime.now(zone).replace(hour=19, minute=5, second=0, microsecond=0)
    data = {
        "candidate_id": "mlb-partial-ml",
        "event_id": "mlb-event-partial",
        "event_name": "Away @ Home",
        "sport": "mlb",
        "league": "MLB",
        "start_time": start,
        "home_team": "Home",
        "away_team": "Away",
        "market_type": "moneyline",
        "selection": "Home ML",
        "american_odds": -110,
        "estimated_probability": 0.62,
        "probability_source": "model",
        "variance": 0.22,
        "data_quality": 0.92,
        "data_source": "MLB_STATS",
        "source_timestamp": datetime.now(UTC),
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "confirmed",
            "bullpen": "unknown",
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
        "recent_hit_rate": 0.62,
        "average_cushion": 1.2,
        "matchup_score": 0.7,
        "script_alignment": 0.7,
        "multiple_paths_score": 0.7,
        "role_stability": 0.8,
        "thesis_key": "home-ml-partial",
        "script_key": "home-script-partial",
        "game_status": "PRE_GAME",
        "market_status": "OPEN",
    }
    data.update(changes)
    return CandidateInput(**data)


def test_partial_mlb_unknown_bullpen_grades_wait() -> None:
    candidate = _partial_mlb_moneyline()
    assert candidate_readiness(candidate) == "PARTIAL"
    evaluation = decision_engine.evaluate(candidate)
    assert evaluation.edge > 0
    assert evaluation.decision == "WAIT"
    assert "WAIT_RESEARCH_INCOMPLETE" in evaluation.reason_codes
    assert "NO_PICK_YET" in evaluation.reason_codes
    assert evaluation.suggested_stake_pct == 0.0
    assert (
        map_decision_threshold(
            decision=evaluation.decision,
            confidence_score=evaluation.confidence_score,
            edge=evaluation.edge,
            miss_by_one_risk=evaluation.miss_by_one_risk,
            reason_codes=evaluation.reason_codes,
        )["threshold"]
        == "reject"
    )


def test_hive_calibration_does_not_promote_wait() -> None:
    evaluation = decision_engine.evaluate(
        _candidate(
            schedule_verified=True,
            universe_scan_complete=True,
            current_form_verified=True,
            l5_l10_verified=True,
            injuries_verified=True,
            weather_verified=True,
            starter_confirmed=True,
            motivation_rotation_verified=True,
            home_away_verified=True,
            market_movement_verified=True,
            sport_specific_sweep_complete=True,
            estimated_probability=0.64,
        )
    )
    evaluation.decision = "WAIT"
    evaluation.reason_codes = ["WAIT_RESEARCH_INCOMPLETE", "NO_PICK_YET"]
    after = decision_engine.apply_hive_calibration(evaluation, 0.70, shift_applied=0.02)
    assert after.decision == "WAIT"
    assert after.suggested_stake_pct == 0.0
    assert after.recommendation_tier == "wait"


def test_wait_cannot_enter_a_ticket() -> None:
    item = SimpleNamespace(
        id="wait-leg",
        decision="WAIT",
        rank=1,
        selection="Home ML",
    )
    cards, quarantined = build_cards([item], max_legs=5, min_rating=0)
    assert cards == {}
    assert quarantined
    assert "WAIT" in quarantined[0].reason
    assert "not ticket-eligible" in quarantined[0].reason


def test_wait_is_blocked_from_marketing() -> None:
    rec = SimpleNamespace(
        decision="WAIT",
        data_source="MLB_STATS",
        snapshot={"probability_source": "model"},
        reason_codes=["NO_PICK_YET"],
        source_timestamp=datetime.now(UTC),
    )
    assert _leg_status(rec) == "WAIT"


def test_health_reports_api_version(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["version"] == "3.3.68"


def test_analyze_partial_mlb_wait_is_returned_in_stay_away(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    candidate = _partial_mlb_moneyline()
    response = client.post(
        "/api/v1/sports/analyze",
        json={
            "sport": "mlb",
            "date": candidate.start_time.astimezone(ZoneInfo("America/New_York"))
            .date()
            .isoformat(),
            "mode": "pregame",
            "user_risk_profile": "balanced",
            "overlay_model_on_sheet": False,
            "candidates": [candidate.model_dump(mode="json")],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["readiness"] == "PARTIAL"
    assert all(item["decision"] != "WAIT" for item in body["ranked_picks"])
    wait_rows = [item for item in body["stay_away"] if item["decision"] == "WAIT"]
    assert len(wait_rows) == 1
    assert wait_rows[0]["candidate_id"] == candidate.candidate_id
    assert "WAIT_RESEARCH_INCOMPLETE" in wait_rows[0]["reason_codes"]
    assert float(wait_rows[0]["suggested_stake_pct"]) == 0.0
    assert body["data_quality_summary"]["official_skip_count"] >= 1


def test_analyze_grading_failure_returns_json_error(
    client: TestClient, auth_headers: dict[str, str], monkeypatch, caplog
) -> None:
    from app.api import sports as sports_api

    def _boom(_evaluations):
        raise RuntimeError("rank exploded")

    monkeypatch.setattr(sports_api.decision_engine, "rank", _boom)
    candidate = _partial_mlb_moneyline(candidate_id="mlb-boom")
    with caplog.at_level(logging.ERROR):
        response = client.post(
            "/api/v1/sports/analyze",
            json={
                "sport": "mlb",
                "date": candidate.start_time.astimezone(ZoneInfo("America/New_York"))
                .date()
                .isoformat(),
                "mode": "pregame",
                "user_risk_profile": "balanced",
                "overlay_model_on_sheet": False,
                "candidates": [candidate.model_dump(mode="json")],
            },
            headers=auth_headers,
        )
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    detail = response.json()["detail"]
    assert detail["error"] == "analyze_failed"
    assert detail["error_id"]
    assert len(detail["error_id"]) <= 12
    assert "Internal Server Error" not in response.text
    assert any(rec.exc_info and "rank exploded" in str(rec.exc_info[1]) for rec in caplog.records)


def test_day_forge_partial_mlb_wait_does_not_crash_or_seal(
    client: TestClient, auth_headers: dict[str, str], monkeypatch, db_session
) -> None:
    from sqlalchemy import select

    from app.api import sports as sports_api
    from app.models import Recommendation

    candidate = _partial_mlb_moneyline()

    def fake_slate(_user, sport_name: str, slate_date):
        return SlateResponse(
            sport=sport_name,
            date=slate_date,
            mode="live",
            readiness="PARTIAL",
            notice="test partial bullpen",
            verification_summary={"readiness": "PARTIAL"},
            candidates=[candidate],
        )

    monkeypatch.setattr(sports_api, "slate", fake_slate)
    monkeypatch.setattr(
        sports_api,
        "build_app_sports_catalog",
        lambda: [{"key": "mlb", "in_season": True}],
    )
    response = client.get(
        "/api/v1/sports/day-forge",
        params={"sport": "mlb", "force": "true"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pass"
    assert body["play"] is None
    assert body["graded_count"] >= 1
    assert body["pass_reason"] == "no_eligible_play"
    saved = list(db_session.scalars(select(Recommendation)).all())
    assert any(row.decision == "WAIT" for row in saved)
    assert all(row.decision in {"PLAY", "LEAN"} or row.suggested_stake_pct == 0 for row in saved)
