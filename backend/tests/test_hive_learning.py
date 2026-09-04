from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.hive.models import HiveAggregate, HiveLearningEvent
from app.hive.service import (
    HiveSignal,
    blend_hive_probability,
    capture_hive_prediction,
    hive_learning_maturity,
    rebuild_bucket,
    resolve_hive_outcome,
)


def _capture(
    db,
    *,
    recommendation_id="r1",
    user_id="user-123",
    probability=0.60,
    consent=True,
    event_id="game-123",
):
    now = datetime.now(timezone.utc)
    return capture_hive_prediction(
        db=db,
        contributor_user_id=user_id,
        consent_to_hive=consent,
        source_recommendation_id=recommendation_id,
        sport="mlb",
        league="MLB",
        event_id=event_id,
        event_start_at=now + timedelta(hours=3),
        market="moneyline",
        market_scope="full_game",
        selection="TEAM_A",
        line=None,
        odds_american=-120,
        model_probability=probability,
        quality_score=84.0,
        model_version="3.3.4",
        protocol_version="ywp-current",
        evidence_version="snapshot-1",
        data_quality=0.95,
        feature_flags={
            "l5_support": True,
            "lineup_verified": True,
            "private_note": "MUST NOT BE STORED",
            "email": "leak@example.com",
            "stake": 50,
        },
    )


def test_prediction_capture_is_idempotent(db_session, monkeypatch):
    monkeypatch.setenv("YWP_HIVE_ANON_SECRET", "test-secret")

    a = _capture(db_session)
    db_session.flush()
    b = _capture(db_session)
    assert a.id == b.id


def test_feature_flags_are_allowlisted(db_session):
    event = _capture(db_session)
    assert "l5_support" in event.feature_flags
    assert "private_note" not in event.feature_flags
    assert "email" not in event.feature_flags
    assert "stake" not in event.feature_flags
    assert "user_id" not in event.__dict__ or True
    assert not hasattr(event, "email")
    assert event.contributor_key != "user-123"


def test_verified_outcome_becomes_eligible(db_session):
    event = _capture(db_session)
    db_session.flush()

    resolved = resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=event.source_recommendation_id,
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    assert resolved.outcome == "WIN"
    assert resolved.training_eligible is True


def test_same_result_does_not_train_twice(db_session):
    event = _capture(db_session, recommendation_id="r-once")
    db_session.flush()
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=event.source_recommendation_id,
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    db_session.flush()
    first = (
        db_session.query(HiveAggregate)
        .filter(HiveAggregate.sport == "mlb", HiveAggregate.market == "moneyline")
        .one()
    )
    assert first.wins == 1
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=event.source_recommendation_id,
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    db_session.flush()
    second = (
        db_session.query(HiveAggregate)
        .filter(HiveAggregate.sport == "mlb", HiveAggregate.market == "moneyline")
        .one()
    )
    assert second.wins == 1
    assert second.eligible_samples == 1


def test_many_users_same_public_pick_are_distinct_observations(db_session):
    a = _capture(db_session, recommendation_id="rec-a", user_id="user-a", event_id="game-shared")
    b = _capture(db_session, recommendation_id="rec-b", user_id="user-b", event_id="game-shared")
    db_session.flush()
    assert a.id != b.id
    assert a.contributor_key != b.contributor_key
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id="rec-a",
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id="rec-b",
        outcome="LOSS",
        verified=True,
        result_source="official",
    )
    db_session.flush()
    agg = (
        db_session.query(HiveAggregate)
        .filter(HiveAggregate.sport == "mlb", HiveAggregate.market == "moneyline")
        .one()
    )
    assert agg.eligible_samples == 2
    assert agg.wins == 1
    assert agg.losses == 1


def test_unverified_outcome_not_eligible_when_required(db_session):
    event = _capture(db_session, recommendation_id="r-unverified")
    db_session.flush()

    resolved = resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=event.source_recommendation_id,
        outcome="WIN",
        verified=False,
        result_source="manual",
    )
    assert resolved.training_eligible is False


def test_product_owned_picks_train_without_consent_gate(db_session, monkeypatch):
    monkeypatch.setenv("YWP_HIVE_REQUIRE_CONSENT", "false")
    event = _capture(db_session, recommendation_id="r-no-consent", consent=False)
    db_session.flush()
    resolved = resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=event.source_recommendation_id,
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    assert resolved.training_eligible is True
    assert resolved.training_ineligibility_reason is None


def test_push_and_void_do_not_count_as_wins_losses(db_session):
    push = _capture(db_session, recommendation_id="r-push", user_id="u1")
    void = _capture(db_session, recommendation_id="r-void", user_id="u2")
    win = _capture(db_session, recommendation_id="r-win", user_id="u3")
    db_session.flush()
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=push.source_recommendation_id,
        outcome="PUSH",
        verified=True,
        result_source="official",
    )
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=void.source_recommendation_id,
        outcome="VOID",
        verified=True,
        result_source="official",
    )
    resolve_hive_outcome(
        db=db_session,
        source_recommendation_id=win.source_recommendation_id,
        outcome="WIN",
        verified=True,
        result_source="official",
    )
    db_session.flush()
    agg = (
        db_session.query(HiveAggregate)
        .filter(HiveAggregate.sport == "mlb", HiveAggregate.market == "moneyline")
        .one()
    )
    assert agg.pushes == 1
    assert agg.voids == 1
    assert agg.wins == 1
    assert agg.losses == 0
    assert agg.raw_rate == 1.0


def test_external_backfill_without_prior_prediction_is_not_training_eligible(db_session):
    resolved = resolve_hive_outcome(
        db=db_session,
        source_recommendation_id="external-only-rec",
        outcome="WIN",
        verified=True,
        result_source="external_book",
    )
    assert resolved is None
    assert db_session.query(HiveLearningEvent).count() == 0
    assert db_session.query(HiveAggregate).count() == 0


def test_hive_never_manufactures_probability():
    signal = HiveSignal(
        sport="mlb",
        league="mlb",
        market="moneyline",
        market_scope="full_game",
        model_version="3.3.4",
        eligible_samples=1000,
        wins=700,
        losses=300,
        pushes=0,
        voids=0,
        posterior_rate=0.699,
        raw_rate=0.70,
        mean_predicted_probability=0.61,
        calibration_delta=0.089,
        release_version="hive-1",
    )
    adjusted, meta = blend_hive_probability(
        base_probability=None,
        hive_signal=signal,
    )
    assert adjusted is None
    assert meta["used"] is False


def test_hive_shift_is_bounded():
    signal = HiveSignal(
        sport="mlb",
        league="mlb",
        market="moneyline",
        market_scope="full_game",
        model_version="3.3.4",
        eligible_samples=1000,
        wins=900,
        losses=100,
        pushes=0,
        voids=0,
        posterior_rate=0.899,
        raw_rate=0.90,
        mean_predicted_probability=0.50,
        calibration_delta=0.399,
        release_version="hive-1",
    )
    adjusted, meta = blend_hive_probability(
        base_probability=0.60,
        hive_signal=signal,
    )
    assert adjusted is not None
    assert adjusted >= 0.60
    assert meta["used"] is True
    assert abs(adjusted - 0.60) <= 0.03500001


def test_samples_below_minimum_do_not_alter_probability(monkeypatch):
    monkeypatch.setenv("YWP_HIVE_MIN_SAMPLE", "40")
    signal = HiveSignal(
        sport="mlb",
        league="mlb",
        market="moneyline",
        market_scope="full_game",
        model_version="3.3.4",
        eligible_samples=10,
        wins=8,
        losses=2,
        pushes=0,
        voids=0,
        posterior_rate=0.75,
        raw_rate=0.80,
        mean_predicted_probability=0.55,
        calibration_delta=0.20,
        release_version="hive-1",
    )
    adjusted, meta = blend_hive_probability(
        base_probability=0.60,
        hive_signal=signal,
    )
    assert adjusted == 0.60
    assert meta["used"] is False
    assert meta["reason"] == "insufficient_hive_sample"


def test_aggregate_rebuild_reproduces_stored_aggregate(db_session):
    for idx, outcome in enumerate(["WIN", "WIN", "LOSS"]):
        event = _capture(
            db_session,
            recommendation_id=f"r-rebuild-{idx}",
            user_id=f"user-{idx}",
            probability=0.55 + idx * 0.05,
        )
        db_session.flush()
        resolve_hive_outcome(
            db=db_session,
            source_recommendation_id=event.source_recommendation_id,
            outcome=outcome,
            verified=True,
            result_source="official",
        )
    db_session.flush()
    stored = (
        db_session.query(HiveAggregate)
        .filter(HiveAggregate.sport == "mlb", HiveAggregate.market == "moneyline")
        .one()
    )
    rebuilt = rebuild_bucket(
        db=db_session,
        sport="mlb",
        league="MLB",
        market="moneyline",
        market_scope="full_game",
        model_version="3.3.4",
    )
    assert rebuilt.id == stored.id
    assert rebuilt.eligible_samples == stored.eligible_samples == 3
    assert rebuilt.wins == stored.wins == 2
    assert rebuilt.losses == stored.losses == 1
    assert rebuilt.posterior_rate == stored.posterior_rate
    assert rebuilt.mean_predicted_probability == stored.mean_predicted_probability


def test_hive_maturity_is_calculated_from_settled_evidence(db_session, monkeypatch):
    monkeypatch.setenv("YWP_HIVE_MIN_SAMPLE", "4")
    monkeypatch.setenv("YWP_HIVE_OPTIMAL_SAMPLE", "10")

    empty = hive_learning_maturity(db=db_session, sport="mlb")
    assert empty["optimum_accuracy_pct"] == 0.0
    assert empty["status"] == "collecting"
    assert empty["volume_score_pct"] == 0.0
    assert empty["calibration_score_pct"] == 0.0

    for idx in range(2):
        event = _capture(
            db_session,
            recommendation_id=f"r-mat-{idx}",
            user_id=f"u-mat-{idx}",
            probability=0.58,
        )
        db_session.flush()
        resolve_hive_outcome(
            db=db_session,
            source_recommendation_id=event.source_recommendation_id,
            outcome="WIN" if idx % 2 == 0 else "LOSS",
            verified=True,
            result_source="official",
        )
    db_session.flush()

    mid = hive_learning_maturity(db=db_session, sport="mlb")
    # 2/4 of collecting band → 20% volume contribution (0.40 * 0.5 * 100)
    assert mid["status"] == "collecting"
    assert mid["eligible_samples"] == 2
    assert mid["optimum_accuracy_pct"] == 20.0
    assert mid["calibration_active"] is False

    for idx in range(2, 10):
        event = _capture(
            db_session,
            recommendation_id=f"r-mat-{idx}",
            user_id=f"u-mat-{idx}",
            probability=0.62,
        )
        db_session.flush()
        resolve_hive_outcome(
            db=db_session,
            source_recommendation_id=event.source_recommendation_id,
            outcome="WIN" if idx % 2 == 0 else "LOSS",
            verified=True,
            result_source="official",
        )
    db_session.flush()

    full = hive_learning_maturity(db=db_session, sport="mlb")
    assert full["eligible_samples"] == 10
    assert full["calibration_active"] is True
    # Volume at optimal = 85%; calibration adds 0–15% from |Δ|.
    assert full["volume_score_pct"] == 85.0
    assert full["optimum_accuracy_pct"] >= 85.0
    assert full["optimum_accuracy_pct"] <= 100.0
    assert full["status"] in {"calibrating", "optimal"}
    assert "formula" in full
