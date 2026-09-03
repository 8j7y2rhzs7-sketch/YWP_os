from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    LearningEvent,
    ModelWeight,
    Recommendation,
    Result,
    Ticket,
    TicketLeg,
    WeightChangeProposal,
)
from app.schemas import MissByOneOut, PatternOut, PerformanceOut


def performance(db: Session, user_id: str) -> PerformanceOut:
    rows = db.execute(
        select(Result, Recommendation)
        .join(Recommendation)
        .where(Recommendation.created_by_user_id == user_id)
    ).all()
    settled = len(rows)
    wins = sum(1 for result, _ in rows if result.outcome == "WIN")
    losses = sum(1 for result, _ in rows if result.outcome == "LOSS")
    pushes = sum(1 for result, _ in rows if result.outcome in {"PUSH", "VOID"})
    profit_loss = sum((result.profit_loss for result, _ in rows), start=Decimal("0.00"))
    wagered = sum(
        (result.stake for result, _ in rows if result.outcome in {"WIN", "LOSS", "PUSH"}),
        start=Decimal("0.00"),
    )

    by_sport: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"settled": 0, "wins": 0, "profit_loss": Decimal("0")}
    )
    by_market: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"settled": 0, "wins": 0, "profit_loss": Decimal("0")}
    )
    calibration: dict[str, dict[str, int]] = defaultdict(lambda: {"settled": 0, "wins": 0})

    for result, recommendation in rows:
        for bucket, key in (
            (by_sport, recommendation.sport),
            (by_market, recommendation.market_type),
        ):
            bucket[key]["settled"] += 1
            bucket[key]["wins"] += int(result.outcome == "WIN")
            bucket[key]["profit_loss"] += result.profit_loss
        lower = recommendation.confidence_score // 5 * 5
        label = f"{lower}-{min(100, lower + 4)}"
        calibration[label]["settled"] += 1
        calibration[label]["wins"] += int(result.outcome == "WIN")

    def summarize(groups: dict[str, dict[str, Any]], label: str) -> list[dict[str, Any]]:
        output = []
        for key, values in sorted(groups.items()):
            count = values["settled"]
            output.append(
                {
                    label: key,
                    **values,
                    "win_rate": round(values["wins"] / count, 4) if count else None,
                }
            )
        return output

    calibration_rows = [
        {
            "confidence_band": band,
            **values,
            "observed_win_rate": round(values["wins"] / values["settled"], 4),
        }
        for band, values in sorted(calibration.items())
    ]
    return PerformanceOut(
        settled=settled,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=round(wins / (wins + losses), 4) if wins + losses else None,
        profit_loss=profit_loss,
        roi=round(float(profit_loss / wagered), 4) if wagered else None,
        by_sport=summarize(by_sport, "sport"),
        by_market=summarize(by_market, "market_type"),
        confidence_calibration=calibration_rows,
    )


def patterns(db: Session, user_id: str) -> PatternOut:
    results = db.scalars(
        select(Result).join(Recommendation).where(Recommendation.created_by_user_id == user_id)
    ).all()
    root_causes = Counter(tag for result in results for tag in result.root_cause_tags)

    loss_rows = db.execute(
        select(Result, Recommendation)
        .join(Recommendation)
        .where(
            Result.outcome == "LOSS",
            Recommendation.created_by_user_id == user_id,
        )
    ).all()
    theses: dict[str, list[str]] = defaultdict(list)
    for _result, recommendation in loss_rows:
        theses[recommendation.thesis_key].append(recommendation.id)

    events = db.scalars(
        select(LearningEvent)
        .join(
            Recommendation,
            Recommendation.id == LearningEvent.recommendation_id,
            isouter=True,
        )
        .where(Recommendation.created_by_user_id == user_id)
        .order_by(LearningEvent.created_at.desc())
        .limit(20)
    ).all()
    return PatternOut(
        root_cause_tags=[{"tag": tag, "count": count} for tag, count in root_causes.most_common()],
        duplicate_thesis_losses=[
            {"thesis_key": thesis, "loss_count": len(ids), "recommendation_ids": ids}
            for thesis, ids in theses.items()
            if len(ids) > 1
        ],
        recent_learning_events=[
            {
                "event_type": event.event_type,
                "sport": event.sport,
                "market_type": event.market_type,
                "analysis": event.analysis,
                "created_at": event.created_at,
            }
            for event in events
        ],
    )


def miss_by_one_report(db: Session, user_id: str) -> MissByOneOut:
    rows = db.execute(
        select(Result, Recommendation)
        .join(Recommendation)
        .where(
            Result.outcome == "LOSS",
            Result.miss_distance.is_not(None),
            Recommendation.created_by_user_id == user_id,
        )
    ).all()
    near = [
        (result, recommendation)
        for result, recommendation in rows
        if result.miss_distance is not None and abs(result.miss_distance) <= Decimal("1.000")
    ]

    def group(key_name: str, key_fn: Any) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"near_misses": 0, "ticket_killers": 0, "last_leg_misses": 0}
        )
        for result, recommendation in near:
            key = key_fn(recommendation) or "unknown"
            grouped[key]["near_misses"] += 1
            grouped[key]["ticket_killers"] += int(result.killed_ticket)
            grouped[key]["last_leg_misses"] += int(result.last_losing_leg)
        return [{key_name: key, **value} for key, value in sorted(grouped.items())]

    thesis_counter = Counter(
        recommendation.thesis_key for _, recommendation in near if recommendation.thesis_key
    )
    near_ids = {recommendation.id for _, recommendation in near}
    cards_by_recommendation: dict[str, set[str]] = defaultdict(set)
    if near_ids:
        card_rows = db.execute(
            select(TicketLeg.recommendation_id, Ticket.ticket_type)
            .join(Ticket, Ticket.id == TicketLeg.ticket_id)
            .where(
                TicketLeg.recommendation_id.in_(near_ids),
                Ticket.user_id == user_id,
            )
        ).all()
        for recommendation_id, ticket_type in card_rows:
            cards_by_recommendation[recommendation_id].add(ticket_type)

    card_groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {"near_misses": 0, "ticket_killers": 0, "last_leg_misses": 0}
    )
    for result, recommendation in near:
        card_types = cards_by_recommendation.get(recommendation.id) or {"unassigned"}
        for card_type in card_types:
            card_groups[card_type]["near_misses"] += 1
            card_groups[card_type]["ticket_killers"] += int(result.killed_ticket)
            card_groups[card_type]["last_leg_misses"] += int(result.last_losing_leg)

    return MissByOneOut(
        near_miss_results=len(near),
        tickets_killed_by_near_miss=sum(int(result.killed_ticket) for result, _ in near),
        last_leg_near_misses=sum(int(result.last_losing_leg) for result, _ in near),
        by_sport=group("sport", lambda recommendation: recommendation.sport),
        by_market=group("market_type", lambda recommendation: recommendation.market_type),
        by_player=group("player_key", lambda recommendation: recommendation.player_key),
        by_line=group(
            "line",
            lambda recommendation: (
                str(recommendation.line) if recommendation.line is not None else "no_line"
            ),
        ),
        by_role=group(
            "role",
            lambda recommendation: (
                recommendation.snapshot.get("role")
                or (
                    "stable"
                    if float(
                        recommendation.snapshot.get("role_stability", recommendation.stability)
                    )
                    >= 0.75
                    else "unstable"
                )
            ),
        ),
        by_script=group("script_key", lambda recommendation: recommendation.script_key),
        by_card_type=[
            {"card_type": card_type, **values} for card_type, values in sorted(card_groups.items())
        ],
        recurring_theses=[
            {"thesis_key": thesis, "near_miss_count": count}
            for thesis, count in thesis_counter.most_common()
            if count > 1
        ],
    )


ERROR_FEATURE_MAP = {
    "BAD_DATA": "data_quality",
    "BAD_WEIGHTING": "probability_weighting",
    "BAD_SCRIPT": "script_alignment",
    "BAD_TIMING": "timing",
    "BAD_PRICE": "market_value",
    "ROLE_WORKLOAD": "role_stability",
    "INJURY_AVAILABILITY": "availability",
    "CORRELATION_EXPOSURE": "correlation_penalty",
    "LINE_ESCALATION": "cushion",
}


def propose_weight_changes(db: Session) -> list[WeightChangeProposal]:
    """Create reviewable proposals only after adequate, repeated evidence."""
    rows = db.execute(select(Result, Recommendation).join(Recommendation)).all()
    segments: dict[tuple[str, str], list[tuple[Result, Recommendation]]] = defaultdict(list)
    for result, recommendation in rows:
        segments[(recommendation.sport, recommendation.market_type)].append(
            (result, recommendation)
        )

    proposals: list[WeightChangeProposal] = []
    for (sport, market), segment_rows in segments.items():
        if len(segment_rows) < settings.learning_min_sample_size:
            continue
        error_counts = Counter(
            result.error_category
            for result, _ in segment_rows
            if result.outcome == "LOSS" and result.error_category in ERROR_FEATURE_MAP
        )
        for error_category, count in error_counts.items():
            if count < settings.learning_min_repeated_pattern:
                continue
            feature = ERROR_FEATURE_MAP[error_category]
            pending = db.scalar(
                select(WeightChangeProposal).where(
                    WeightChangeProposal.sport == sport,
                    WeightChangeProposal.market_type == market,
                    WeightChangeProposal.feature_name == feature,
                    WeightChangeProposal.status == "pending",
                )
            )
            if pending:
                proposals.append(pending)
                continue
            current = db.scalar(
                select(ModelWeight)
                .where(
                    ModelWeight.sport == sport,
                    ModelWeight.market_type == market,
                    ModelWeight.feature_name == feature,
                    ModelWeight.is_active.is_(True),
                )
                .order_by(ModelWeight.version.desc())
            )
            current_weight = current.weight if current else Decimal("0.100000")
            error_rate = count / len(segment_rows)
            delta = min(settings.learning_max_weight_delta, max(0.005, error_rate * 0.03))
            proposed_weight = max(Decimal("0"), current_weight - Decimal(str(delta)))
            proposal = WeightChangeProposal(
                sport=sport,
                market_type=market,
                feature_name=feature,
                current_weight=current_weight,
                proposed_weight=proposed_weight,
                sample_size=len(segment_rows),
                repeated_pattern_count=count,
                evidence={
                    "error_category": error_category,
                    "error_rate": round(error_rate, 4),
                    "guardrail": "bounded_decrease_only",
                },
                reason=(
                    f"{error_category} repeated {count} times in {len(segment_rows)} settled "
                    f"{sport}/{market} recommendations. Human review required."
                ),
            )
            db.add(proposal)
            proposals.append(proposal)
    db.commit()
    for proposal in proposals:
        db.refresh(proposal)
    return proposals


def review_weight_proposal(
    db: Session,
    proposal: WeightChangeProposal,
    *,
    approve: bool,
    reviewer_user_id: str,
    note: str | None = None,
) -> WeightChangeProposal:
    if proposal.status != "pending":
        raise ValueError("Only pending proposals can be reviewed")
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.now(UTC)
    if not approve:
        proposal.status = "rejected"
        if note:
            proposal.evidence = {**proposal.evidence, "review_note": note}
        db.commit()
        db.refresh(proposal)
        return proposal

    active = db.scalar(
        select(ModelWeight)
        .where(
            ModelWeight.sport == proposal.sport,
            ModelWeight.market_type == proposal.market_type,
            ModelWeight.feature_name == proposal.feature_name,
            ModelWeight.is_active.is_(True),
        )
        .order_by(ModelWeight.version.desc())
    )
    next_version = 1
    if active:
        active.is_active = False
        next_version = active.version + 1
    weight = ModelWeight(
        sport=proposal.sport,
        market_type=proposal.market_type,
        feature_name=proposal.feature_name,
        weight=proposal.proposed_weight,
        version=next_version,
        sample_size=proposal.sample_size,
        is_active=True,
        source_proposal_id=proposal.id,
    )
    db.add(weight)
    db.flush()
    proposal.status = "applied"
    proposal.applied_weight_id = weight.id
    if note:
        proposal.evidence = {**proposal.evidence, "review_note": note}
    db.commit()
    db.refresh(proposal)
    return proposal


def rollback_weight_proposal(
    db: Session, proposal: WeightChangeProposal, reviewer_user_id: str
) -> WeightChangeProposal:
    if proposal.status != "applied" or not proposal.applied_weight_id:
        raise ValueError("Only an applied proposal can be rolled back")
    applied = db.get(ModelWeight, proposal.applied_weight_id)
    if not applied or not applied.is_active:
        raise ValueError("Applied weight is no longer active")
    applied.is_active = False
    rollback = ModelWeight(
        sport=proposal.sport,
        market_type=proposal.market_type,
        feature_name=proposal.feature_name,
        weight=proposal.current_weight,
        version=applied.version + 1,
        sample_size=proposal.sample_size,
        is_active=True,
        source_proposal_id=proposal.id,
    )
    db.add(rollback)
    proposal.status = "rolled_back"
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(proposal)
    return proposal


def load_feature_weights(db: Session, sport: str, market_type: str) -> dict[str, float]:
    rows = db.scalars(
        select(ModelWeight).where(
            ModelWeight.sport == sport,
            ModelWeight.market_type == market_type,
            ModelWeight.is_active.is_(True),
        )
    ).all()
    return {row.feature_name: float(row.weight) for row in rows}


def record_usage_event(
    db: Session,
    *,
    event_type: str,
    sport: str | None,
    market_type: str | None = None,
    recommendation_id: str | None = None,
    analysis: dict[str, Any] | None = None,
) -> None:
    db.add(
        LearningEvent(
            recommendation_id=recommendation_id,
            event_type=event_type,
            sport=sport,
            market_type=market_type,
            analysis=analysis or {},
        )
    )


def apply_micro_learning(db: Session, result: Result, recommendation: Recommendation) -> None:
    """Every graded result trains a tiny, bounded weight shift immediately."""
    feature = ERROR_FEATURE_MAP.get(result.error_category or "", "market_value")
    if result.outcome == "WIN":
        delta = settings.learning_micro_delta
        if result.process_grade in {"A", "B"}:
            delta *= 1.25
    elif result.outcome == "LOSS":
        delta = -settings.learning_micro_delta
        if result.error_category in ERROR_FEATURE_MAP:
            delta *= 1.5
    else:
        record_usage_event(
            db,
            event_type="RESULT_NEUTRAL",
            sport=recommendation.sport,
            market_type=recommendation.market_type,
            recommendation_id=recommendation.id,
            analysis={"outcome": result.outcome, "lesson": result.lesson},
        )
        return

    active = db.scalar(
        select(ModelWeight)
        .where(
            ModelWeight.sport == recommendation.sport,
            ModelWeight.market_type == recommendation.market_type,
            ModelWeight.feature_name == feature,
            ModelWeight.is_active.is_(True),
        )
        .order_by(ModelWeight.version.desc())
    )
    current = float(active.weight) if active else 0.10
    next_weight = min(
        settings.learning_weight_ceiling,
        max(settings.learning_weight_floor, current + delta),
    )
    if abs(next_weight - current) < 0.0001:
        return
    if active:
        active.is_active = False
        next_version = active.version + 1
        sample = active.sample_size + 1
    else:
        next_version = 1
        sample = 1
    db.add(
        ModelWeight(
            sport=recommendation.sport,
            market_type=recommendation.market_type,
            feature_name=feature,
            weight=Decimal(str(round(next_weight, 6))),
            version=next_version,
            sample_size=sample,
            is_active=True,
        )
    )
    record_usage_event(
        db,
        event_type="MICRO_WEIGHT_APPLIED",
        sport=recommendation.sport,
        market_type=recommendation.market_type,
        recommendation_id=recommendation.id,
        analysis={
            "feature": feature,
            "from": current,
            "to": next_weight,
            "delta": delta,
            "outcome": result.outcome,
            "error_category": result.error_category,
            "lesson": result.lesson,
        },
    )


def learning_pulse(db: Session, user_id: str) -> dict[str, Any]:
    rows = db.execute(
        select(LearningEvent, Recommendation)
        .join(
            Recommendation,
            Recommendation.id == LearningEvent.recommendation_id,
            isouter=True,
        )
    ).all()
    events = [
        event
        for event, recommendation in rows
        if (recommendation is not None and recommendation.created_by_user_id == user_id)
        or (
            event.recommendation_id is None
            and (event.analysis or {}).get("user_id") == user_id
        )
    ]
    protocol_runs = sum(1 for event in events if event.event_type == "PROTOCOL_RUN")
    graded = sum(1 for event in events if event.event_type == "RESULT_GRADED")
    micros = [event for event in events if event.event_type == "MICRO_WEIGHT_APPLIED"]
    weights = list(db.scalars(select(ModelWeight).where(ModelWeight.is_active.is_(True))).all())
    latest = None
    if micros:
        latest_event = max(micros, key=lambda item: item.created_at)
        latest = str((latest_event.analysis or {}).get("lesson") or latest_event.event_type)
    if graded or protocol_runs:
        headline = (
            f"Trained on {graded} grades and {protocol_runs} protocol runs. "
            f"{len(micros)} live weight shifts are already in the engine."
        )
    else:
        headline = "No training yet. Grade a result or run a slate — every use teaches it."
    return {
        "protocol_runs": protocol_runs,
        "graded_results": graded,
        "micro_updates": len(micros),
        "active_shifts": [
            {
                "sport": row.sport,
                "market_type": row.market_type,
                "feature_name": row.feature_name,
                "weight": float(row.weight),
                "version": row.version,
                "sample_size": row.sample_size,
            }
            for row in weights
        ],
        "latest_lesson": latest,
        "headline": headline,
    }
