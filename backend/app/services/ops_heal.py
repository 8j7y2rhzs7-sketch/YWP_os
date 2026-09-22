"""Ops Heal — product self-heal bot alongside Hive pick-calibration.

Hive learns from settled WIN/LOSS and adjusts probability blend.
Ops Heal watches product health contracts (Day Forge freeze, Decision Board
500s, settlement stalls) and runs *allowlisted* remediations only.

It never edits application source code. Code patches stay human PRs.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

OPS_HEAL_CYCLE_TYPE = "ops_heal_cycle"
OPS_HEAL_STATUS_TYPE = "ops_heal_status"

# Allowlisted remediation ids — expand only with explicit safe actions.
ALLOWED_REMEDIATIONS = frozenset(
    {
        "run_settle_day",
        "sync_hive_outcomes",
        "probe_day_forge",
        "ack_error_reports",
        "record_coverage_gaps",
        "noop_observe",
    }
)


@dataclass(slots=True)
class ContractResult:
    contract_id: str
    title: str
    ok: bool
    severity: str  # info | warn | critical
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
    remediations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RemediationResult:
    remediation_id: str
    ok: bool
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_ops_heal_cycle(
    *,
    db: Session,
    user_id: str,
    timezone_name: str | None = None,
    trigger: str = "manual",
    apply: bool = True,
) -> dict[str, Any]:
    """Evaluate health contracts and optionally apply allowlisted remediations."""
    contracts = [
        _contract_day_forge_not_frozen(db=db, user_id=user_id),
        _contract_board_errors(db=db, user_id=user_id),
        _contract_hive_pending_drain(db=db, user_id=user_id),
        _contract_settlement_gaps(db=db, user_id=user_id),
    ]

    planned: list[str] = []
    for row in contracts:
        if not row.ok:
            for rem in row.remediations:
                if rem in ALLOWED_REMEDIATIONS and rem not in planned:
                    planned.append(rem)

    applied: list[RemediationResult] = []
    if apply and planned:
        for rem_id in planned:
            applied.append(
                _apply_remediation(
                    rem_id,
                    db=db,
                    user_id=user_id,
                    timezone_name=timezone_name,
                )
            )

    failing = [c for c in contracts if not c.ok]
    status = "healthy" if not failing else (
        "critical" if any(c.severity == "critical" for c in failing) else "degraded"
    )
    explanation = (
        "Ops Heal: all product health contracts green."
        if status == "healthy"
        else (
            f"Ops Heal: {len(failing)} contract(s) failing — "
            + ", ".join(c.contract_id for c in failing)
            + (
                f"; applied {len(applied)} allowlisted remediation(s)."
                if applied
                else "; observation only (apply=false)."
            )
        )
    )

    cycle = {
        "id": str(uuid4()),
        "trigger": trigger,
        "status": status,
        "explanation": explanation,
        "contracts": [_contract_dict(c) for c in contracts],
        "planned_remediations": planned,
        "applied_remediations": [_rem_dict(r) for r in applied],
        "bot": "ops_heal",
        "scope": "product_health",
        "not_in_scope": [
            "probability_calibration",
            "source_code_edits",
            "unbounded_autonomous_deploys",
        ],
        "created_at": _utcnow().isoformat(),
    }
    _persist_cycle(db=db, cycle=cycle)
    db.flush()
    return cycle


def list_ops_heal_cycles(*, db: Session, limit: int = 12) -> list[dict[str, Any]]:
    from app.hive.models import HiveModelSnapshot

    rows = (
        db.query(HiveModelSnapshot)
        .filter(HiveModelSnapshot.snapshot_type == OPS_HEAL_CYCLE_TYPE)
        .order_by(HiveModelSnapshot.created_at.desc())
        .limit(max(1, min(limit, 40)))
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        params = row.parameters if isinstance(row.parameters, dict) else {}
        out.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "notes": row.notes,
                **params,
            }
        )
    return out


def latest_ops_heal_status(*, db: Session) -> dict[str, Any]:
    cycles = list_ops_heal_cycles(db=db, limit=1)
    if not cycles:
        return {
            "bot": "ops_heal",
            "status": "idle",
            "explanation": "Ops Heal has not run yet. Open Learning or POST /ops-heal/run.",
            "contracts": [],
        }
    return cycles[0]


def classify_error_for_heal(message: str, screen: str | None = None) -> list[str]:
    """Map client error text → contract remediations (no code edits)."""
    text = f"{message} {screen or ''}".lower()
    remediations: list[str] = []
    if "internal server error" in text or "build-ticket" in text or "decision board" in text:
        remediations.extend(["run_settle_day", "sync_hive_outcomes", "ack_error_reports"])
    if "day forge" in text or "standing by" in text or "slate heat is offline" in text:
        remediations.append("probe_day_forge")
    if "pending sync" in text or "settle" in text:
        remediations.extend(["run_settle_day", "sync_hive_outcomes"])
    return [r for r in dict.fromkeys(remediations) if r in ALLOWED_REMEDIATIONS]


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------


def _contract_day_forge_not_frozen(*, db: Session, user_id: str) -> ContractResult:
    """Day Forge must not sit forever at unavailable @ ~5%."""
    del db, user_id
    # Soft contract: verify the cook path no longer returns hard-unavailable freeze.
    # Probe imports the resolver; full HTTP slate may be heavy — check module invariants.
    try:
        from app.services.day_forge import cook_progress_from_slate, day_forge_sport_queue

        empty = cook_progress_from_slate([])
        queue = day_forge_sport_queue(
            [
                {"key": "nfl", "in_season": True},
                {"key": "mlb", "in_season": True},
                {"key": "wnba", "in_season": True},
            ]
        )
        frozen = empty.status == "unavailable" and float(empty.progress) <= 0.06
        ok = (not frozen) and bool(queue) and queue[0] == "nfl"
        return ContractResult(
            contract_id="day_forge_not_frozen",
            title="Day Forge stays cooking / cascades sports",
            ok=ok,
            severity="critical" if not ok else "info",
            detail=(
                "Empty/offline slate stays cooking; sport queue prefers live keys."
                if ok
                else "Day Forge still freezes at unavailable — deploy cook-path fix."
            ),
            evidence={
                "empty_status": empty.status,
                "empty_phase": empty.phase,
                "empty_progress": empty.progress,
                "sport_queue_head": queue[:4],
            },
            remediations=["probe_day_forge"] if not ok else [],
        )
    except Exception as exc:  # noqa: BLE001
        return ContractResult(
            contract_id="day_forge_not_frozen",
            title="Day Forge stays cooking / cascades sports",
            ok=False,
            severity="critical",
            detail=f"Day Forge contract crashed: {exc}",
            remediations=["probe_day_forge", "noop_observe"],
        )


def _contract_board_errors(*, db: Session, user_id: str) -> ContractResult:
    from app.models import ErrorReport

    since = _utcnow() - timedelta(hours=48)
    rows = list(
        db.scalars(
            select(ErrorReport)
            .where(
                ErrorReport.status == "open",
                ErrorReport.created_at >= since,
            )
            .order_by(ErrorReport.created_at.desc())
            .limit(40)
        ).all()
    )
    # Prefer this user's reports; still include anonymous crashes.
    scoped = [
        r for r in rows if r.user_id is None or r.user_id == user_id or not user_id
    ]
    boardish = [
        r
        for r in scoped
        if _looks_like_board_failure(r.message or "", r.screen)
    ]
    ok = len(boardish) == 0
    return ContractResult(
        contract_id="decision_board_errors",
        title="Decision Board not throwing open Internal Server Errors",
        ok=ok,
        severity="critical" if not ok else "info",
        detail=(
            "No open Decision Board / build-ticket Internal Server Errors in 48h."
            if ok
            else f"{len(boardish)} open board-related error report(s) need heal + ack."
        ),
        evidence={
            "open_board_errors": [
                {"id": r.id, "message": (r.message or "")[:160], "screen": r.screen}
                for r in boardish[:8]
            ]
        },
        remediations=(
            ["run_settle_day", "sync_hive_outcomes", "ack_error_reports"] if not ok else []
        ),
    )


def _contract_hive_pending_drain(*, db: Session, user_id: str) -> ContractResult:
    from app.hive.models import HiveLearningEvent
    from app.hive.service import hive_learning_maturity

    pending = int(
        db.scalar(
            select(func.count())
            .select_from(HiveLearningEvent)
            .where(HiveLearningEvent.outcome.is_(None))
        )
        or 0
    )
    maturity = hive_learning_maturity(db=db)
    # Warn when a backlog sits while eligible is still near zero — settle isn't running.
    stalled = pending >= 20 and int(maturity.get("eligible_samples") or 0) < 5
    ok = not stalled
    return ContractResult(
        contract_id="hive_pending_drain",
        title="Hive pending outcomes get settled (not stuck forever)",
        ok=ok,
        severity="warn" if not ok else "info",
        detail=(
            f"Pending={pending}, eligible={maturity.get('eligible_samples', 0)} — ok."
            if ok
            else (
                f"Pending sync backlog ({pending}) with almost no settled samples — "
                "run settle-day / ESPN+Odds auto-grade."
            )
        ),
        evidence={
            "pending": pending,
            "eligible_samples": maturity.get("eligible_samples"),
            "optimum_accuracy_pct": maturity.get("optimum_accuracy_pct"),
            "user_id": user_id,
        },
        remediations=["run_settle_day", "sync_hive_outcomes"] if not ok else [],
    )


def _contract_settlement_gaps(*, db: Session, user_id: str) -> ContractResult:
    from app.models import LearningEvent

    del user_id
    since = _utcnow() - timedelta(days=7)
    gaps = list(
        db.scalars(
            select(LearningEvent)
            .where(
                LearningEvent.event_type == "SETTLEMENT_COVERAGE_GAP",
                LearningEvent.created_at >= since,
            )
            .order_by(LearningEvent.created_at.desc())
            .limit(30)
        ).all()
    )
    ok = len(gaps) < 10
    return ContractResult(
        contract_id="settlement_coverage_gaps",
        title="Settlement coverage gaps stay scarce",
        ok=ok,
        severity="warn" if not ok else "info",
        detail=(
            f"{len(gaps)} settlement coverage gap event(s) in 7d."
            + ("" if ok else " Record + review markets still skipping auto-grade.")
        ),
        evidence={
            "gap_count": len(gaps),
            "samples": [
                {
                    "sport": g.sport,
                    "market_type": g.market_type,
                    "detail": (g.analysis or {}).get("detail")
                    if isinstance(g.analysis, dict)
                    else None,
                }
                for g in gaps[:8]
            ],
        },
        remediations=["record_coverage_gaps", "run_settle_day"] if not ok else [],
    )


def _looks_like_board_failure(message: str, screen: str | None) -> bool:
    text = f"{message} {screen or ''}".lower()
    if "internal server error" in text:
        return True
    if "decision board" in text or "build-ticket" in text or "ticket builder" in text:
        return True
    if screen and re.search(r"analysis", screen, re.I):
        return "server error" in text or "failed" in text
    return False


# ---------------------------------------------------------------------------
# Remediations (allowlisted only)
# ---------------------------------------------------------------------------


def _apply_remediation(
    remediation_id: str,
    *,
    db: Session,
    user_id: str,
    timezone_name: str | None,
) -> RemediationResult:
    if remediation_id not in ALLOWED_REMEDIATIONS:
        return RemediationResult(
            remediation_id=remediation_id,
            ok=False,
            detail="Remediation not in allowlist.",
        )
    handlers: dict[str, Callable[..., RemediationResult]] = {
        "run_settle_day": _rem_run_settle_day,
        "sync_hive_outcomes": _rem_sync_hive,
        "probe_day_forge": _rem_probe_day_forge,
        "ack_error_reports": _rem_ack_errors,
        "record_coverage_gaps": _rem_record_gaps,
        "noop_observe": lambda **_: RemediationResult(
            remediation_id="noop_observe",
            ok=True,
            detail="Observed only — no mutation.",
        ),
    }
    try:
        return handlers[remediation_id](
            db=db, user_id=user_id, timezone_name=timezone_name
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ops Heal remediation %s failed", remediation_id)
        return RemediationResult(
            remediation_id=remediation_id,
            ok=False,
            detail=f"Remediation failed: {exc}",
        )


def _rem_run_settle_day(
    *, db: Session, user_id: str, timezone_name: str | None
) -> RemediationResult:
    from app.services.settlement import settle_user_day

    result = settle_user_day(db, user_id, timezone_name=timezone_name)
    return RemediationResult(
        remediation_id="run_settle_day",
        ok=True,
        detail=(
            f"Settle-day ran: {len(result.items)} item(s), "
            f"{result.hive_outcomes_mapped} Hive outcome(s) mapped."
        ),
        evidence={
            "items": len(result.items),
            "hive_outcomes_mapped": result.hive_outcomes_mapped,
            "board_graded": result.board_graded,
        },
    )


def _rem_sync_hive(
    *, db: Session, user_id: str, timezone_name: str | None
) -> RemediationResult:
    del timezone_name
    from app.services.settlement import sync_hive_outcomes_for_graded

    updated = sync_hive_outcomes_for_graded(db, user_id)
    return RemediationResult(
        remediation_id="sync_hive_outcomes",
        ok=True,
        detail=f"Synced {updated} graded recommendation(s) onto Hive captures.",
        evidence={"updated": updated},
    )


def _rem_probe_day_forge(
    *, db: Session, user_id: str, timezone_name: str | None
) -> RemediationResult:
    del db, user_id, timezone_name
    from app.services.day_forge import cook_progress_from_slate, day_forge_sport_queue
    from app.services.odds_provider import build_app_sports_catalog

    catalog = build_app_sports_catalog()
    queue = day_forge_sport_queue(catalog)
    cook = cook_progress_from_slate([])
    ok = cook.status == "cooking" and bool(queue)
    return RemediationResult(
        remediation_id="probe_day_forge",
        ok=ok,
        detail=(
            f"Day Forge probe: status={cook.status} phase={cook.phase} "
            f"queue={queue[:5]}"
        ),
        evidence={"status": cook.status, "phase": cook.phase, "queue": queue[:8]},
    )


def _rem_ack_errors(
    *, db: Session, user_id: str, timezone_name: str | None
) -> RemediationResult:
    del timezone_name
    from app.models import AuditLog, ErrorReport

    since = _utcnow() - timedelta(hours=48)
    rows = list(
        db.scalars(
            select(ErrorReport)
            .where(
                ErrorReport.status == "open",
                ErrorReport.created_at >= since,
            )
            .limit(40)
        ).all()
    )
    acked = 0
    for row in rows:
        if not _looks_like_board_failure(row.message or "", row.screen):
            continue
        # Only ack reports we attempted to heal — mark triage, not silent delete.
        row.status = "triaged_by_ops_heal"
        acked += 1
    if acked:
        db.add(
            AuditLog(
                user_id=user_id,
                action="OPS_HEAL_ACK_ERRORS",
                entity_type="error_report",
                entity_id="batch",
                details={"acked": acked},
            )
        )
        db.flush()
    return RemediationResult(
        remediation_id="ack_error_reports",
        ok=True,
        detail=f"Triaged {acked} board-related open error report(s).",
        evidence={"acked": acked},
    )


def _rem_record_gaps(
    *, db: Session, user_id: str, timezone_name: str | None
) -> RemediationResult:
    del timezone_name
    from app.hive.service import record_hive_progress_report
    from app.models import LearningEvent

    since = _utcnow() - timedelta(days=7)
    gaps = list(
        db.scalars(
            select(LearningEvent)
            .where(
                LearningEvent.event_type == "SETTLEMENT_COVERAGE_GAP",
                LearningEvent.created_at >= since,
            )
            .limit(50)
        ).all()
    )
    record_hive_progress_report(
        db=db,
        trigger="ops_heal_coverage",
        extra={
            "ops_heal": True,
            "gap_count": len(gaps),
            "gaps": [
                {
                    "sport": g.sport,
                    "market_type": g.market_type,
                    "detail": (g.analysis or {}).get("detail")
                    if isinstance(g.analysis, dict)
                    else None,
                }
                for g in gaps[:20]
            ],
            "user_id": user_id,
        },
    )
    return RemediationResult(
        remediation_id="record_coverage_gaps",
        ok=True,
        detail=f"Published {len(gaps)} settlement gap(s) into Hive progress.",
        evidence={"gap_count": len(gaps)},
    )


def _persist_cycle(*, db: Session, cycle: dict[str, Any]) -> None:
    from app.hive.models import HiveModelSnapshot

    db.add(
        HiveModelSnapshot(
            release_version=f"ops-heal-{uuid4().hex[:12]}",
            snapshot_type=OPS_HEAL_CYCLE_TYPE,
            parameters=cycle,
            sample_count=sum(1 for c in cycle.get("contracts", []) if not c.get("ok")),
            notes=str(cycle.get("explanation") or "ops_heal"),
        )
    )


def _contract_dict(row: ContractResult) -> dict[str, Any]:
    return {
        "contract_id": row.contract_id,
        "title": row.title,
        "ok": row.ok,
        "severity": row.severity,
        "detail": row.detail,
        "evidence": row.evidence,
        "remediations": row.remediations,
    }


def _rem_dict(row: RemediationResult) -> dict[str, Any]:
    return {
        "remediation_id": row.remediation_id,
        "ok": row.ok,
        "detail": row.detail,
        "evidence": row.evidence,
    }
