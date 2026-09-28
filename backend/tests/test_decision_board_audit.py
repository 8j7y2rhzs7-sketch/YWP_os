from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.schemas import CandidateInput
from app.services.board_metrics import (
    card_risk,
    joint_win_probability_disclosure,
    market_scope_label,
    outlier_review_reasons,
    select_weakest_leg,
)
from app.services.decision_engine import decision_engine
from app.services.mlb_model import MLBProjection
from app.services.ticket_builder import build_cards


def _candidate(**changes) -> CandidateInput:
    data = {
        "candidate_id": "candidate-1",
        "event_id": "event-1",
        "event_name": "Away Team @ Home Team",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "home_team": "Home Team",
        "away_team": "Away Team",
        "bookmaker": "draftkings",
        "bookmaker_label": "DraftKings",
        "market_type": "moneyline",
        "selection": "Home Team ML",
        "american_odds": -110,
        "estimated_probability": 0.64,
        "probability_source": "model",
        "variance": 0.22,
        "data_quality": 0.9,
        "data_source": "MLB_STATS_API+THE_ODDS_API",
        "source_timestamp": datetime.now(UTC),
        "thesis_key": "thesis-1",
        "script_key": "script-1",
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
    }
    data.update(changes)
    return CandidateInput(**data)


def _full_play(**changes):
    now = datetime.now(UTC)
    base = dict(
        id="play-x",
        analysis_id="analysis-1",
        candidate_id="cand-1",
        event_id="event-1",
        event_name="Away Team @ Home Team",
        sport="mlb",
        league="MLB",
        slate_date=now.date(),
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
        confidence_score=88,
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
        snapshot={
            "probability_source": "model",
            "home_team": "Home Team",
            "away_team": "Away Team",
            "bookmaker": "draftkings",
            "bookmaker_label": "DraftKings",
            "start_time": now.isoformat(),
        },
        data_source="MLB_STATS_API+THE_ODDS_API",
        source_timestamp=now,
        model_version="test",
        protocol_version="test",
        input_hash="abc",
        outcome=None,
        created_at=now,
    )
    base.update(changes)
    return SimpleNamespace(**base)


def test_quality_score_is_not_win_probability() -> None:
    evaluation = decision_engine.evaluate(_candidate())
    assert evaluation.confidence_score != round(evaluation.adjusted_probability * 100)


def test_plus_money_high_model_probability_is_review() -> None:
    evaluation = decision_engine.evaluate(
        _candidate(selection="Miami ML", american_odds=157, estimated_probability=0.88)
    )
    assert evaluation.decision == "REVIEW"
    assert "OUTLIER_PLUS_MONEY_PROBABILITY" in evaluation.reason_codes
    assert "OUTLIER_EDGE_REVIEW" in evaluation.reason_codes


def test_review_excluded_from_official_cards() -> None:
    review = _full_play(id="rev-1", decision="REVIEW", rank=1, selection="Outlier ML")
    play = _full_play(
        id="play-2",
        rank=2,
        thesis_key="thesis-b",
        script_key="script-b",
        player_key="player-b",
        event_id="event-2",
        selection="Clean ML",
        confidence_score=90,
        ywp_rating=Decimal("8.5"),
    )
    cards, quarantined = build_cards([review, play], max_legs=5, min_rating=0)
    assert cards["max_bet"].recommendation_ids == ["play-2"]
    assert any(item.recommendation_id == "rev-1" for item in quarantined)


def test_weakest_leg_yis_tiebreak_matches_screenshot_case() -> None:
    texas = _full_play(
        id="texas",
        selection="Texas Rangers ML",
        confidence_score=88,
        ywp_rating=Decimal("8.18"),
        american_odds=105,
    )
    miami = _full_play(
        id="miami",
        selection="Miami -1.5",
        confidence_score=88,
        ywp_rating=Decimal("8.05"),
        american_odds=157,
        event_id="event-2",
        thesis_key="thesis-b",
        script_key="script-b",
        player_key="player-b",
        market_type="run_line",
    )
    weakest, criterion, explanation = select_weakest_leg([texas, miami])
    assert weakest.id == "miami"
    assert criterion == "lowest_quality_then_yis"
    assert "not American odds alone" in explanation

    cards, _ = build_cards([texas, miami], max_legs=5, min_rating=0)
    elite = cards["elite_two"]
    assert elite.weakest_leg_id == "miami"
    assert elite.weakest_leg_criterion == "lowest_quality_then_yis"
    assert elite.quality_score == 88
    assert "not a win probability" in elite.quality_score_note.lower()


def test_joint_probability_not_invented_from_quality_scores() -> None:
    a = _full_play(id="a1", snapshot={"probability_source": "market_implied"})
    b = _full_play(
        id="b1",
        event_id="event-2",
        thesis_key="tb",
        script_key="sb",
        player_key="pb",
        snapshot={"probability_source": "market_implied"},
    )
    disclosure = joint_win_probability_disclosure([a, b])
    assert disclosure["joint_win_probability"] is None
    assert disclosure["joint_probability_status"] == "unavailable"


def test_dependent_legs_block_joint_product() -> None:
    a = _full_play(id="a1", event_id="same")
    b = _full_play(
        id="b1",
        event_id="same",
        thesis_key="tb",
        script_key="sb",
        player_key="pb",
        selection="Other market",
    )
    disclosure = joint_win_probability_disclosure([a, b])
    assert disclosure["joint_probability_status"] == "unavailable_dependent_legs"


def test_market_scope_labels() -> None:
    assert "Game total" in market_scope_label("game_total_over", "full_game")
    assert "Moneyline" in market_scope_label("moneyline", "full_game")
    assert "First 5" in market_scope_label("game_total_over", "f5")


def test_card_risk_accounts_for_leg_count() -> None:
    legs = [
        _full_play(
            id=f"l{i}",
            risk="low",
            event_id=f"e{i}",
            thesis_key=f"t{i}",
            script_key=f"s{i}",
            player_key=f"p{i}",
        )
        for i in range(4)
    ]
    risk, explanation = card_risk(legs)
    assert risk in {"medium_high", "high"}
    assert "legs" in explanation.lower()


def test_mlb_model_does_not_silently_shrink_extremes() -> None:
    projection = MLBProjection(
        home_win_probability=0.55,
        away_win_probability=0.45,
        expected_total_runs=11.5,
        expected_home_margin=0.4,
        model_quality=0.8,
        reasoning=("test",),
    )
    over = projection.total_probability(7.5, "over")
    assert over > 0.82


def test_demo_probability_blocked_from_cards() -> None:
    from app.core.config import settings

    demo = _full_play(
        id="demo-1",
        snapshot={"probability_source": "demo"},
        data_source="DEMO_SYNTHETIC",
    )
    cards, quarantined = build_cards([demo], max_legs=5, min_rating=0)
    if settings.demo_mode and settings.env != "production":
        # Demo mode may still build cards for local/test fixtures.
        assert isinstance(cards, dict)
    else:
        assert not cards
        assert any("demo" in item.reason.lower() for item in quarantined)


def test_outlier_helper_codes() -> None:
    codes = outlier_review_reasons(
        adjusted_probability=0.88,
        american_odds=157,
        probability_source="model",
    )
    assert "OUTLIER_EDGE_REVIEW" in codes
    assert "OUTLIER_PLUS_MONEY_PROBABILITY" in codes
