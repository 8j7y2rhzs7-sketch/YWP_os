"""Nine-stage edge pipeline — market math, MC, thresholds, calibration."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine
from app.services.pipeline import (
    PIPELINE_STAGES,
    brier_score,
    compare_to_market,
    devig_two_way,
    estimate_stat_distribution,
    map_decision_threshold,
    simulate_ticket,
    summarize_calibration,
)
from app.services.ticket_builder import build_cards


def test_pipeline_has_nine_stages() -> None:
    assert len(PIPELINE_STAGES) == 9
    assert PIPELINE_STAGES[0]["key"] == "verification"
    assert PIPELINE_STAGES[8]["key"] == "calibration"


def test_devig_two_way_removes_vig() -> None:
    # Classic -110 / -110 → each fair ≈ 50%.
    a, b = devig_two_way(-110, -110)
    assert abs(a - 0.5) < 0.001
    assert abs(b - 0.5) < 0.001
    raw = compare_to_market(model_probability=0.55, american_odds=-110)
    assert raw["status"] == "raw_implied_vig_proxy"
    fair = compare_to_market(
        model_probability=0.55, american_odds=-110, opposite_american_odds=-110
    )
    assert fair["status"] == "devigged_two_way"
    assert fair["fair_implied_probability"] == 0.5
    assert fair["edge_vs_fair"] == 0.05


def test_stat_distribution_emits_mean_variance_tail() -> None:
    dist = estimate_stat_distribution(
        line=22.5,
        is_over=True,
        mean=24.0,
        sigma=4.0,
        hit_rate=0.7,
        model_probability=0.62,
    )
    assert dist["status"] == "ok"
    assert dist["mean"] == 24.0
    assert dist["variance"] == 16.0
    assert dist["tail_probability"] is not None
    assert dist["tail_probability"] > 0.5


def test_decision_threshold_mapping() -> None:
    q = map_decision_threshold(
        decision="PLAY", confidence_score=90, edge=0.05, miss_by_one_risk=0.2
    )
    assert q["threshold"] == "qualify"
    assert q["force_pick"] is False
    b = map_decision_threshold(
        decision="LEAN", confidence_score=80, edge=0.02, miss_by_one_risk=0.3
    )
    assert b["threshold"] == "borderline"
    r = map_decision_threshold(
        decision="SKIP", confidence_score=60, edge=-0.01, miss_by_one_risk=0.8
    )
    assert r["threshold"] == "reject"


def test_monte_carlo_same_game_below_independent_product() -> None:
    now = datetime.now(UTC)

    def leg(i: int, p: float) -> SimpleNamespace:
        return SimpleNamespace(
            id=str(uuid4()),
            event_id="game-1",
            player_key=f"p{i}",
            script_key=f"s{i}",
            thesis_key=f"t{i}",
            market_type="player_points_over",
            selection=f"Player {i} Over 20.5",
            adjusted_probability=Decimal(str(p)),
            snapshot={"probability_source": "model", "model_probability": p},
        )

    legs = [leg(1, 0.6), leg(2, 0.6), leg(3, 0.6)]
    mc = simulate_ticket(legs, sims=5000, seed=7)
    assert mc["status"] == "monte_carlo"
    assert mc["win_probability"] is not None
    # Same-game dependence is detected; all-hit rate sits between independence and min(p).
    assert mc["correlation"]["max_rho"] > 0
    assert mc["independent_product"] <= mc["win_probability"] + 0.02
    assert mc["win_probability"] <= 0.6 + 0.02


def test_evaluate_attaches_pipeline_payload() -> None:
    now = datetime.now(UTC)
    candidate = CandidateInput(
        candidate_id="pipe-1",
        event_id="event-1",
        event_name="A @ B",
        sport="wnba",
        league="WNBA",
        start_time=now,
        market_type="player_points_over",
        selection="Star Over 22.5 points",
        line=Decimal("22.5"),
        american_odds=-110,
        opposite_american_odds=-110,
        estimated_probability=0.58,
        variance=0.3,
        data_quality=0.9,
        data_source="ESPN_PLAYER_PROP_MODEL",
        probability_source="model",
        source_timestamp=now,
        source_status={"market": "confirmed", "schedule": "confirmed"},
        recent_hit_rate=0.7,
        average_cushion=2.5,
        cushion_scale=4.0,
        miss_by_one_count_l10=1,
        matchup_score=0.7,
        script_alignment=0.7,
        multiple_paths_score=0.7,
        role_stability=0.8,
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        injuries_verified=True,
        sport_specific_sweep_complete=True,
        independent_value_verified=True,
        motivation_rotation_verified=True,
        starter_confirmed=True,
        thesis_key="pts-over",
        script_key="form-script",
    )
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert "pipeline" in evaluation.payload
    assert evaluation.payload["pipeline_threshold"] in {"qualify", "borderline", "reject"}
    assert evaluation.payload["market_comparison"]["status"] == "devigged_two_way"
    assert evaluation.payload["pipeline_distribution"]["status"] == "ok"


def test_build_cards_exposes_monte_carlo_fields() -> None:
    now = datetime.now(UTC)

    def play(i: int) -> SimpleNamespace:
        return SimpleNamespace(
            id=str(uuid4()),
            analysis_id=str(uuid4()),
            created_by_user_id=str(uuid4()),
            candidate_id=f"c{i}",
            event_id=f"e{i}",
            event_name="A @ B",
            sport="mlb",
            league="MLB",
            slate_date=date.today(),
            mode="pregame",
            market_type="moneyline",
            market_period="full_game",
            selection=f"Team {i} ML",
            line=None,
            american_odds=-110,
            estimated_probability=Decimal("0.58"),
            implied_probability=Decimal("0.50"),
            adjusted_probability=Decimal("0.58"),
            edge=Decimal("0.08"),
            expected_value=Decimal("0.06"),
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
            recommendation_tier="cash_builder",
            rank=i,
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
            thesis_key=f"t{i}",
            script_key=f"s{i}",
            player_key=f"p{i}",
            data_source="UNIT",
            source_timestamp=now,
            model_version="test",
            protocol_version="2026.09.03",
            input_hash=f"h{i}",
            snapshot={
                "probability_source": "model",
                "model_probability": 0.58,
                "pipeline_threshold": "qualify",
                "pipeline_distribution": {"tail_probability": 0.58},
            },
            outcome=None,
            created_at=now,
        )

    cards, _ = build_cards([play(i) for i in range(1, 4)], max_legs=5, min_rating=0)
    assert "elite_two" in cards
    card = cards["elite_two"]
    assert card.pipeline_threshold in {"qualify", "borderline", "reject"}
    assert card.joint_probability_status in {"monte_carlo", "single_leg", "independent_product"}
    assert card.monte_carlo_sims is not None


def test_calibration_brier_and_by_market() -> None:
    assert abs(brier_score(0.7, True) - 0.09) < 1e-9
    summary = summarize_calibration(
        [
            (0.7, True, 0.02, "player_points_over"),
            (0.6, False, -0.01, "player_points_over"),
            (0.55, True, 0.0, "moneyline"),
        ]
    )
    assert summary["n"] == 3
    assert summary["brier"] is not None
    assert summary["mean_clv"] is not None
    assert len(summary["by_market"]) == 2
