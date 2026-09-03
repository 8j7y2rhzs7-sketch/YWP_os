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
    assert evaluation.decision == "SKIP"
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
    assert any("15 percentage points" in item.reason for item in quarantined)


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


def _play(**changes):
    base = dict(
        id="play-x",
        analysis_id="analysis-1",
        candidate_id="cand-1",
        event_id="event-1",
        event_name="Demo Event",
        sport="mlb",
        league="MLB",
        slate_date=datetime.now(UTC).date(),
        market_type="moneyline",
        market_period="full_game",
        selection="Demo ML",
        line=None,
        american_odds=-110,
        estimated_probability=Decimal("0.60"),
        implied_probability=Decimal("0.52"),
        adjusted_probability=Decimal("0.58"),
        decision="PLAY",
        ywp_rating=Decimal("8.0"),
        miss_by_one_risk=Decimal("0.2"),
        edge=Decimal("0.05"),
        confidence_score=70,
        vision_score=Decimal("7.0"),
        variance=Decimal("0.25"),
        expected_value=Decimal("0.08"),
        reliability=Decimal("0.80"),
        stability=Decimal("0.75"),
        data_quality=Decimal("0.90"),
        risk="low",
        risk_tier="Moderate",
        variance_rating="Medium",
        edge_class="Solid",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.01"),
        recommendation_tier="official",
        rank=1,
        reason_codes=[],
        reasoning_summary="Unit test pick",
        warnings=[],
        safer_alternative=None,
        higher_upside=None,
        invalidation_conditions=[],
        live_trigger=None,
        hedge=None,
        quick_cash=False,
        chain_reaction_key=None,
        thesis_key="thesis-a",
        script_key="script-a",
        player_key=None,
        snapshot={},
        data_source="unit-test",
        source_timestamp=datetime.now(UTC),
        model_version="test",
        protocol_version="test",
        input_hash="abc",
        outcome=None,
        created_at=datetime.now(UTC),
    )
    base.update(changes)
    return SimpleNamespace(**base)


def test_analysis_rank_one_lands_on_max_bet() -> None:
    """Higher board rank must beat a lower-ranked pick with a bigger raw score."""
    top = _play(
        id="rank-1",
        rank=1,
        thesis_key="thesis-top",
        event_id="event-top",
        selection="Board #1 ML",
        confidence_score=72,
        ywp_rating=Decimal("8.1"),
        edge=Decimal("0.04"),
        script_key="script-top",
        player_key="player-top",
    )
    louder = _play(
        id="rank-4",
        rank=4,
        thesis_key="thesis-loud",
        event_id="event-loud",
        selection="Louder score ML",
        confidence_score=90,
        ywp_rating=Decimal("9.0"),
        edge=Decimal("0.09"),
        script_key="script-loud",
        player_key="player-loud",
    )
    cards, quarantined = build_cards([top, louder], max_legs=5, min_rating=0)
    assert cards["max_bet"].recommendation_ids == ["rank-1"]
    assert "elite_two" in cards
    assert cards["elite_two"].recommendation_ids[0] == "rank-1"
    held = {
        item.recommendation_id
        for item in quarantined
        if "needs" not in item.reason
    }
    assert "rank-1" not in held


def test_ineligible_top_rank_is_explained() -> None:
    watch = _play(
        id="watch-1",
        rank=1,
        decision="WATCH",
        thesis_key="watch-thesis",
        event_id="event-watch",
        selection="Watch board #1",
        ywp_rating=Decimal("6.0"),
    )
    play = _play(
        id="play-2",
        rank=2,
        thesis_key="play-thesis",
        event_id="event-play",
        selection="Play board #2",
        player_key="player-play",
        script_key="script-play",
    )
    cards, quarantined = build_cards([watch, play], max_legs=5, min_rating=0)
    assert cards["max_bet"].recommendation_ids == ["play-2"]
    assert any(
        item.recommendation_id == "watch-1" and "not ticket-eligible" in item.reason
        for item in quarantined
    )


def test_underfilled_multi_leg_cards_are_dropped() -> None:
    only = _play(
        id="solo-1",
        rank=2,
        thesis_key="solo-thesis",
        event_id="event-solo",
        selection="Solo play ML",
        player_key="player-solo",
        script_key="script-solo",
    )
    cards, quarantined = build_cards([only], max_legs=5, min_rating=0)
    assert "max_bet" in cards
    assert cards["max_bet"].recommendation_ids == ["solo-1"]
    assert "elite_two" not in cards
    assert "core_3" not in cards
    assert any(
        "needs 2 legs" in item.reason or "needs 3 legs" in item.reason
        for item in quarantined
    )
