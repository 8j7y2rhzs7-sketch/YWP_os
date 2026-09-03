from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine
from app.services.readiness import candidate_readiness, candidate_verification_gaps


def candidate(**changes) -> CandidateInput:
    data = {
        "candidate_id": "candidate-1",
        "event_id": "event-1",
        "event_name": "Demo Event",
        "sport": "mlb",
        "league": "MLB",
        "start_time": datetime.now(UTC),
        "market_type": "player_strikeouts_over",
        "selection": "Pitcher over 5.5 strikeouts",
        "line": Decimal("5.5"),
        "american_odds": -110,
        "estimated_probability": 0.64,
        "variance": 0.3,
        "data_quality": 0.95,
        "data_source": "TEST",
        "source_timestamp": datetime.now(UTC),
        "source_status": {"market": "confirmed", "lineup": "confirmed"},
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
        "thesis_key": "pitcher-k-over",
        "script_key": "pitcher-duration-script",
    }
    data.update(changes)
    return CandidateInput(**data)


def test_first_start_back_and_duration_are_hard_gates() -> None:
    evaluation = decision_engine.evaluate(
        candidate(
            market_is_pitcher_strikeout_over=True,
            first_start_back=True,
            normal_workload_confirmed=False,
            k_duration_verified=False,
        )
    )
    assert evaluation.decision == "SKIP"
    assert "FIRST_START_BACK_EXCLUSION" in evaluation.reason_codes
    assert "K_DURATION_GATE_FAILED" in evaluation.reason_codes


def test_line_escalation_and_low_total_two_path_gate() -> None:
    evaluation = decision_engine.evaluate(
        candidate(
            market_type="team_total_over",
            selection="Team over 4.5",
            line=Decimal("4.5"),
            base_line=Decimal("3.5"),
            alt_line_approved=False,
            low_alt_over=True,
            credible_scoring_paths=1,
            dominant_scoring_path_verified=False,
        )
    )
    assert evaluation.decision == "SKIP"
    assert "LINE_ESCALATION_BLOCKED" in evaluation.reason_codes
    assert "LOW_TOTAL_TWO_PATH_GATE_FAILED" in evaluation.reason_codes


def test_soccer_regulation_draw_trap_is_blocked() -> None:
    evaluation = decision_engine.evaluate(
        candidate(
            sport="soccer",
            league="Demo Cup",
            market_type="moneyline",
            market_period="90_min",
            selection="Favorite 90-minute ML",
            is_knockout=True,
            draw_probability=0.30,
            extra_time_available=True,
            to_qualify_market_available=True,
            market_is_pitcher_strikeout_over=False,
        )
    )
    assert evaluation.decision == "SKIP"
    assert "EXTRA_TIME_TRAP" in evaluation.reason_codes


def test_risk_profile_changes_stake_only_not_official_pick() -> None:
    verified = candidate(
        schedule_verified=True,
        universe_scan_complete=True,
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
        normal_workload_confirmed=True,
        k_duration_verified=True,
    )
    conservative = decision_engine.evaluate(verified, RiskProfile.conservative)
    aggressive = decision_engine.evaluate(verified, RiskProfile.aggressive)

    assert conservative.decision == aggressive.decision
    assert conservative.confidence_score == aggressive.confidence_score
    assert conservative.ywp_intelligence_score == aggressive.ywp_intelligence_score
    assert conservative.vision_score == aggressive.vision_score
    assert conservative.input_hash == aggressive.input_hash
    assert conservative.suggested_stake_pct < aggressive.suggested_stake_pct


def test_market_price_is_not_accepted_as_independent_ywp_probability() -> None:
    market_only = candidate(
        probability_source="market_implied",
        schedule_verified=True,
        universe_scan_complete=True,
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
    )

    evaluation = decision_engine.evaluate(market_only)

    assert candidate_readiness(market_only) == "PARTIAL"
    assert "independent model probability" in candidate_verification_gaps(market_only)
    assert evaluation.decision == "SKIP"
    assert "NO_INDEPENDENT_PROBABILITY" in evaluation.reason_codes


def test_fully_researched_manual_candidate_can_be_verified() -> None:
    researched = candidate(
        probability_source="manual_verified",
        schedule_verified=True,
        universe_scan_complete=True,
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
    )

    assert candidate_readiness(researched) == "VERIFIED"
    assert candidate_verification_gaps(researched) == []
