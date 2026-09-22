"""Ops Heal — product self-heal bot alongside Hive pick-calibration.

Hive learns from settled WIN/LOSS and adjusts probability blend.
Ops Heal collects evidence from *all* app process movements (API, audits,
learning events, protocol, tickets, locks, settlement, Hive, errors),
runs allowlisted remediations, and drafts human-reviewable change briefs.

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
OPS_HEAL_PROPOSAL_TYPE = "ops_heal_proposal"

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

PROPOSAL_STATUSES = frozenset({"pending", "implemented", "dismissed"})
PROPOSAL_REVIEW_ACTIONS = frozenset({"implemented", "dismissed"})


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

    # Collect + analyze → draft human-reviewable change briefs (never auto-code).
    from app.services.ops_evidence import (
        collect_all_process_evidence,
        persist_evidence_pack,
        proposals_from_process_evidence,
    )

    evidence = collect_all_process_evidence(db=db, user_id=user_id, hours=72)
    persist_evidence_pack(db=db, pack=evidence)

    drafts = analyze_improvement_proposals(
        db=db,
        user_id=user_id,
        contracts=contracts,
        applied=applied,
        trigger=trigger,
    )
    drafts.extend(proposals_from_process_evidence(evidence))
    proposals = upsert_improvement_proposals(db=db, drafts=drafts)

    pending_count = len(
        [p for p in list_ops_heal_proposals(db=db, status="pending", limit=40)]
    )
    evidence_summary = evidence.get("summary") if isinstance(evidence.get("summary"), dict) else {}
    if proposals:
        explanation += (
            f" Drafted {len(proposals)} improvement proposal(s) for human review "
            f"({pending_count} pending in inbox)."
        )
    elif pending_count:
        explanation += f" {pending_count} improvement proposal(s) waiting in inbox."
    explanation += (
        f" Evidence: {evidence_summary.get('processes_active', 0)}/"
        f"{evidence_summary.get('processes_tracked', 0)} processes active · "
        f"{evidence_summary.get('total_movements', 0)} movements."
    )

    cycle = {
        "id": str(uuid4()),
        "trigger": trigger,
        "status": status,
        "explanation": explanation,
        "contracts": [_contract_dict(c) for c in contracts],
        "planned_remediations": planned,
        "applied_remediations": [_rem_dict(r) for r in applied],
        "proposals_drafted": [p.get("id") for p in proposals],
        "proposals_pending": pending_count,
        "evidence": {
            "id": evidence.get("id"),
            "summary": evidence_summary,
            "process_coverage": evidence.get("process_coverage"),
        },
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
    from app.services.ops_evidence import latest_evidence_pack

    cycles = list_ops_heal_cycles(db=db, limit=1)
    pending = list_ops_heal_proposals(db=db, status="pending", limit=40)
    evidence = latest_evidence_pack(db=db)
    if not cycles:
        return {
            "bot": "ops_heal",
            "status": "idle",
            "explanation": "Ops Heal has not run yet. Open Learning or POST /ops-heal/run.",
            "contracts": [],
            "proposals_pending": len(pending),
            "proposals": pending[:8],
            "evidence": evidence,
        }
    latest = dict(cycles[0])
    latest["proposals_pending"] = len(pending)
    latest["proposals"] = pending[:8]
    if evidence and "evidence" not in latest:
        latest["evidence"] = {
            "id": evidence.get("id"),
            "summary": evidence.get("summary"),
            "process_coverage": evidence.get("process_coverage"),
            "created_at": evidence.get("created_at"),
        }
    return latest


def list_ops_heal_proposals(
    *,
    db: Session,
    status: str | None = "pending",
    limit: int = 20,
) -> list[dict[str, Any]]:
    from app.hive.models import HiveModelSnapshot

    rows = (
        db.query(HiveModelSnapshot)
        .filter(HiveModelSnapshot.snapshot_type == OPS_HEAL_PROPOSAL_TYPE)
        .order_by(HiveModelSnapshot.created_at.desc())
        .limit(120)
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        params = row.parameters if isinstance(row.parameters, dict) else {}
        item = {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "notes": row.notes,
            **params,
        }
        item_status = str(item.get("status") or "pending")
        if status and status != "all" and item_status != status:
            continue
        out.append(item)
        if len(out) >= max(1, min(limit, 60)):
            break
    return out


def review_ops_heal_proposal(
    *,
    db: Session,
    proposal_id: str,
    action: str,
    reviewer_user_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a drafted change as implemented or dismissed when a human checks in."""
    from app.hive.models import HiveModelSnapshot
    from app.models import AuditLog

    if action not in PROPOSAL_REVIEW_ACTIONS:
        raise ValueError(f"action must be one of {sorted(PROPOSAL_REVIEW_ACTIONS)}")

    row = db.get(HiveModelSnapshot, proposal_id)
    if row is None or row.snapshot_type != OPS_HEAL_PROPOSAL_TYPE:
        raise KeyError("proposal_not_found")

    params = dict(row.parameters) if isinstance(row.parameters, dict) else {}
    params["status"] = action
    params["reviewed_at"] = _utcnow().isoformat()
    params["reviewed_by_user_id"] = reviewer_user_id
    if note:
        params["review_note"] = note[:500]
    row.parameters = params
    row.notes = f"{action}: {params.get('title') or row.notes or 'ops_heal_proposal'}"
    db.add(
        AuditLog(
            user_id=reviewer_user_id,
            action=f"OPS_HEAL_PROPOSAL_{action.upper()}",
            entity_type="ops_heal_proposal",
            entity_id=proposal_id,
            details={
                "fingerprint": params.get("fingerprint"),
                "title": params.get("title"),
                "note": note,
            },
        )
    )
    db.flush()
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        **params,
    }


def analyze_improvement_proposals(
    *,
    db: Session,
    user_id: str,
    contracts: list[ContractResult],
    applied: list[RemediationResult],
    trigger: str,
) -> list[dict[str, Any]]:
    """Turn collected health evidence into concrete change briefs for humans."""
    del user_id
    applied_ids = [r.remediation_id for r in applied]
    drafts: list[dict[str, Any]] = []

    for contract in contracts:
        if contract.ok:
            continue
        draft = _proposal_from_contract(contract, applied_ids=applied_ids, trigger=trigger)
        if draft:
            drafts.append(draft)

    drafts.extend(_proposals_from_error_clusters(db=db, trigger=trigger))
    drafts.extend(_proposals_from_coverage_gaps(db=db, trigger=trigger))

    # Deduplicate within this cycle by fingerprint.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for draft in drafts:
        fp = str(draft.get("fingerprint") or "")
        if not fp or fp in seen:
            continue
        seen.add(fp)
        unique.append(draft)
    return unique


def upsert_improvement_proposals(
    *, db: Session, drafts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Persist new pending proposals; refresh evidence on matching open fingerprints."""
    from app.hive.models import HiveModelSnapshot

    if not drafts:
        return []

    open_rows = (
        db.query(HiveModelSnapshot)
        .filter(HiveModelSnapshot.snapshot_type == OPS_HEAL_PROPOSAL_TYPE)
        .order_by(HiveModelSnapshot.created_at.desc())
        .limit(80)
        .all()
    )
    by_fp: dict[str, Any] = {}
    for row in open_rows:
        params = row.parameters if isinstance(row.parameters, dict) else {}
        if str(params.get("status") or "pending") != "pending":
            continue
        fp = str(params.get("fingerprint") or "")
        if fp and fp not in by_fp:
            by_fp[fp] = row

    stored: list[dict[str, Any]] = []
    for draft in drafts:
        fp = str(draft.get("fingerprint") or "")
        if not fp:
            continue
        existing = by_fp.get(fp)
        if existing is not None:
            params = dict(existing.parameters) if isinstance(existing.parameters, dict) else {}
            params["evidence"] = draft.get("evidence") or params.get("evidence")
            params["summary"] = draft.get("summary") or params.get("summary")
            params["recommended_change"] = (
                draft.get("recommended_change") or params.get("recommended_change")
            )
            params["last_seen_at"] = _utcnow().isoformat()
            params["sightings"] = int(params.get("sightings") or 1) + 1
            params["auto_remediations_tried"] = list(
                dict.fromkeys(
                    list(params.get("auto_remediations_tried") or [])
                    + list(draft.get("auto_remediations_tried") or [])
                )
            )
            existing.parameters = params
            existing.sample_count = int(params.get("sightings") or 1)
            stored.append({"id": existing.id, **params})
            continue

        proposal_id = str(uuid4())
        payload = {
            **draft,
            "id": proposal_id,
            "status": "pending",
            "sightings": 1,
            "last_seen_at": _utcnow().isoformat(),
            "created_at": _utcnow().isoformat(),
            "bot": "ops_heal",
            "implements_when": "human_checks_in",
        }
        db.add(
            HiveModelSnapshot(
                id=proposal_id,
                release_version=f"ops-heal-proposal-{fp[:40]}-{uuid4().hex[:8]}",
                snapshot_type=OPS_HEAL_PROPOSAL_TYPE,
                parameters=payload,
                sample_count=1,
                notes=str(draft.get("title") or "ops_heal_proposal"),
            )
        )
        stored.append(payload)
    db.flush()
    return stored


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


# ---------------------------------------------------------------------------
# Improvement proposals (collect → analyze → human implements later)
# ---------------------------------------------------------------------------


def _proposal_from_contract(
    contract: ContractResult,
    *,
    applied_ids: list[str],
    trigger: str,
) -> dict[str, Any] | None:
    templates: dict[str, dict[str, Any]] = {
        "day_forge_not_frozen": {
            "area": "day_forge",
            "priority": "high",
            "title": "Keep Day Forge cooking instead of freezing at ~5%",
            "recommended_change": (
                "Verify cook_progress_from_slate empty/offline path stays status=cooking "
                "and day_forge_sport_queue prefers catalog keys. Ship a cook-path regression "
                "test if Home still stops polling."
            ),
        },
        "decision_board_errors": {
            "area": "decision_board",
            "priority": "high",
            "title": "Stop Decision Board Internal Server Errors after analyze",
            "recommended_change": (
                "Harden build-ticket / stay_away serialization for large prop boards. "
                "Cap or slim stay_away payloads and add a regression test for oversized analyzes."
            ),
        },
        "hive_pending_drain": {
            "area": "settlement",
            "priority": "medium",
            "title": "Unstick Hive pending outcomes so learning can leave 0%",
            "recommended_change": (
                "Ensure settle-day covers every app sport (ESPN + Odds) and maps grades onto "
                "Hive captures automatically. Add monitoring if pending stays high with low eligible."
            ),
        },
        "settlement_coverage_gaps": {
            "area": "settlement",
            "priority": "medium",
            "title": "Close settlement coverage gaps for skipped markets",
            "recommended_change": (
                "Review SETTLEMENT_COVERAGE_GAP events by sport/market and extend auto-grade "
                "paths (boxscore merge, prop result sources) for the repeating gaps."
            ),
        },
    }
    template = templates.get(contract.contract_id)
    if not template:
        return None
    return {
        "fingerprint": f"contract:{contract.contract_id}",
        "area": template["area"],
        "priority": template["priority"],
        "title": template["title"],
        "summary": contract.detail,
        "recommended_change": template["recommended_change"],
        "source_contracts": [contract.contract_id],
        "auto_remediations_tried": [
            r for r in applied_ids if r in (contract.remediations or [])
        ],
        "evidence": {
            "contract": _contract_dict(contract),
            "trigger": trigger,
        },
    }


def _proposals_from_error_clusters(*, db: Session, trigger: str) -> list[dict[str, Any]]:
    from app.models import ErrorReport

    since = _utcnow() - timedelta(hours=72)
    rows = list(
        db.scalars(
            select(ErrorReport)
            .where(ErrorReport.created_at >= since)
            .order_by(ErrorReport.created_at.desc())
            .limit(60)
        ).all()
    )
    clusters: dict[str, list[Any]] = {}
    for row in rows:
        key = _error_cluster_key(row.message or "", row.screen)
        if not key:
            continue
        clusters.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for key, group in clusters.items():
        if len(group) < 2:
            continue
        sample = group[0]
        out.append(
            {
                "fingerprint": f"error_cluster:{key}",
                "area": "client_errors",
                "priority": "high" if "internal_server_error" in key else "medium",
                "title": f"Recurring client error: {key.replace('_', ' ')}",
                "summary": (
                    f"{len(group)} report(s) in 72h matching `{key}`. "
                    f"Latest: {(sample.message or '')[:140]}"
                ),
                "recommended_change": (
                    "Reproduce from the listed screens, fix the failing endpoint/UI path, "
                    "and add a guard or regression test so the cluster stops growing."
                ),
                "source_contracts": ["decision_board_errors"]
                if "server_error" in key or "build_ticket" in key
                else [],
                "auto_remediations_tried": [],
                "evidence": {
                    "cluster_key": key,
                    "count": len(group),
                    "screens": sorted({(r.screen or "unknown") for r in group})[:8],
                    "sample_messages": [(r.message or "")[:160] for r in group[:5]],
                    "trigger": trigger,
                },
            }
        )
    return out


def _proposals_from_coverage_gaps(*, db: Session, trigger: str) -> list[dict[str, Any]]:
    from app.models import LearningEvent

    since = _utcnow() - timedelta(days=7)
    gaps = list(
        db.scalars(
            select(LearningEvent)
            .where(
                LearningEvent.event_type == "SETTLEMENT_COVERAGE_GAP",
                LearningEvent.created_at >= since,
            )
            .order_by(LearningEvent.created_at.desc())
            .limit(80)
        ).all()
    )
    by_market: dict[str, list[Any]] = {}
    for gap in gaps:
        sport = (gap.sport or "unknown").lower()
        market = (gap.market_type or "unknown").lower()
        by_market.setdefault(f"{sport}:{market}", []).append(gap)

    out: list[dict[str, Any]] = []
    for key, group in by_market.items():
        if len(group) < 3:
            continue
        sport, market = key.split(":", 1)
        out.append(
            {
                "fingerprint": f"coverage_gap:{key}",
                "area": "settlement",
                "priority": "medium",
                "title": f"Add auto-grade coverage for {sport} {market}",
                "summary": f"{len(group)} coverage-gap event(s) for {sport}/{market} in 7d.",
                "recommended_change": (
                    f"Extend settlement providers so {sport} {market} grades without a manual "
                    "per-sport ask. Prefer ESPN boxscore / Odds scores already used elsewhere."
                ),
                "source_contracts": ["settlement_coverage_gaps"],
                "auto_remediations_tried": [],
                "evidence": {
                    "sport": sport,
                    "market_type": market,
                    "count": len(group),
                    "samples": [
                        (g.analysis or {}).get("detail")
                        if isinstance(g.analysis, dict)
                        else None
                        for g in group[:5]
                    ],
                    "trigger": trigger,
                },
            }
        )
    return out


def _error_cluster_key(message: str, screen: str | None) -> str | None:
    text = f"{message} {screen or ''}".lower()
    if "internal server error" in text:
        return "internal_server_error"
    if "build-ticket" in text or "ticket builder" in text:
        return "build_ticket_failure"
    if "day forge" in text or "standing by" in text:
        return "day_forge_freeze"
    if "network request failed" in text or "failed to fetch" in text:
        return "network_request_failed"
    if "pending sync" in text:
        return "pending_sync_stall"
    return None


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
