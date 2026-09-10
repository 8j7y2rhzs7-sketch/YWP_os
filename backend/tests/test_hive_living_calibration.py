from __future__ import annotations

from datetime import datetime, timezone

from app.hive.service import HiveSignal, blend_hive_probability
from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine


def _candidate(**overrides):
    base = dict(
        candidate_id="cand-1",
        event_id="event-1",
        event_name="Away @ Home",
        sport="mlb",
        league="MLB",
        start_time=datetime.now(timezone.utc),
        market_type="moneyline",
        market_period="full_game",
        selection="Away ML",
        american_odds=-110,
        estimated_probability=0.58,
        probability_source="model",
        variance=0.2,
        data_quality=0.95,
        data_source="mlb_stats",
        source_timestamp=datetime.now(timezone.utc),
        thesis_key="thesis-away-ml",
        script_key="script-away-ml",
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
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "confirmed",
            "bullpen": "confirmed",
        },
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_hive_calibration_changes_working_probability():
    evaluation = decision_engine.evaluate(_candidate(), RiskProfile.balanced)
    signal = HiveSignal(
        sport="mlb",
        league="mlb",
        market="moneyline",
        market_scope="full_game",
        model_version="test",
        eligible_samples=50,
        wins=32,
        losses=18,
        pushes=0,
        voids=0,
        posterior_rate=0.64,
        raw_rate=0.64,
        mean_predicted_probability=0.55,
        calibration_delta=0.03,
        release_version="test",
    )
    adjusted, meta = blend_hive_probability(
        base_probability=evaluation.adjusted_probability,
        hive_signal=signal,
    )
    assert meta["used"] is True
    assert adjusted is not None
    before = evaluation.adjusted_probability
    after = decision_engine.apply_hive_calibration(
        evaluation,
        float(adjusted),
        shift_applied=float(meta["shift_applied"]),
    )
    assert "HIVE_CALIBRATION" in after.reason_codes
    assert after.adjusted_probability == adjusted
    assert after.adjusted_probability != before or meta["shift_applied"] == 0.0


def test_hive_calibration_cannot_override_research_skip():
    evaluation = decision_engine.evaluate(_candidate(), RiskProfile.balanced)
    evaluation.reason_codes = [*evaluation.reason_codes, "RESEARCH_INCOMPLETE"]
    evaluation.decision = "SKIP"
    locked = evaluation.adjusted_probability
    after = decision_engine.apply_hive_calibration(
        evaluation,
        0.91,
        shift_applied=0.08,
    )
    assert after.decision == "SKIP"
    assert after.adjusted_probability == locked
    assert "HIVE_CALIBRATION" not in after.reason_codes
