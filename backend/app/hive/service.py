from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .config import settings
from .models import HiveAggregate, HiveLearningEvent


ALLOWED_FLAGS = {
    "l5_support",
    "l10_support",
    "lineup_verified",
    "starter_verified",
    "injury_check",
    "bullpen_edge",
    "weather_edge",
    "market_value",
    "game_script_alignment",
    "vision_support",
    "ain_pass",
    "draw_et_trap",
    "minutes_restriction",
    "data_complete",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _contributor_key(user_id: Any) -> str:
    if not settings.anon_secret:
        raise RuntimeError("YWP_HIVE_ANON_SECRET must be configured when Hive is enabled")
    return hmac.new(
        settings.anon_secret.encode("utf-8"),
        str(user_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _sanitize_flags(flags: dict[str, Any] | None) -> dict[str, Any]:
    if not flags:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in flags.items():
        if key not in ALLOWED_FLAGS:
            continue
        if isinstance(value, (bool, int, float, str)) or value is None:
            sanitized[key] = value
    return sanitized


def _event_idempotency_key(
    contributor_key: str,
    source_recommendation_id: str,
    model_version: str,
) -> str:
    return _stable_hash(
        {
            "contributor": contributor_key,
            "recommendation": str(source_recommendation_id),
            "model_version": model_version,
        }
    )


def _bucket_key(
    sport: str,
    league: str | None,
    market: str,
    market_scope: str,
    model_version: str,
) -> str:
    return _stable_hash(
        {
            "sport": _norm(sport),
            "league": _norm(league),
            "market": _norm(market),
            "scope": _norm(market_scope),
            "model_version": model_version.strip(),
        }
    )


def _training_eligibility(event: HiveLearningEvent) -> tuple[bool, str | None]:
    if not settings.enabled:
        return False, "hive_disabled"
    if settings.require_consent and not event.consent_to_hive:
        return False, "consent_required"
    if event.outcome not in {"WIN", "LOSS", "PUSH", "VOID"}:
        return False, "outcome_missing"
    if settings.require_verified_outcome and not event.outcome_verified:
        return False, "outcome_unverified"
    if event.event_start_at and event.created_at:
        # A Hive predictive sample must have existed before the event started.
        created = event.created_at
        start = event.event_start_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if created >= start:
            return False, "prediction_not_pre_event"
    if event.model_probability is not None and not 0.0 <= event.model_probability <= 1.0:
        return False, "invalid_probability"
    return True, None


def capture_hive_prediction(
    *,
    db: Session,
    contributor_user_id: Any,
    consent_to_hive: bool,
    source_recommendation_id: str,
    sport: str,
    league: str | None,
    event_id: str,
    event_start_at: datetime | None,
    market: str,
    market_scope: str,
    selection: str,
    line: float | None,
    odds_american: int | None,
    model_probability: float | None,
    quality_score: float | None,
    model_version: str,
    protocol_version: str | None = None,
    evidence_version: str | None = None,
    data_quality: float | None = None,
    feature_flags: dict[str, Any] | None = None,
) -> HiveLearningEvent | None:
    if not settings.enabled:
        return None

    contributor = _contributor_key(contributor_user_id)
    idem = _event_idempotency_key(
        contributor, str(source_recommendation_id), model_version
    )

    existing = (
        db.query(HiveLearningEvent)
        .filter(HiveLearningEvent.idempotency_key == idem)
        .one_or_none()
    )
    if existing:
        return existing

    event = HiveLearningEvent(
        idempotency_key=idem,
        contributor_key=contributor,
        source_recommendation_id=str(source_recommendation_id),
        sport=_norm(sport),
        league=_norm(league) or None,
        event_id=str(event_id),
        event_start_at=event_start_at,
        market=_norm(market),
        market_scope=_norm(market_scope),
        selection=selection.strip(),
        line=line,
        odds_american=odds_american,
        model_probability=model_probability,
        quality_score=quality_score,
        model_version=model_version.strip(),
        protocol_version=protocol_version,
        evidence_version=evidence_version,
        data_quality=data_quality,
        feature_flags=_sanitize_flags(feature_flags),
        consent_to_hive=bool(consent_to_hive),
        training_eligible=False,
        training_ineligibility_reason="outcome_missing",
    )
    db.add(event)
    db.flush()
    return event


def record_hive_action(
    *,
    db: Session,
    source_recommendation_id: str,
    action: str,
) -> HiveLearningEvent | None:
    if action not in {"accepted", "rejected", "ignored"}:
        raise ValueError("invalid Hive action")

    event = (
        db.query(HiveLearningEvent)
        .filter(
            HiveLearningEvent.source_recommendation_id
            == str(source_recommendation_id)
        )
        .order_by(HiveLearningEvent.created_at.desc())
        .first()
    )
    if event is None:
        return None
    event.action = action
    event.updated_at = _utcnow()
    db.flush()
    return event


def resolve_hive_outcome(
    *,
    db: Session,
    source_recommendation_id: str,
    outcome: str,
    verified: bool,
    result_source: str,
    resolved_at: datetime | None = None,
) -> HiveLearningEvent | None:
    normalized = outcome.upper()
    if normalized not in {"WIN", "LOSS", "PUSH", "VOID"}:
        raise ValueError("invalid Hive outcome")

    event = (
        db.query(HiveLearningEvent)
        .filter(
            HiveLearningEvent.source_recommendation_id
            == str(source_recommendation_id)
        )
        .order_by(HiveLearningEvent.created_at.desc())
        .first()
    )
    if event is None:
        return None

    # Idempotent exact repeat.
    if (
        event.outcome == normalized
        and bool(event.outcome_verified) == bool(verified)
        and event.result_source == result_source
    ):
        return event

    # Correction is allowed; aggregate is rebuilt from source rows so no double-counting.
    event.outcome = normalized
    event.outcome_verified = bool(verified)
    event.result_source = result_source.strip()
    event.resolved_at = resolved_at or _utcnow()

    eligible, reason = _training_eligibility(event)
    event.training_eligible = eligible
    event.training_ineligibility_reason = reason
    event.updated_at = _utcnow()
    db.flush()

    rebuild_bucket_for_event(db=db, event=event)
    return event


def _beta_posterior_rate(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n <= 0:
        return None

    # Weakly informative Beta(2,2) prior prevents tiny samples from looking certain.
    alpha = 2.0 + wins
    beta = 2.0 + losses
    return alpha / (alpha + beta)


def rebuild_bucket_for_event(*, db: Session, event: HiveLearningEvent) -> HiveAggregate:
    return rebuild_bucket(
        db=db,
        sport=event.sport,
        league=event.league,
        market=event.market,
        market_scope=event.market_scope,
        model_version=event.model_version,
    )


def rebuild_bucket(
    *,
    db: Session,
    sport: str,
    league: str | None,
    market: str,
    market_scope: str,
    model_version: str,
) -> HiveAggregate:
    sport_n = _norm(sport)
    league_n = _norm(league) or None
    market_n = _norm(market)
    scope_n = _norm(market_scope)
    key = _bucket_key(sport_n, league_n, market_n, scope_n, model_version)

    q = db.query(HiveLearningEvent).filter(
        HiveLearningEvent.sport == sport_n,
        HiveLearningEvent.market == market_n,
        HiveLearningEvent.market_scope == scope_n,
        HiveLearningEvent.model_version == model_version,
        HiveLearningEvent.training_eligible.is_(True),
    )
    if league_n is None:
        q = q.filter(HiveLearningEvent.league.is_(None))
    else:
        q = q.filter(HiveLearningEvent.league == league_n)

    rows = q.all()
    wins = sum(1 for r in rows if r.outcome == "WIN")
    losses = sum(1 for r in rows if r.outcome == "LOSS")
    pushes = sum(1 for r in rows if r.outcome == "PUSH")
    voids = sum(1 for r in rows if r.outcome == "VOID")

    resolved_binary = wins + losses
    raw_rate = (wins / resolved_binary) if resolved_binary else None
    posterior = _beta_posterior_rate(wins, losses)

    probs = [
        float(r.model_probability)
        for r in rows
        if r.outcome in {"WIN", "LOSS"} and r.model_probability is not None
    ]
    mean_pred = (sum(probs) / len(probs)) if probs else None
    calibration_delta = (
        posterior - mean_pred
        if posterior is not None and mean_pred is not None
        else None
    )

    agg = (
        db.query(HiveAggregate)
        .filter(HiveAggregate.bucket_key == key)
        .one_or_none()
    )
    if agg is None:
        agg = HiveAggregate(
            bucket_key=key,
            sport=sport_n,
            league=league_n,
            market=market_n,
            market_scope=scope_n,
            model_version=model_version,
        )
        db.add(agg)

    agg.eligible_samples = len(rows)
    agg.wins = wins
    agg.losses = losses
    agg.pushes = pushes
    agg.voids = voids
    agg.sum_predicted_probability = sum(probs)
    agg.predicted_probability_count = len(probs)
    agg.raw_rate = raw_rate
    agg.posterior_rate = posterior
    agg.mean_predicted_probability = mean_pred
    agg.calibration_delta = calibration_delta
    agg.updated_at = _utcnow()
    db.flush()
    return agg


@dataclass(frozen=True)
class HiveSignal:
    sport: str
    league: str | None
    market: str
    market_scope: str
    model_version: str
    eligible_samples: int
    wins: int
    losses: int
    pushes: int
    voids: int
    posterior_rate: float | None
    raw_rate: float | None
    mean_predicted_probability: float | None
    calibration_delta: float | None
    release_version: str


def get_hive_signal(
    *,
    db: Session,
    sport: str,
    league: str | None,
    market: str,
    market_scope: str,
    model_version: str,
) -> HiveSignal:
    key = _bucket_key(sport, league, market, market_scope, model_version)
    agg = (
        db.query(HiveAggregate)
        .filter(HiveAggregate.bucket_key == key)
        .one_or_none()
    )

    if agg is None:
        return HiveSignal(
            sport=_norm(sport),
            league=_norm(league) or None,
            market=_norm(market),
            market_scope=_norm(market_scope),
            model_version=model_version,
            eligible_samples=0,
            wins=0,
            losses=0,
            pushes=0,
            voids=0,
            posterior_rate=None,
            raw_rate=None,
            mean_predicted_probability=None,
            calibration_delta=None,
            release_version=settings.release_version,
        )

    return HiveSignal(
        sport=agg.sport,
        league=agg.league,
        market=agg.market,
        market_scope=agg.market_scope,
        model_version=agg.model_version,
        eligible_samples=agg.eligible_samples,
        wins=agg.wins,
        losses=agg.losses,
        pushes=agg.pushes,
        voids=agg.voids,
        posterior_rate=agg.posterior_rate,
        raw_rate=agg.raw_rate,
        mean_predicted_probability=agg.mean_predicted_probability,
        calibration_delta=agg.calibration_delta,
        release_version=settings.release_version,
    )


def hive_learning_maturity(
    *,
    db: Session,
    sport: str | None = None,
) -> dict[str, Any]:
    """Compute Hive optimum-accuracy readiness from live evidence.

    This is not a cosmetic gauge. The percentage is derived from:

    1. Settled eligible sample volume (piecewise toward optimal_sample)
       - 0 → min_sample maps to 0–40%  (collecting; blend still locked)
       - min_sample → optimal_sample maps to 40–85% (calibrating volume)
    2. Observed calibration quality across buckets with enough samples
       - contributes the final 0–15% once blend is active
       - score = 1 - clamp(mean(|calibration_delta|) / 0.15, 0, 1)

    100% means: enough settled outcomes AND tight calibration error.
    """
    eligible_q = db.query(HiveLearningEvent).filter(
        HiveLearningEvent.training_eligible.is_(True)
    )
    pending_q = db.query(HiveLearningEvent).filter(HiveLearningEvent.outcome.is_(None))
    resolved_q = db.query(HiveLearningEvent).filter(
        HiveLearningEvent.outcome.isnot(None)
    )
    agg_q = db.query(HiveAggregate).filter(HiveAggregate.eligible_samples > 0)
    if sport:
        sport_n = _norm(sport)
        eligible_q = eligible_q.filter(HiveLearningEvent.sport == sport_n)
        pending_q = pending_q.filter(HiveLearningEvent.sport == sport_n)
        resolved_q = resolved_q.filter(HiveLearningEvent.sport == sport_n)
        agg_q = agg_q.filter(HiveAggregate.sport == sport_n)

    eligible = int(eligible_q.count())
    pending = int(pending_q.count())
    resolved = int(resolved_q.count())
    min_sample = max(1, int(settings.min_sample))
    optimal = max(min_sample, int(settings.optimal_sample))

    if eligible < min_sample:
        volume_score = 0.40 * (eligible / min_sample)
    else:
        volume_score = 0.40 + 0.45 * min(
            1.0, (eligible - min_sample) / max(1, optimal - min_sample)
        )

    mature_buckets = [
        agg
        for agg in agg_q.all()
        if int(agg.eligible_samples or 0) >= min_sample
        and agg.calibration_delta is not None
    ]
    if mature_buckets:
        mean_abs_delta = sum(abs(float(agg.calibration_delta)) for agg in mature_buckets) / len(
            mature_buckets
        )
        # |delta| of 0.00 → perfect (1.0); |delta| ≥ 0.15 → no credit.
        calibration_quality = max(0.0, min(1.0, 1.0 - (mean_abs_delta / 0.15)))
        calibrated_bucket_count = len(mature_buckets)
    else:
        mean_abs_delta = None
        calibration_quality = 0.0
        calibrated_bucket_count = 0

    calibration_score = 0.15 * calibration_quality if eligible >= min_sample else 0.0
    pct = round(min(100.0, (volume_score + calibration_score) * 100.0), 1)

    if pct >= 100.0 - 1e-9:
        status = "optimal"
    elif eligible >= min_sample:
        status = "calibrating"
    else:
        status = "collecting"

    wins = sum(int(agg.wins or 0) for agg in mature_buckets) if mature_buckets else 0
    losses = sum(int(agg.losses or 0) for agg in mature_buckets) if mature_buckets else 0

    return {
        "eligible_samples": eligible,
        "pending_samples": pending,
        "resolved_samples": resolved,
        "min_sample_for_calibration": min_sample,
        "optimal_sample": optimal,
        "volume_score_pct": round(volume_score * 100.0, 1),
        "calibration_score_pct": round(calibration_score * 100.0, 1),
        "calibration_quality": round(calibration_quality, 4),
        "mean_abs_calibration_delta": (
            round(mean_abs_delta, 6) if mean_abs_delta is not None else None
        ),
        "calibrated_bucket_count": calibrated_bucket_count,
        "wins": wins,
        "losses": losses,
        "optimum_accuracy_pct": pct,
        "calibration_active": eligible >= min_sample,
        "status": status,
        "formula": {
            "volume_weight": "0–40% collecting to min_sample, then 40–85% to optimal_sample",
            "calibration_weight": "0–15% from 1 - clamp(|Δ|/0.15) once blend is active",
            "optimal_means": "enough settled samples and tight calibration error",
        },
        "release_version": settings.release_version,
    }


def blend_hive_probability(
    *,
    base_probability: float | None,
    hive_signal: HiveSignal,
) -> tuple[float | None, dict[str, Any]]:
    meta = {
        "eligible_samples": hive_signal.eligible_samples,
        "wins": hive_signal.wins,
        "losses": hive_signal.losses,
        "posterior_rate": hive_signal.posterior_rate,
        "release_version": hive_signal.release_version,
        "shift_applied": 0.0,
        "used": False,
        "reason": None,
    }

    if base_probability is None:
        meta["reason"] = "base_probability_unavailable"
        return None, meta

    base = max(0.0, min(1.0, float(base_probability)))

    if hive_signal.eligible_samples < settings.min_sample:
        meta["reason"] = "insufficient_hive_sample"
        return base, meta

    if hive_signal.posterior_rate is None:
        meta["reason"] = "hive_rate_unavailable"
        return base, meta

    # Calibration-style adjustment: compare aggregate posterior outcome rate
    # with the average probability the model historically assigned in this bucket.
    if (
        hive_signal.mean_predicted_probability is not None
        and hive_signal.calibration_delta is not None
    ):
        desired_shift = hive_signal.calibration_delta
    else:
        # Conservative fallback: move only 25% toward observed posterior.
        desired_shift = (hive_signal.posterior_rate - base) * 0.25

    bound = abs(settings.max_probability_shift)
    shift = max(-bound, min(bound, desired_shift))
    adjusted = max(0.0, min(1.0, base + shift))

    meta["shift_applied"] = round(adjusted - base, 8)
    meta["used"] = True
    meta["reason"] = "bounded_hive_calibration"
    return adjusted, meta
