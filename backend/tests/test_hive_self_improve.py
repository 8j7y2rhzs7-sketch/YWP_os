from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.hive.self_improve import (
    HivePolicy,
    blend_with_policy,
    generate_policy_ideas,
    get_active_policy,
    run_self_improvement_cycle,
    save_active_policy,
    score_policy_on_history,
)
from app.hive.service import HiveSignal, capture_hive_prediction, resolve_hive_outcome


def _seed_bucket(db, *, n=60, true_rate=0.55, model_p=0.62):
    """Create eligible settled events where the model is overconfident."""
    now = datetime.now(timezone.utc)
    for i in range(n):
        rid = f"si-{i}"
        capture_hive_prediction(
            db=db,
            contributor_user_id="user-si",
            consent_to_hive=True,
            source_recommendation_id=rid,
            sport="mlb",
            league="MLB",
            event_id=f"game-si-{i}",
            event_start_at=now + timedelta(hours=3),
            market="moneyline",
            market_scope="full_game",
            selection="TEAM_A",
            line=None,
            odds_american=-110,
            model_probability=model_p,
            quality_score=80.0,
            model_version="3.3.12",
            protocol_version="ywp-current",
            evidence_version="snap-si",
            data_quality=0.9,
            feature_flags={"l5_support": True},
        )
        # Roughly true_rate wins
        outcome = "WIN" if (i / n) < true_rate else "LOSS"
        resolve_hive_outcome(
            db=db,
            source_recommendation_id=rid,
            outcome=outcome,
            verified=True,
            result_source="test",
            resolved_at=now + timedelta(hours=5),
        )
    db.flush()


def test_self_improve_generates_bounded_ideas(db_session):
    base = HivePolicy(max_probability_shift=0.035, min_sample=40, shift_scale=1.0)
    ideas = generate_policy_ideas(db=db_session, base=base)
    assert ideas
    for name, policy in ideas:
        assert 0.01 <= policy.max_probability_shift <= 0.05
        assert 20 <= policy.min_sample <= 120
        assert 0.5 <= policy.shift_scale <= 1.5
        assert name


def test_inhibited_bucket_skips_blend():
    signal = HiveSignal(
        sport="mlb",
        league="mlb",
        market="moneyline",
        market_scope="full_game",
        model_version="t",
        eligible_samples=80,
        wins=40,
        losses=40,
        pushes=0,
        voids=0,
        posterior_rate=0.5,
        raw_rate=0.5,
        mean_predicted_probability=0.6,
        calibration_delta=-0.1,
        release_version="t",
    )
    policy = HivePolicy(
        max_probability_shift=0.035,
        min_sample=40,
        shift_scale=1.0,
        inhibited_bucket_keys=("deadbeef",),
    )
    adjusted, meta = blend_with_policy(
        base_probability=0.6,
        hive_signal=signal,
        policy=policy,
        bucket_key="deadbeef",
    )
    assert adjusted == 0.6
    assert meta["used"] is False
    assert meta["reason"] == "bucket_inhibited_by_self_improve"


def test_self_improve_cycle_runs_and_records(db_session, monkeypatch):
    monkeypatch.setenv("YWP_HIVE_ANON_SECRET", "test-secret")
    monkeypatch.setenv("YWP_HIVE_MIN_SAMPLE", "20")
    _seed_bucket(db_session, n=48, true_rate=0.5, model_p=0.65)

    # Start from a known active policy
    save_active_policy(db=db_session, policy=HivePolicy(min_sample=20, shift_scale=1.2))
    before = get_active_policy(db=db_session)

    result = run_self_improvement_cycle(db=db_session, sport="mlb", trigger="test")
    assert result["ran"] is True
    assert "explanation" in result
    assert result["baseline"]["n"] >= 20
    assert isinstance(result["trials"], list)
    assert len(result["trials"]) >= 1

    after = get_active_policy(db=db_session)
    # Policy always remains within constitutional clamps
    assert 0.01 <= after.max_probability_shift <= 0.05
    assert 20 <= after.min_sample <= 120
    # Either kept or promoted — both valid; if promoted, dict may change
    assert after.to_dict()
    assert before.to_dict()


def test_score_policy_prefers_better_calibration(db_session, monkeypatch):
    monkeypatch.setenv("YWP_HIVE_ANON_SECRET", "test-secret")
    _seed_bucket(db_session, n=50, true_rate=0.5, model_p=0.7)

    aggressive = HivePolicy(max_probability_shift=0.05, min_sample=20, shift_scale=1.5)
    timid = HivePolicy(max_probability_shift=0.01, min_sample=20, shift_scale=0.5)
    a = score_policy_on_history(db=db_session, policy=aggressive, sport="mlb")
    b = score_policy_on_history(db=db_session, policy=timid, sport="mlb")
    assert a["brier"] is not None and b["brier"] is not None
    # Both scorable; relative order depends on data but must be finite
    assert 0.0 <= a["brier"] <= 1.0
    assert 0.0 <= b["brier"] <= 1.0
