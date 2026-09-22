"""Ops Heal evidence — collect movements from every app process.

Forward path: HTTP middleware records APP_PROCESS_MOVEMENT events.
Backward path: each Ops Heal cycle aggregates audits, learning events,
protocol runs, tickets, locks, settlement, Hive, and client errors into
one evidence pack that feeds improvement proposals.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

APP_PROCESS_MOVEMENT = "APP_PROCESS_MOVEMENT"
OPS_HEAL_EVIDENCE_TYPE = "ops_heal_evidence"

# Map API path → product process name (all major app surfaces).
PROCESS_ROUTE_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/api/v1/auth/"), "auth"),
    (re.compile(r"^/api/v1/users"), "profile"),
    (re.compile(r"^/api/v1/sports/catalog"), "sports_catalog"),
    (re.compile(r"^/api/v1/sports/prefetch"), "odds_prefetch"),
    (re.compile(r"^/api/v1/sports/slate"), "slate"),
    (re.compile(r"^/api/v1/sports/market-board"), "market_board"),
    (re.compile(r"^/api/v1/sports/day-forge"), "day_forge"),
    (re.compile(r"^/api/v1/sports/analyze"), "analyze"),
    (re.compile(r"^/api/v1/sports/build-ticket"), "decision_board"),
    (re.compile(r"^/api/v1/sports/preview-custom"), "custom_ticket"),
    (re.compile(r"^/api/v1/sports/settle-day"), "settle_day"),
    (re.compile(r"^/api/v1/sports/result"), "manual_result"),
    (re.compile(r"^/api/v1/sports/"), "sports"),
    (re.compile(r"^/api/v1/tickets/.*/lock"), "lock_check"),
    (re.compile(r"^/api/v1/tickets"), "tickets"),
    (re.compile(r"^/api/v1/learning"), "learning"),
    (re.compile(r"^/api/v1/protocol"), "protocol"),
    (re.compile(r"^/api/v1/hive"), "hive"),
    (re.compile(r"^/api/v1/ops-heal"), "ops_heal"),
    (re.compile(r"^/api/v1/errors"), "error_reports"),
    (re.compile(r"^/api/v1/whop"), "whop"),
    (re.compile(r"^/api/v1/"), "api_other"),
]

# Domain event_type / audit action → process
LEARNING_EVENT_PROCESS = {
    "DAY_FORGE": "day_forge",
    "PROTOCOL_RUN": "protocol",
    "TICKET_CREATED": "tickets",
    "TICKET_LEG_ADDED": "tickets",
    "TICKET_PLACED": "tickets",
    "RESULT_GRADED": "settlement",
    "RESULT_GRADED_MICRO_DISABLED": "learning",
    "RESULT_NEUTRAL": "settlement",
    "MICRO_WEIGHT_APPLIED": "learning",
    "MISS_BY_ONE": "learning",
    "ERROR_ANALYSIS": "learning",
    "SETTLEMENT_COVERAGE_GAP": "settlement",
    "EOD_QUALITY_PASS": "eod_quality",
    "EOD_MISSED_WINNER": "eod_quality",
    "EOD_FALSE_SKIP": "eod_quality",
    "EOD_GOOD_DODGE": "eod_quality",
    APP_PROCESS_MOVEMENT: "api_movement",
}

AUDIT_ACTION_PROCESS = {
    "USER_REGISTERED": "auth",
    "USER_PROFILE_UPDATED": "profile",
    "TICKET_CREATED": "tickets",
    "TICKET_LEG_CHANGED": "tickets",
    "TICKET_PLACED": "tickets",
    "TICKET_CANCELLED": "tickets",
    "error_report_submitted": "error_reports",
    "WEIGHT_PROPOSAL_REVIEWED": "learning",
    "WEIGHT_PROPOSAL_ROLLED_BACK": "learning",
    "OPS_HEAL_ACK_ERRORS": "ops_heal",
    "OPS_HEAL_PROPOSAL_IMPLEMENTED": "ops_heal",
    "OPS_HEAL_PROPOSAL_DISMISSED": "ops_heal",
    "WHOP_SUBSCRIPTION_ACTIVATED": "whop",
    "WHOP_SUBSCRIPTION_DEACTIVATED": "whop",
    "TESTER_PROVISIONED": "auth",
    "ADMIN_PROVISIONED": "auth",
}

ALL_PROCESSES = (
    "auth",
    "profile",
    "sports_catalog",
    "odds_prefetch",
    "slate",
    "market_board",
    "day_forge",
    "analyze",
    "decision_board",
    "custom_ticket",
    "protocol",
    "tickets",
    "lock_check",
    "settle_day",
    "settlement",
    "manual_result",
    "learning",
    "hive",
    "eod_quality",
    "error_reports",
    "ops_heal",
    "whop",
    "api_other",
    "api_movement",
)

_SKIP_PATH_RE = re.compile(
    r"^(?:/(?:docs|redoc|openapi\.json|favicon)|/api/v1/health|/experiences)(?:/|$)",
    re.I,
)

# Soft-dedupe noisy GET polls (day-forge / slate home polling).
_get_bucket_lock = Lock()
_get_buckets: dict[str, float] = {}
_GET_DEDUPE_SECONDS = 20.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def process_for_path(path: str) -> str:
    for pattern, name in PROCESS_ROUTE_MAP:
        if pattern.search(path):
            return name
    return "api_other"


def should_record_movement(*, method: str, path: str, status_code: int) -> bool:
    if not path.startswith("/api/v1"):
        return False
    if path.rstrip("/") == "/api/v1/health" or path.startswith("/api/v1/health/"):
        return False
    if _SKIP_PATH_RE.match(path):
        return False
    method_u = method.upper()
    if method_u in {"OPTIONS", "HEAD"}:
        return False
    # Always keep mutations and failures.
    if method_u != "GET" or status_code >= 400:
        return True
    # Dedupe successful GET polls so Home Day Forge polling does not flood.
    key = f"{method_u}:{path.split('?')[0]}:{status_code // 100}"
    now = time.monotonic()
    with _get_bucket_lock:
        last = _get_buckets.get(key)
        if last is not None and (now - last) < _GET_DEDUPE_SECONDS:
            return False
        _get_buckets[key] = now
        # Bound memory
        if len(_get_buckets) > 4000:
            cutoff = now - 120
            stale = [k for k, ts in _get_buckets.items() if ts < cutoff]
            for k in stale:
                _get_buckets.pop(k, None)
    return True


def record_app_movement(
    db: Session,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str | None = None,
) -> None:
    """Persist one API process movement (no auth secrets / bodies)."""
    from app.models import LearningEvent

    process = process_for_path(path)
    clean_path = path.split("?")[0][:180]
    db.add(
        LearningEvent(
            event_type=APP_PROCESS_MOVEMENT,
            sport=None,
            market_type=process,
            analysis={
                "process": process,
                "method": method.upper(),
                "path": clean_path,
                "status_code": int(status_code),
                "duration_ms": round(float(duration_ms), 1),
                "ok": int(status_code) < 400,
                "user_id": user_id,
                "source": "http_middleware",
            },
        )
    )


def collect_all_process_evidence(
    *,
    db: Session,
    user_id: str | None = None,
    hours: int = 72,
) -> dict[str, Any]:
    """Aggregate evidence across every major app process / movement stream."""
    from app.hive.models import HiveLearningEvent
    from app.models import (
        AuditLog,
        ErrorReport,
        LearningEvent,
        LockCheck,
        ProtocolRun,
        Recommendation,
        Result,
        Ticket,
    )

    since = _utcnow() - timedelta(hours=max(1, min(hours, 168)))
    process_counts: Counter[str] = Counter()
    process_errors: Counter[str] = Counter()
    streams: dict[str, Any] = {}

    # --- Forward API movements ---
    movements = list(
        db.scalars(
            select(LearningEvent)
            .where(
                LearningEvent.event_type == APP_PROCESS_MOVEMENT,
                LearningEvent.created_at >= since,
            )
            .order_by(LearningEvent.created_at.desc())
            .limit(800)
        ).all()
    )
    movement_rows = []
    for row in movements:
        analysis = row.analysis if isinstance(row.analysis, dict) else {}
        process = str(analysis.get("process") or row.market_type or "api_movement")
        process_counts[process] += 1
        if not analysis.get("ok", True):
            process_errors[process] += 1
        movement_rows.append(
            {
                "process": process,
                "method": analysis.get("method"),
                "path": analysis.get("path"),
                "status_code": analysis.get("status_code"),
                "duration_ms": analysis.get("duration_ms"),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    streams["api_movements"] = {
        "count": len(movement_rows),
        "recent": movement_rows[:40],
        "by_process": dict(Counter(r["process"] for r in movement_rows)),
        "failures": sum(1 for r in movement_rows if int(r.get("status_code") or 200) >= 400),
    }

    # --- Learning / usage events (all process types) ---
    learning_rows = list(
        db.scalars(
            select(LearningEvent)
            .where(
                LearningEvent.event_type != APP_PROCESS_MOVEMENT,
                LearningEvent.created_at >= since,
            )
            .order_by(LearningEvent.created_at.desc())
            .limit(500)
        ).all()
    )
    learning_by_type: Counter[str] = Counter()
    for row in learning_rows:
        learning_by_type[row.event_type] += 1
        process = LEARNING_EVENT_PROCESS.get(row.event_type, "learning")
        process_counts[process] += 1
    streams["learning_events"] = {
        "count": len(learning_rows),
        "by_type": dict(learning_by_type),
    }

    # --- Audit trail ---
    audit_q = select(AuditLog).where(AuditLog.created_at >= since)
    if user_id:
        audit_q = audit_q.where(
            (AuditLog.user_id == user_id) | (AuditLog.user_id.is_(None))
        )
    audits = list(
        db.scalars(audit_q.order_by(AuditLog.created_at.desc()).limit(400)).all()
    )
    audit_by_action: Counter[str] = Counter()
    for row in audits:
        audit_by_action[row.action] += 1
        process = AUDIT_ACTION_PROCESS.get(row.action, "api_other")
        process_counts[process] += 1
    streams["audits"] = {"count": len(audits), "by_action": dict(audit_by_action)}

    # --- Protocol runs ---
    protocols = list(
        db.scalars(
            select(ProtocolRun)
            .where(ProtocolRun.created_at >= since)
            .order_by(ProtocolRun.created_at.desc())
            .limit(200)
        ).all()
    )
    proto_status: Counter[str] = Counter()
    for row in protocols:
        proto_status[row.status] += 1
        process_counts["protocol"] += 1
        if str(row.status).lower() in {"fail", "failed", "error", "blocked"}:
            process_errors["protocol"] += 1
    streams["protocol_runs"] = {
        "count": len(protocols),
        "by_status": dict(proto_status),
        "by_sport": dict(Counter(r.sport for r in protocols)),
    }

    # --- Recommendations (board / analyze output) ---
    rec_count = int(
        db.scalar(
            select(func.count())
            .select_from(Recommendation)
            .where(Recommendation.created_at >= since)
        )
        or 0
    )
    process_counts["analyze"] += rec_count
    process_counts["decision_board"] += rec_count
    streams["recommendations"] = {"count": rec_count}

    # --- Tickets / lock checks / results ---
    ticket_q = select(Ticket).where(Ticket.created_at >= since)
    if user_id:
        ticket_q = ticket_q.where(Ticket.user_id == user_id)
    tickets = list(db.scalars(ticket_q.limit(300)).all())
    ticket_status = Counter(t.status for t in tickets)
    process_counts["tickets"] += len(tickets)
    streams["tickets"] = {
        "count": len(tickets),
        "by_status": dict(ticket_status),
        "settled": sum(1 for t in tickets if t.settled_outcome),
    }

    locks = list(
        db.scalars(
            select(LockCheck)
            .where(LockCheck.created_at >= since)
            .order_by(LockCheck.created_at.desc())
            .limit(200)
        ).all()
    )
    process_counts["lock_check"] += len(locks)
    streams["lock_checks"] = {
        "count": len(locks),
        "by_status": dict(Counter(l.lock_status for l in locks)),
    }

    results = list(
        db.scalars(
            select(Result)
            .where(Result.result_time >= since)
            .order_by(Result.result_time.desc())
            .limit(300)
        ).all()
    )
    process_counts["settlement"] += len(results)
    streams["results"] = {
        "count": len(results),
        "by_outcome": dict(Counter(r.outcome for r in results if r.outcome)),
    }

    # --- Hive ---
    hive_pending = int(
        db.scalar(
            select(func.count())
            .select_from(HiveLearningEvent)
            .where(
                HiveLearningEvent.outcome.is_(None),
                HiveLearningEvent.created_at >= since,
            )
        )
        or 0
    )
    hive_resolved = int(
        db.scalar(
            select(func.count())
            .select_from(HiveLearningEvent)
            .where(
                HiveLearningEvent.outcome.is_not(None),
                HiveLearningEvent.created_at >= since,
            )
        )
        or 0
    )
    process_counts["hive"] += hive_pending + hive_resolved
    streams["hive"] = {"pending": hive_pending, "resolved": hive_resolved}

    # --- Client errors ---
    errors = list(
        db.scalars(
            select(ErrorReport)
            .where(ErrorReport.created_at >= since)
            .order_by(ErrorReport.created_at.desc())
            .limit(200)
        ).all()
    )
    process_counts["error_reports"] += len(errors)
    process_errors["error_reports"] += sum(1 for e in errors if e.status == "open")
    streams["error_reports"] = {
        "count": len(errors),
        "open": sum(1 for e in errors if e.status == "open"),
        "by_screen": dict(Counter((e.screen or "unknown") for e in errors)),
        "by_category": dict(Counter(e.category for e in errors)),
    }

    coverage = []
    for name in ALL_PROCESSES:
        count = int(process_counts.get(name, 0))
        errs = int(process_errors.get(name, 0))
        coverage.append(
            {
                "process": name,
                "movements": count,
                "errors": errs,
                "active": count > 0,
                "error_rate": round(errs / count, 3) if count else 0.0,
            }
        )

    active = [c for c in coverage if c["active"]]
    quiet = [c["process"] for c in coverage if not c["active"]]
    hot_failures = sorted(
        [c for c in coverage if c["errors"] > 0],
        key=lambda c: (c["error_rate"], c["errors"]),
        reverse=True,
    )[:12]

    pack = {
        "id": str(uuid4()),
        "bot": "ops_heal",
        "kind": "process_evidence",
        "window_hours": hours,
        "since": since.isoformat(),
        "created_at": _utcnow().isoformat(),
        "user_id": user_id,
        "streams": streams,
        "process_coverage": coverage,
        "summary": {
            "processes_tracked": len(ALL_PROCESSES),
            "processes_active": len(active),
            "processes_quiet": quiet,
            "total_movements": int(sum(process_counts.values())),
            "total_errors": int(sum(process_errors.values())),
            "hot_failures": hot_failures,
        },
    }
    return pack


def persist_evidence_pack(*, db: Session, pack: dict[str, Any]) -> dict[str, Any]:
    from app.hive.models import HiveModelSnapshot

    db.add(
        HiveModelSnapshot(
            release_version=f"ops-heal-evidence-{uuid4().hex[:12]}",
            snapshot_type=OPS_HEAL_EVIDENCE_TYPE,
            parameters=pack,
            sample_count=int(pack.get("summary", {}).get("total_movements") or 0),
            notes=(
                f"Evidence: {pack.get('summary', {}).get('processes_active', 0)}/"
                f"{pack.get('summary', {}).get('processes_tracked', 0)} processes active"
            ),
        )
    )
    db.flush()
    return pack


def latest_evidence_pack(*, db: Session) -> dict[str, Any] | None:
    from app.hive.models import HiveModelSnapshot

    row = (
        db.query(HiveModelSnapshot)
        .filter(HiveModelSnapshot.snapshot_type == OPS_HEAL_EVIDENCE_TYPE)
        .order_by(HiveModelSnapshot.created_at.desc())
        .first()
    )
    if not row:
        return None
    params = row.parameters if isinstance(row.parameters, dict) else {}
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "notes": row.notes,
        **params,
    }


def proposals_from_process_evidence(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Draft human-reviewable changes from cross-process evidence."""
    summary = pack.get("summary") if isinstance(pack.get("summary"), dict) else {}
    drafts: list[dict[str, Any]] = []

    for fail in summary.get("hot_failures") or []:
        if not isinstance(fail, dict):
            continue
        process = str(fail.get("process") or "")
        errors = int(fail.get("errors") or 0)
        rate = float(fail.get("error_rate") or 0)
        if errors < 2 and rate < 0.25:
            continue
        if process in {"error_reports", "api_other"}:
            continue
        drafts.append(
            {
                "fingerprint": f"process_failures:{process}",
                "area": process,
                "priority": "high" if rate >= 0.35 or errors >= 5 else "medium",
                "title": f"Stabilize failing {process.replace('_', ' ')} process",
                "summary": (
                    f"{errors} error movement(s) on `{process}` "
                    f"(error_rate={rate:.0%}) in the evidence window."
                ),
                "recommended_change": (
                    f"Inspect recent `{process}` movements and failing responses, "
                    "add guards/regression coverage, and confirm the path recovers "
                    "cleanly on the next Learning check-in."
                ),
                "source_contracts": [],
                "auto_remediations_tried": [],
                "evidence": {"process": fail, "window_hours": pack.get("window_hours")},
            }
        )

    quiet = list(summary.get("processes_quiet") or [])
    # Only flag core product processes that should usually move when the app is used.
    expected_core = {
        "day_forge",
        "analyze",
        "decision_board",
        "tickets",
        "settle_day",
        "learning",
        "hive",
    }
    missing_core = sorted(expected_core.intersection(quiet))
    total_movements = int(summary.get("total_movements") or 0)
    if missing_core and total_movements >= 15:
        drafts.append(
            {
                "fingerprint": "process_quiet:" + ",".join(missing_core[:6]),
                "area": "process_coverage",
                "priority": "medium",
                "title": "Core processes produced no movements",
                "summary": (
                    f"App activity is present ({total_movements} movements) but these "
                    f"core processes stayed quiet: {', '.join(missing_core)}."
                ),
                "recommended_change": (
                    "Confirm Home/Learning/Board entry points still call these APIs, "
                    "or restore instrumentation if a process was bypassed."
                ),
                "source_contracts": [],
                "auto_remediations_tried": [],
                "evidence": {
                    "quiet_core": missing_core,
                    "active_processes": summary.get("processes_active"),
                },
            }
        )

    streams = pack.get("streams") if isinstance(pack.get("streams"), dict) else {}
    hive = streams.get("hive") if isinstance(streams.get("hive"), dict) else {}
    pending = int(hive.get("pending") or 0)
    resolved = int(hive.get("resolved") or 0)
    if pending >= 20 and resolved < 5:
        drafts.append(
            {
                "fingerprint": "process_hive_stall",
                "area": "hive",
                "priority": "high",
                "title": "Hive capture process is not draining into grades",
                "summary": f"Hive pending={pending} vs resolved={resolved} in window.",
                "recommended_change": (
                    "Verify settle-day + ESPN/Odds mapping run for every sport the app "
                    "uses, then confirm Learning sync moves pending → eligible."
                ),
                "source_contracts": ["hive_pending_drain"],
                "auto_remediations_tried": ["run_settle_day", "sync_hive_outcomes"],
                "evidence": hive,
            }
        )

    return drafts
