from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.schemas import CandidateInput
from app.services.decision_engine import decision_engine
from app.services.ticket_builder import build_cards
from app.services.ticket_gates import cap_pitcher_k_overs, cash_card_k_overs_ok


def candidate(**changes) -> CandidateInput:
    data = {
        "candidate_id": "candidate-1",
        "event_id": "event-1",
        "event_name": "Demo Event",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "market_type": "moneyline",
        "selection": "Demo Metro ML",
        "american_odds": -110,
        "estimated_probability": 0.64,
        "variance": 0.22,
        "data_quality": 0.95,
        "data_source": "TEST",
        "source_timestamp": datetime.now(UTC),
        "source_status": {"market": "confirmed", "lineup": "confirmed"},
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
        "average_cushion": 1.5,
        "matchup_score": 0.8,
        "script_alignment": 0.8,
        "multiple_paths_score": 0.8,
        "role_stability": 0.8,
        "ain_checks": {
            "recent_form_l5_l10": True,
            "situational_angles": True,
            "h2h_context": True,
        },
        "thesis_key": "demo-ml",
        "script_key": "demo-script",
        "game_status": "PRE_GAME",
        "market_status": "OPEN",
    }
    data.update(changes)
    return CandidateInput(**data)


def test_live_game_is_rejected() -> None:
    evaluation = decision_engine.evaluate(candidate(game_status="LIVE"))
    assert evaluation.decision == "SKIP"
    assert "GAME_NOT_PRE_GAME" in evaluation.reason_codes


def test_closed_market_is_rejected() -> None:
    evaluation = decision_engine.evaluate(candidate(market_status="SUSPENDED"))
    assert evaluation.decision == "SKIP"
    assert "MARKET_NOT_OPEN" in evaluation.reason_codes


def test_three_identical_probabilities_are_data_anomaly() -> None:
    evaluations = [
        decision_engine.evaluate(
            candidate(
                candidate_id=f"clone-{index}",
                event_id=f"event-{index}",
                thesis_key=f"thesis-{index}",
                script_key=f"script-{index}",
                estimated_probability=0.60,
                american_odds=-110,
            )
        )
        for index in range(3)
    ]
    ranked = decision_engine.rank(evaluations)
    assert all(item.decision == "SKIP" for item in ranked)
    assert all("DATA_ANOMALY" in item.reason_codes for item in ranked)


def test_model_edge_over_15_points_is_quarantined() -> None:
    evaluation = decision_engine.evaluate(
        candidate(estimated_probability=0.90, american_odds=-110)
    )
    assert "MODEL_EDGE_QUARANTINE" in evaluation.reason_codes
    rec = SimpleNamespace(
        id="rec-1",
        decision="PLAY",
        ywp_rating=Decimal("8.5"),
        thesis_key="edge-thesis",
        miss_by_one_risk=Decimal("0.2"),
        edge=Decimal(str(evaluation.edge)),
        confidence_score=evaluation.confidence_score,
        vision_score=Decimal(str(evaluation.vision_score)),
        variance=Decimal("0.2"),
        expected_value=Decimal("0.2"),
        snapshot={},
        player_key=None,
        event_id="event-1",
        selection="Huge edge ML",
        market_type="moneyline",
        quick_cash=False,
        chain_reaction_key=None,
        risk="low",
    )
    cards, quarantined = build_cards([rec], max_legs=5, min_rating=0)
    assert cards == {}
    assert any("15 percentage points" in item["reason"] for item in quarantined)


def test_cash_card_rejects_second_pitcher_k_over() -> None:
    first = SimpleNamespace(
        id="k-1",
        market_type="player_strikeouts_over",
        snapshot={"market_is_pitcher_strikeout_over": True},
    )
    second = SimpleNamespace(
        id="k-2",
        market_type="player_strikeouts_over",
        snapshot={"market_is_pitcher_strikeout_over": True},
    )
    ml = SimpleNamespace(
        id="ml-1",
        market_type="moneyline",
        snapshot={},
    )
    kept, rejected = cap_pitcher_k_overs([first, second, ml], max_k=1)
    assert rejected is True
    assert [item.id for item in kept] == ["k-1", "ml-1"]
    assert cash_card_k_overs_ok("cash_builder", [first, second]) is False
    assert cash_card_k_overs_ok("cash_builder", [first, ml]) is True
    assert cash_card_k_overs_ok("elite_two", [first, second]) is True


def test_official_pass_returns_no_tickets() -> None:
    skip = SimpleNamespace(
        id="skip-1",
        decision="SKIP",
        ywp_rating=Decimal("4.0"),
        thesis_key="skip-thesis",
        miss_by_one_risk=Decimal("0.2"),
        edge=Decimal("0.01"),
        confidence_score=40,
        vision_score=Decimal("4.0"),
        variance=Decimal("0.4"),
        expected_value=Decimal("-0.02"),
        snapshot={},
        player_key=None,
        event_id="event-1",
        selection="Stay away",
        market_type="moneyline",
        quick_cash=False,
        chain_reaction_key=None,
        risk="high",
    )
    cards, _quarantined = build_cards([skip], max_legs=5, min_rating=7.5)
    assert cards == {}
