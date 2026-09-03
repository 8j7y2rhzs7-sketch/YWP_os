from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import BankrollAccount, LockCheck, Ticket, TicketLeg
from app.schemas import CurrentStateUpdate, LockCheckRequest
from app.services.decision_engine import implied_probability, input_hash
from app.services.ticket_gates import (
    cash_card_k_overs_ok,
    game_status_ok,
    market_status_ok,
    model_edge_quarantine,
    snapshot_game_status,
    snapshot_market_status,
)

STATUS_PRIORITY = {"LOCKED": 0, "WARNING": 1, "CHANGE_REQUIRED": 2, "SKIP": 3}


def _raise_status(current: str, proposed: str) -> str:
    return proposed if STATUS_PRIORITY[proposed] > STATUS_PRIORITY[current] else current


def run_lock_check(
    db: Session,
    ticket: Ticket,
    user_id: str,
    request: LockCheckRequest,
) -> LockCheck:
    now = datetime.now(UTC)
    updates = {item.recommendation_id: item for item in request.updates}
    status = "LOCKED"
    warnings: list[str] = []
    leg_results: list[dict[str, Any]] = []
    checks: dict[str, str] = {
        "starters": "PASS",
        "lineups": "PASS",
        "odds_movement": "PASS",
        "weather": "PASS",
        "injuries": "PASS",
        "market_availability": "PASS",
        "data_quality": "PASS",
        "correlation": "PASS",
        "thesis_exposure": "PASS",
        "bankroll": "PASS",
    }

    active_actions = {"follow", "replace"}
    thesis_counts = Counter(leg.thesis_key for leg in ticket.legs if leg.action in active_actions)
    if any(count > 1 for count in thesis_counts.values()):
        checks["thesis_exposure"] = "FAIL"
        warnings.append("The same thesis appears more than once on this ticket.")
        status = _raise_status(status, "SKIP")

    script_counts = Counter(leg.script_key for leg in ticket.legs if leg.action in active_actions)
    if any(count > 1 for count in script_counts.values()) and not (
        ticket.intentional_correlation or request.acknowledge_correlation
    ):
        checks["correlation"] = "FAIL"
        warnings.append("Multiple legs rely on the same game script without explicit intent.")
        status = _raise_status(status, "CHANGE_REQUIRED")

    other_active_theses = set(
        db.scalars(
            select(TicketLeg.thesis_key)
            .join(Ticket)
            .where(
                Ticket.user_id == user_id,
                Ticket.id != ticket.id,
                Ticket.status.in_(["draft", "locked", "placed"]),
                TicketLeg.action.in_(active_actions),
            )
        ).all()
    )
    repeated = set(thesis_counts).intersection(other_active_theses)
    if repeated and not (request.intentional_thesis_exposure or ticket.intentional_thesis_exposure):
        checks["thesis_exposure"] = "FAIL"
        warnings.append("Cross-ticket thesis exposure detected: " + ", ".join(sorted(repeated)))
        status = _raise_status(status, "CHANGE_REQUIRED")

    bankroll = db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == user_id))
    if bankroll and bankroll.balance > 0:
        cap = bankroll.balance * bankroll.max_stake_pct
        if ticket.stake > cap and not ticket.override_acknowledged:
            checks["bankroll"] = "FAIL"
            warnings.append(f"Stake exceeds the configured per-ticket cap of {cap:.2f}.")
            status = _raise_status(status, "SKIP")

    active_recs = [
        leg.recommendation for leg in ticket.legs if leg.action in active_actions
    ]
    if not cash_card_k_overs_ok(ticket.ticket_type, active_recs):
        checks["correlation"] = "FAIL"
        warnings.append("Cash cards cannot include more than one pitcher strikeout over.")
        status = _raise_status(status, "SKIP")

    for leg in ticket.legs:
        recommendation = leg.recommendation
        leg_status = "LOCKED"
        changes: list[str] = []
        update: CurrentStateUpdate | None = updates.get(recommendation.id)
        snapshot = recommendation.snapshot

        if leg.action not in active_actions:
            leg_results.append(
                {
                    "recommendation_id": recommendation.id,
                    "selection": recommendation.selection,
                    "status": "IGNORED",
                    "changes_detected": [f"Leg action is {leg.action}."],
                }
            )
            continue

        is_demo = recommendation.data_source == "YWP_DEMO_PROVIDER"
        game_status = snapshot_game_status(snapshot)
        market_status = snapshot_market_status(snapshot)
        if update is not None:
            if update.game_status:
                game_status = update.game_status
            if update.market_status:
                market_status = update.market_status
            if not update.market_available:
                market_status = "CLOSED"

        if not game_status_ok(game_status):
            changes.append(f"Game status is {game_status}; only PRE_GAME is eligible.")
            leg_status = "SKIP"
            checks["market_availability"] = "FAIL"
        if not market_status_ok(market_status):
            changes.append(f"Market status is {market_status}; only OPEN is eligible.")
            leg_status = "SKIP"
            checks["market_availability"] = "FAIL"
        if model_edge_quarantine(float(recommendation.edge)):
            changes.append("Model edge exceeds 15 percentage points; quarantined for review.")
            leg_status = "SKIP"
            checks["data_quality"] = "FAIL"
        if "DATA_ANOMALY" in (recommendation.reason_codes or []):
            changes.append("DATA_ANOMALY remains on this recommendation.")
            leg_status = "SKIP"
            checks["data_quality"] = "FAIL"

        if update is None and not is_demo:
            changes.append("No fresh provider snapshot was supplied.")
            leg_status = "SKIP"
            checks["data_quality"] = "FAIL"
        elif update is not None:
            age = max(0, (now - update.source_timestamp).total_seconds())
            if age > settings.lock_check_ttl_seconds:
                changes.append("Current snapshot is older than the Lock Check window.")
                leg_status = _raise_status(leg_status, "WARNING")
                checks["data_quality"] = "WARNING"

            if not update.market_available:
                changes.append("Market is no longer available.")
                leg_status = "SKIP"
                checks["market_availability"] = "FAIL"
            if update.starter_changed:
                changes.append("Starter/pitcher changed.")
                leg_status = _raise_status(leg_status, "CHANGE_REQUIRED")
                checks["starters"] = "FAIL"
            if update.lineup_changed:
                changes.append("Material lineup change detected.")
                leg_status = _raise_status(leg_status, "CHANGE_REQUIRED")
                checks["lineups"] = "FAIL"
            if update.key_injury_change:
                changes.append("Key injury or availability change detected.")
                leg_status = _raise_status(leg_status, "CHANGE_REQUIRED")
                checks["injuries"] = "FAIL"
            if update.severe_weather_change:
                changes.append("Severe weather/venue change affects the thesis.")
                leg_status = _raise_status(leg_status, "CHANGE_REQUIRED")
                checks["weather"] = "FAIL"

            if update.current_odds is not None:
                movement = abs(
                    implied_probability(update.current_odds)
                    - implied_probability(recommendation.american_odds)
                )
                if movement >= settings.odds_blocking_move_probability_points:
                    changes.append("Price moved beyond the blocking threshold.")
                    leg_status = _raise_status(leg_status, "CHANGE_REQUIRED")
                    checks["odds_movement"] = "FAIL"
                elif movement >= settings.odds_warning_move_probability_points:
                    changes.append("Price moved beyond the warning threshold.")
                    leg_status = _raise_status(leg_status, "WARNING")
                    checks["odds_movement"] = "WARNING"

            if (
                update.data_quality is not None
                and update.data_quality < settings.minimum_data_quality
            ):
                changes.append("Current data quality is below the YWP minimum.")
                leg_status = "SKIP"
                checks["data_quality"] = "FAIL"

            is_k_over = bool(snapshot.get("market_is_pitcher_strikeout_over"))
            first_start = (
                update.first_start_back
                if update.first_start_back is not None
                else bool(snapshot.get("first_start_back"))
            )
            normal_workload = (
                update.normal_workload_confirmed
                if update.normal_workload_confirmed is not None
                else bool(snapshot.get("normal_workload_confirmed"))
            )
            duration_verified = (
                update.k_duration_verified
                if update.k_duration_verified is not None
                else bool(snapshot.get("k_duration_verified", True))
            )
            if is_k_over and first_start and not normal_workload:
                changes.append("First-start-back strikeout-over exclusion is active.")
                leg_status = "SKIP"
                checks["starters"] = "FAIL"
            if is_k_over and not duration_verified:
                changes.append("Pitcher strikeout duration gate is not verified.")
                leg_status = "SKIP"
                checks["starters"] = "FAIL"

            bullpen_verified = (
                update.bullpen_verified
                if update.bullpen_verified is not None
                else bool(snapshot.get("bullpen_verified", True))
            )
            if snapshot.get("bullpen_game") and not bullpen_verified:
                changes.append("Bullpen-game sequencing remains unverified.")
                leg_status = _raise_status(leg_status, "WARNING")

            changes.extend(update.notes)

        if not changes:
            changes.append("No material changes detected.")

        status = _raise_status(status, leg_status)
        leg_results.append(
            {
                "recommendation_id": recommendation.id,
                "selection": recommendation.selection,
                "status": leg_status,
                "confidence_score": recommendation.confidence_score,
                "changes_detected": changes,
            }
        )

    messages = {
        "LOCKED": (
            "PLACE_TICKET",
            "No material changes. Proceed only if the user accepts the stated risk.",
        ),
        "WARNING": (
            "REVIEW_WARNING",
            "Minor concern detected. Review every warning before placement.",
        ),
        "CHANGE_REQUIRED": (
            "CHANGE_OR_REMOVE",
            "A material change or structure problem must be resolved.",
        ),
        "SKIP": (
            "DO_NOT_PLACE",
            "The ticket no longer meets YWP requirements. Official output: SKIP.",
        ),
    }
    action, message = messages[status]
    penalty = sum(1 for result in leg_results if result["status"] == "WARNING") * 3
    penalty += sum(1 for result in leg_results if result["status"] == "CHANGE_REQUIRED") * 8
    penalty += sum(1 for result in leg_results if result["status"] == "SKIP") * 15
    ticket_confidence = max(0, ticket.confidence_score - penalty)
    expires_at = now + timedelta(seconds=settings.lock_check_ttl_seconds)
    hash_payload = {
        "ticket_id": ticket.id,
        "updates": [item.model_dump(mode="json") for item in request.updates],
        "checks": checks,
        "status": status,
        "timestamp": now.isoformat(),
    }
    record = LockCheck(
        ticket_id=ticket.id,
        user_id=user_id,
        lock_status=status,
        ticket_confidence_score=ticket_confidence,
        recommended_action=action,
        overall_message=message,
        checks=checks,
        warnings=list(dict.fromkeys(warnings)),
        leg_results=leg_results,
        input_hash=input_hash(hash_payload),
        expires_at=expires_at,
    )
    db.add(record)
    ticket.last_lock_status = status
    ticket.last_lock_expires_at = expires_at
    if status == "LOCKED":
        ticket.status = "locked"
    db.commit()
    db.refresh(record)
    return record


def load_ticket_for_lock(db: Session, ticket_id: str, user_id: str) -> Ticket | None:
    return db.scalar(
        select(Ticket)
        .options(selectinload(Ticket.legs).selectinload(TicketLeg.recommendation))
        .where(Ticket.id == ticket_id, Ticket.user_id == user_id)
    )
