"""Hive self-improvement loop — invent, simulate, promote better learning tactics.

This is the second loop: not only calibrate picks, but search for better *ways*
to calibrate, using settled history as the judge. Humans set constitutional
bounds; Hive proposes within those bounds and only keeps proven winners.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from .config import settings
from .models import HiveAggregate, HiveLearningEvent, HiveModelSnapshot
from .service import HiveSignal, _beta_posterior_rate, _norm


ACTIVE_POLICY_TYPE = "active_policy"
ACTIVE_POLICY_RELEASE = "hive-policy-current"
CYCLE_SNAPSHOT_TYPE = "self_improvement_cycle"

# Constitutional ceilings — Hive may never exceed these even if a proposal wins.
HARD_MAX_SHIFT = 0.05
HARD_MIN_SAMPLE_FLOOR = 20
HARD_MIN_SAMPLE_CEILING = 120
PROMOTE_EPSILON = 0.00025  # require clear Brier improvement to promote


@dataclass(frozen=True)
class HivePolicy:
    max_probability_shift: float = 0.035
    min_sample: int = 40
    shift_scale: float = 1.0
    inhibited_bucket_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_probability_shift": float(self.max_probability_shift),
            "min_sample": int(self.min_sample),
            "shift_scale": float(self.shift_scale),
            "inhibited_bucket_keys": list(self.inhibited_bucket_keys),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "HivePolicy":
        raw = raw or {}
        keys = raw.get("inhibited_bucket_keys") or []
        return cls(
            max_probability_shift=float(
                raw.get("max_probability_shift", settings.max_probability_shift)
            ),
            min_sample=int(raw.get("min_sample", settings.min_sample)),
            shift_scale=float(raw.get("shift_scale", 1.0)),
            inhibited_bucket_keys=tuple(str(k) for k in keys),
        )

    def clamped(self) -> "HivePolicy":
        return HivePolicy(
            max_probability_shift=max(
                0.01, min(HARD_MAX_SHIFT, float(self.max_probability_shift))
            ),
            min_sample=max(
                HARD_MIN_SAMPLE_FLOOR,
                min(HARD_MIN_SAMPLE_CEILING, int(self.min_sample)),
            ),
            shift_scale=max(0.5, min(1.5, float(self.shift_scale))),
            inhibited_bucket_keys=tuple(dict.fromkeys(self.inhibited_bucket_keys))[:32],
        )


def default_policy() -> HivePolicy:
    return HivePolicy(
        max_probability_shift=float(settings.max_probability_shift),
        min_sample=int(settings.min_sample),
        shift_scale=1.0,
        inhibited_bucket_keys=(),
    ).clamped()


def get_active_policy(*, db: Session) -> HivePolicy:
    row = (
        db.query(HiveModelSnapshot)
        .filter(
            HiveModelSnapshot.snapshot_type == ACTIVE_POLICY_TYPE,
            HiveModelSnapshot.release_version == ACTIVE_POLICY_RELEASE,
        )
        .order_by(HiveModelSnapshot.created_at.desc())
        .first()
    )
    if row is None or not isinstance(row.parameters, dict):
        return default_policy()
    return HivePolicy.from_dict(row.parameters).clamped()


def save_active_policy(*, db: Session, policy: HivePolicy, notes: str | None = None) -> HiveModelSnapshot:
    policy = policy.clamped()
    existing = (
        db.query(HiveModelSnapshot)
        .filter(
            HiveModelSnapshot.snapshot_type == ACTIVE_POLICY_TYPE,
            HiveModelSnapshot.release_version == ACTIVE_POLICY_RELEASE,
        )
        .first()
    )
    if existing is None:
        existing = HiveModelSnapshot(
            release_version=ACTIVE_POLICY_RELEASE,
            snapshot_type=ACTIVE_POLICY_TYPE,
            parameters=policy.to_dict(),
            sample_count=0,
            notes=notes,
        )
        db.add(existing)
    else:
        existing.parameters = policy.to_dict()
        existing.notes = notes
        existing.created_at = datetime.now(timezone.utc)
    db.flush()
    return existing


def blend_with_policy(
    *,
    base_probability: float | None,
    hive_signal: HiveSignal,
    policy: HivePolicy,
    bucket_key: str | None = None,
) -> tuple[float | None, dict[str, Any]]:
    """Apply Hive blend under an explicit policy (for live + simulation)."""
    policy = policy.clamped()
    meta: dict[str, Any] = {
        "eligible_samples": hive_signal.eligible_samples,
        "wins": hive_signal.wins,
        "losses": hive_signal.losses,
        "posterior_rate": hive_signal.posterior_rate,
        "release_version": hive_signal.release_version,
        "shift_applied": 0.0,
        "used": False,
        "reason": None,
        "policy": policy.to_dict(),
    }

    if base_probability is None:
        meta["reason"] = "base_probability_unavailable"
        return None, meta

    if bucket_key and bucket_key in policy.inhibited_bucket_keys:
        meta["reason"] = "bucket_inhibited_by_self_improve"
        return max(0.0, min(1.0, float(base_probability))), meta

    if hive_signal.eligible_samples < policy.min_sample:
        meta["reason"] = "insufficient_hive_sample"
        return max(0.0, min(1.0, float(base_probability))), meta

    # Temporarily honor policy bounds via settings-shaped signal path.
    # Duplicate core math so simulation never mutates global env.
    base = max(0.0, min(1.0, float(base_probability)))
    if hive_signal.posterior_rate is None:
        meta["reason"] = "hive_rate_unavailable"
        return base, meta

    if (
        hive_signal.mean_predicted_probability is not None
        and hive_signal.calibration_delta is not None
    ):
        desired_shift = float(hive_signal.calibration_delta) * float(policy.shift_scale)
    else:
        desired_shift = (float(hive_signal.posterior_rate) - base) * 0.25 * float(
            policy.shift_scale
        )

    bound = abs(float(policy.max_probability_shift))
    shift = max(-bound, min(bound, desired_shift))
    adjusted = max(0.0, min(1.0, base + shift))
    meta["shift_applied"] = round(adjusted - base, 8)
    meta["used"] = True
    meta["reason"] = "bounded_hive_calibration"
    return adjusted, meta


def _bucket_key_from_event(event: HiveLearningEvent) -> str:
    from .service import _bucket_key

    return _bucket_key(
        event.sport,
        event.league,
        event.market,
        event.market_scope,
        event.model_version,
    )


def _signal_from_aggregate(agg: HiveAggregate) -> HiveSignal:
    return HiveSignal(
        sport=agg.sport,
        league=agg.league,
        market=agg.market,
        market_scope=agg.market_scope,
        model_version=agg.model_version,
        eligible_samples=int(agg.eligible_samples or 0),
        wins=int(agg.wins or 0),
        losses=int(agg.losses or 0),
        pushes=int(agg.pushes or 0),
        voids=int(agg.voids or 0),
        posterior_rate=agg.posterior_rate,
        raw_rate=agg.raw_rate,
        mean_predicted_probability=agg.mean_predicted_probability,
        calibration_delta=agg.calibration_delta,
        release_version=settings.release_version,
    )


def _leave_one_out_signal(
    *,
    events: list[HiveLearningEvent],
    holdout: HiveLearningEvent,
) -> HiveSignal | None:
    peers = [
        e
        for e in events
        if e.id != holdout.id
        and e.outcome in {"WIN", "LOSS"}
        and e.training_eligible
    ]
    if not peers:
        return None
    wins = sum(1 for e in peers if e.outcome == "WIN")
    losses = sum(1 for e in peers if e.outcome == "LOSS")
    probs = [
        float(e.model_probability)
        for e in peers
        if e.model_probability is not None
    ]
    posterior = _beta_posterior_rate(wins, losses)
    mean_pred = (sum(probs) / len(probs)) if probs else None
    calibration_delta = (
        posterior - mean_pred
        if posterior is not None and mean_pred is not None
        else None
    )
    return HiveSignal(
        sport=holdout.sport,
        league=holdout.league,
        market=holdout.market,
        market_scope=holdout.market_scope,
        model_version=holdout.model_version,
        eligible_samples=len(peers),
        wins=wins,
        losses=losses,
        pushes=0,
        voids=0,
        posterior_rate=posterior,
        raw_rate=(wins / (wins + losses)) if (wins + losses) else None,
        mean_predicted_probability=mean_pred,
        calibration_delta=calibration_delta,
        release_version=settings.release_version,
    )


def score_policy_on_history(
    *,
    db: Session,
    policy: HivePolicy,
    sport: str | None = None,
) -> dict[str, Any]:
    """Score a policy with leave-one-out Brier on settled eligible events.

    Uses base model probabilities as the prediction being adjusted — never
    trains on Hive-adjusted values (anti feedback-loop rule).
    """
    q = db.query(HiveLearningEvent).filter(
        HiveLearningEvent.training_eligible.is_(True),
        HiveLearningEvent.outcome.in_(["WIN", "LOSS"]),
        HiveLearningEvent.model_probability.isnot(None),
    )
    if sport:
        q = q.filter(HiveLearningEvent.sport == _norm(sport))
    events = q.all()
    if len(events) < max(10, HARD_MIN_SAMPLE_FLOOR):
        return {
            "n": len(events),
            "brier": None,
            "base_brier": None,
            "helps": 0,
            "hurts": 0,
            "reason": "insufficient_history",
        }

    by_bucket: dict[str, list[HiveLearningEvent]] = {}
    for event in events:
        by_bucket.setdefault(_bucket_key_from_event(event), []).append(event)

    hive_sq = 0.0
    base_sq = 0.0
    n = 0
    helps = 0
    hurts = 0
    for bucket_events in by_bucket.values():
        if len(bucket_events) < 3:
            continue
        for event in bucket_events:
            y = 1.0 if event.outcome == "WIN" else 0.0
            p0 = float(event.model_probability)
            base_err = (p0 - y) ** 2
            signal = _leave_one_out_signal(events=bucket_events, holdout=event)
            if signal is None:
                continue
            adjusted, meta = blend_with_policy(
                base_probability=p0,
                hive_signal=signal,
                policy=policy,
                bucket_key=_bucket_key_from_event(event),
            )
            p1 = float(adjusted if adjusted is not None else p0)
            hive_err = (p1 - y) ** 2
            base_sq += base_err
            hive_sq += hive_err
            n += 1
            if meta.get("used") and hive_err < base_err - 1e-12:
                helps += 1
            elif meta.get("used") and hive_err > base_err + 1e-12:
                hurts += 1

    if n <= 0:
        return {
            "n": 0,
            "brier": None,
            "base_brier": None,
            "helps": 0,
            "hurts": 0,
            "reason": "no_scorable_rows",
        }

    return {
        "n": n,
        "brier": round(hive_sq / n, 8),
        "base_brier": round(base_sq / n, 8),
        "helps": helps,
        "hurts": hurts,
        "reason": "ok",
    }


def _worst_bucket_key(db: Session, sport: str | None = None) -> str | None:
    """Bucket where Hive would hurt most under current defaults (shadow)."""
    policy = default_policy()
    q = db.query(HiveAggregate).filter(HiveAggregate.eligible_samples > 0)
    if sport:
        q = q.filter(HiveAggregate.sport == _norm(sport))
    aggs = q.all()
    worst_key = None
    worst_delta = 0.0
    for agg in aggs:
        if int(agg.eligible_samples or 0) < policy.min_sample:
            continue
        if agg.calibration_delta is None:
            continue
        # Large |delta| with poor win rate relative to prediction = candidate inhibit
        hurt = abs(float(agg.calibration_delta))
        if hurt > worst_delta:
            worst_delta = hurt
            worst_key = agg.bucket_key
    return worst_key


def generate_policy_ideas(
    *,
    db: Session,
    base: HivePolicy,
    sport: str | None = None,
) -> list[tuple[str, HivePolicy]]:
    """Bounded idea menu — Hive invents variants within constitutional limits."""
    base = base.clamped()
    ideas: list[tuple[str, HivePolicy]] = []

    ideas.append(
        (
            "tighten_shift_bound",
            HivePolicy(
                max_probability_shift=base.max_probability_shift - 0.005,
                min_sample=base.min_sample,
                shift_scale=base.shift_scale,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )
    ideas.append(
        (
            "loosen_shift_bound",
            HivePolicy(
                max_probability_shift=base.max_probability_shift + 0.005,
                min_sample=base.min_sample,
                shift_scale=base.shift_scale,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )
    ideas.append(
        (
            "raise_min_sample",
            HivePolicy(
                max_probability_shift=base.max_probability_shift,
                min_sample=base.min_sample + 10,
                shift_scale=base.shift_scale,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )
    ideas.append(
        (
            "lower_min_sample",
            HivePolicy(
                max_probability_shift=base.max_probability_shift,
                min_sample=base.min_sample - 5,
                shift_scale=base.shift_scale,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )
    ideas.append(
        (
            "more_conservative_scale",
            HivePolicy(
                max_probability_shift=base.max_probability_shift,
                min_sample=base.min_sample,
                shift_scale=base.shift_scale * 0.85,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )
    ideas.append(
        (
            "more_aggressive_scale",
            HivePolicy(
                max_probability_shift=base.max_probability_shift,
                min_sample=base.min_sample,
                shift_scale=base.shift_scale * 1.15,
                inhibited_bucket_keys=base.inhibited_bucket_keys,
            ).clamped(),
        )
    )

    worst = _worst_bucket_key(db, sport=sport)
    if worst and worst not in base.inhibited_bucket_keys:
        ideas.append(
            (
                "inhibit_worst_bucket",
                HivePolicy(
                    max_probability_shift=base.max_probability_shift,
                    min_sample=base.min_sample,
                    shift_scale=base.shift_scale,
                    inhibited_bucket_keys=base.inhibited_bucket_keys + (worst,),
                ).clamped(),
            )
        )
    if base.inhibited_bucket_keys:
        ideas.append(
            (
                "clear_inhibits",
                HivePolicy(
                    max_probability_shift=base.max_probability_shift,
                    min_sample=base.min_sample,
                    shift_scale=base.shift_scale,
                    inhibited_bucket_keys=(),
                ).clamped(),
            )
        )

    # Deduplicate by policy dict
    seen: set[str] = set()
    unique: list[tuple[str, HivePolicy]] = []
    for name, policy in ideas:
        key = str(policy.to_dict())
        if key in seen or policy.to_dict() == base.to_dict():
            continue
        seen.add(key)
        unique.append((name, policy))
    return unique


def run_self_improvement_cycle(
    *,
    db: Session,
    sport: str | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    """One reflection cycle: invent ideas → simulate on history → promote if better."""
    if not settings.enabled:
        return {"ran": False, "reason": "hive_disabled"}

    current = get_active_policy(db=db)
    baseline = score_policy_on_history(db=db, policy=current, sport=sport)
    if baseline.get("brier") is None:
        return {
            "ran": False,
            "reason": baseline.get("reason") or "insufficient_history",
            "baseline": baseline,
            "active_policy": current.to_dict(),
        }

    ideas = generate_policy_ideas(db=db, base=current, sport=sport)
    trials: list[dict[str, Any]] = []
    best_name = "current"
    best_policy = current
    best_score = float(baseline["brier"])

    for name, policy in ideas:
        scored = score_policy_on_history(db=db, policy=policy, sport=sport)
        trial = {
            "idea": name,
            "policy": policy.to_dict(),
            "score": scored,
        }
        trials.append(trial)
        brier = scored.get("brier")
        if brier is None:
            continue
        if float(brier) < best_score - PROMOTE_EPSILON:
            best_score = float(brier)
            best_policy = policy
            best_name = name

    promoted = best_name != "current"
    explanation = (
        f"Tried {len(trials)} ideas against settled history. "
        + (
            f"Promoted '{best_name}' (Brier {baseline['brier']} → {best_score})."
            if promoted
            else f"Kept current policy (best challenger did not beat baseline {baseline['brier']} by ε={PROMOTE_EPSILON})."
        )
    )

    if promoted:
        save_active_policy(
            db=db,
            policy=best_policy,
            notes=f"self_improve:{best_name}:{trigger}",
        )

    cycle = HiveModelSnapshot(
        release_version=f"hive-cycle-{uuid4().hex[:12]}",
        snapshot_type=CYCLE_SNAPSHOT_TYPE,
        parameters={
            "trigger": trigger,
            "sport": sport,
            "baseline": baseline,
            "trials": trials,
            "promoted": promoted,
            "winner": best_name,
            "active_policy_after": best_policy.to_dict() if promoted else current.to_dict(),
            "explanation": explanation,
        },
        sample_count=int(baseline.get("n") or 0),
        notes=explanation,
    )
    db.add(cycle)
    db.flush()

    return {
        "ran": True,
        "cycle_id": cycle.id,
        "promoted": promoted,
        "winner": best_name,
        "explanation": explanation,
        "baseline": baseline,
        "trials": trials,
        "active_policy": get_active_policy(db=db).to_dict(),
    }


def list_self_improvement_cycles(
    *,
    db: Session,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = (
        db.query(HiveModelSnapshot)
        .filter(HiveModelSnapshot.snapshot_type == CYCLE_SNAPSHOT_TYPE)
        .order_by(HiveModelSnapshot.created_at.desc())
        .limit(max(1, min(100, limit)))
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        params = row.parameters if isinstance(row.parameters, dict) else {}
        out.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "sample_count": row.sample_count,
                "explanation": row.notes or params.get("explanation"),
                "promoted": params.get("promoted"),
                "winner": params.get("winner"),
                "baseline": params.get("baseline"),
                "active_policy_after": params.get("active_policy_after"),
                "trial_count": len(params.get("trials") or []),
            }
        )
    return out
