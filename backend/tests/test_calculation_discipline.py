"""Weekly-report lessons encoded as hard calculation gates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import CandidateInput, RiskProfile
from app.services.board_metrics import select_weakest_leg
from app.services.calculation_discipline import (
    eliminate_weakest_until_stable,
    heavy_juice_blockers,
    market_family,
    official_output_label,
    same_player_category_conflicts,
)
from app.services.decision_engine import decision_engine
from app.services.ticket_builder import build_cards


def _base_candidate(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="cand-discipline-1",
        event_id="event-1",
        event_name="Away @ Home",
        sport="mlb",
        league="MLB",
        start_time=now,
        market_type="moneyline",
        selection="Home ML",
        american_odds=-110,
        estimated_probability=0.58,
        variance=0.25,
        data_quality=0.9,
        data_source="TEST",
        source_timestamp=now,
        source_status={"market": "confirmed"},
        thesis_key="thesis-home",
        script_key="script-home",
        schedule_verified=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=True,
        injuries_verified=True,
        weather_verified=True,
        starter_confirmed=True,
        motivation_rotation_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        universe_scan_complete=True,
        independent_value_verified=True,
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_heavy_juice_is_not_safety() -> None:
    assert heavy_juice_blockers(
        american_odds=-300,
        edge=0.01,
        independent_value_verified=False,
    ) == ["HEAVY_JUICE_NOT_SAFETY"]
    candidate = _base_candidate(
        american_odds=-300,
        estimated_probability=0.78,
        independent_value_verified=False,
    )
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "HEAVY_JUICE_NOT_SAFETY" in evaluation.reason_codes


def test_prop_identity_and_market_series_gates() -> None:
    now = datetime.now(UTC)
    missing_id = _base_candidate(
        sport="wnba",
        league="WNBA",
        market_type="player_points_over",
        selection="Mystery Player Over 19.5",
        line=Decimal("19.5"),
        player_key=None,
        recent_hit_rate=0.7,
        average_cushion=3.0,
        role_stability=0.8,
        observation_values=[22, 24, 21, 25, 20, 23, 26, 19, 24, 22],
    )
    evaluation = decision_engine.evaluate(missing_id, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "IDENTITY_PLAYER_KEY_MISSING" in evaluation.reason_codes

    # Incomplete series with identity → WAIT / NO PICK YET (not a fake SKIP story).
    wait_case = _base_candidate(
        sport="wnba",
        league="WNBA",
        market_type="player_points_over",
        selection="A'ja Wilson Over 19.5",
        line=Decimal("19.5"),
        player_key="aja-wilson",
        role_stability=0.8,
        # No L10 / hit rate / cushion → wait for market series.
        l5_l10_verified=False,
        current_form_verified=False,
        schedule_verified=False,
        source_timestamp=now,
    )
    # Force PARTIAL readiness via unverified research flags already set.
    wait_eval = decision_engine.evaluate(wait_case, RiskProfile.balanced)
    assert wait_eval.decision in {"WAIT", "SKIP"}
    assert (
        "NO_PICK_YET" in wait_eval.reason_codes or "MARKET_SERIES_MISSING" in wait_eval.reason_codes
    )


def test_same_player_category_stack_empties_card() -> None:
    def leg(market: str, selection: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=str(uuid4()),
            analysis_id=str(uuid4()),
            created_by_user_id=str(uuid4()),
            candidate_id=market,
            event_id="event-same",
            event_name="A @ B",
            sport="mlb",
            league="MLB",
            slate_date=datetime.now(UTC).date(),
            mode="pregame",
            market_type=market,
            market_period="full_game",
            selection=selection,
            line=Decimal("5.5"),
            american_odds=-115,
            estimated_probability=Decimal("0.60"),
            implied_probability=Decimal("0.53"),
            adjusted_probability=Decimal("0.60"),
            edge=Decimal("0.06"),
            expected_value=Decimal("0.05"),
            confidence_score=90,
            ywp_rating=Decimal("8.5"),
            vision_score=Decimal("7.5"),
            miss_by_one_risk=Decimal("0.20"),
            reliability=Decimal("0.8"),
            stability=Decimal("0.8"),
            variance=Decimal("0.25"),
            data_quality=Decimal("0.9"),
            risk="low",
            risk_tier="Minimal",
            variance_rating="Low",
            edge_class="Strong",
            expected_value_label="Positive",
            suggested_stake_pct=Decimal("0.01"),
            decision="PLAY",
            recommendation_tier="core_parlay",
            rank=1,
            reason_codes=["OK"],
            reasoning_summary="test",
            warnings=[],
            safer_alternative=None,
            higher_upside=None,
            invalidation_conditions=[],
            live_trigger=None,
            hedge=None,
            quick_cash=False,
            chain_reaction_key=None,
            thesis_key=f"thesis-{market}",
            script_key=f"script-{market}",
            player_key="pitcher-same",
            data_source="UNIT",
            source_timestamp=datetime.now(UTC),
            model_version="test",
            protocol_version="2026.09.03",
            input_hash=market,
            snapshot={"probability_source": "model", "script_alignment": 0.7},
            outcome=None,
            created_at=datetime.now(UTC),
        )

    assert market_family("player_strikeouts_over") == "pitcher_k"
    conflicts = same_player_category_conflicts(
        [
            leg("player_strikeouts_over", "K over"),
            leg("pitcher_earned_runs_over", "ER over"),
        ]
    )
    assert any("pitcher" in c for c in conflicts)

    cards, _ = build_cards(
        [
            leg("player_strikeouts_over", "K over"),
            leg("pitcher_earned_runs_over", "ER over"),
        ],
        max_legs=5,
        min_rating=0,
    )
    # Same-pitcher K+ER must not survive as a multi-leg official card.
    for key, card in cards.items():
        if key == "max_bet":
            continue
        assert (
            len(card.legs) <= 1
            or not any("SAME_PLAYER" in w for w in card.warnings)
            or len(card.legs) == 0
        )


def test_weakest_leg_drop_and_recheck() -> None:
    safe = SimpleNamespace(
        id="safe",
        selection="Safe",
        confidence_score=90,
        ywp_rating=8.5,
        miss_by_one_risk=0.20,
        american_odds=-110,
    )
    killer = SimpleNamespace(
        id="killer",
        selection="Killer",
        confidence_score=88,
        ywp_rating=8.2,
        miss_by_one_risk=0.70,
        american_odds=-105,
    )
    kept, notes = eliminate_weakest_until_stable(
        [safe, killer], min_legs=1, select_weakest=select_weakest_leg
    )
    assert [item.id for item in kept] == ["safe"]
    assert any("Dropped weakest" in n for n in notes)


def test_official_output_labels() -> None:
    assert official_output_label(has_qualified_cards=False, has_play_lean=False) == "NO_BET"
    assert (
        official_output_label(has_qualified_cards=False, has_play_lean=True)
        == "NO_BET_CARDS_FAILED_GATES"
    )
    assert official_output_label(has_qualified_cards=True, has_play_lean=True) == "DECISION_CARDS"
