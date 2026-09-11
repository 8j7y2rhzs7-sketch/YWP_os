"""End-of-day quality pass — learn from called AND uncalled board outcomes.

After Sync Scores grades finals, this pass compares:
- locked ticket legs vs board PLAY/LEAN/WATCH that never locked
- missed winners (shown as PLAY/LEAN, won, not locked)
- good dodges (Sheet SKIP that lost)
- false skips (Sheet SKIP that won)
- packaging notes (locked hit-rate vs leftover PLAY/LEAN hit-rate)

Writes LearningEvent rows so next-day quality can improve.
Does not invent certainty language — only process forensics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.hive.service import record_hive_action
from app.models import LearningEvent, Recommendation, Ticket, TicketLeg
from app.services.learning import record_usage_event

BOARD_CALL_DECISIONS = frozenset({"PLAY", "LEAN", "WATCH"})
PLAY_LEAN = frozenset({"PLAY", "LEAN"})


@dataclass
class EodPickRef:
    recommendation_id: str
    selection: str
    decision: str
    recommendation_tier: str
    outcome: str
    market_type: str
    american_odds: int


@dataclass
class EodQualityReport:
    slate_date: date
    locked_graded: int = 0
    locked_wins: int = 0
    locked_losses: int = 0
    board_uncalled_graded: int = 0
    board_uncalled_wins: int = 0
    board_uncalled_losses: int = 0
    missed_winners: list[EodPickRef] = field(default_factory=list)
    good_dodges: list[EodPickRef] = field(default_factory=list)
    false_skips: list[EodPickRef] = field(default_factory=list)
    locked_hit_rate: float | None = None
    uncalled_play_lean_hit_rate: float | None = None
    packaging_gap: float | None = None
    quality_score: float = 0.0
    headline: str = "No graded slate yet."
    lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slate_date"] = self.slate_date.isoformat()
        return payload


def _hit_rate(wins: int, losses: int) -> float | None:
    total = wins + losses
    if total <= 0:
        return None
    return round(wins / total, 4)


def _is_sheet_menu(recommendation: Recommendation) -> bool:
    if (recommendation.data_source or "") == "THE_ODDS_API_BOARD":
        return True
    snap = recommendation.snapshot or {}
    if snap.get("data_source") == "THE_ODDS_API_BOARD":
        return True
    reasons = snap.get("reason_codes") or recommendation.reason_codes or []
    return "SPORTSBOOK_MENU" in reasons


def _pick_ref(recommendation: Recommendation) -> EodPickRef:
    return EodPickRef(
        recommendation_id=str(recommendation.id),
        selection=str(recommendation.selection),
        decision=str(recommendation.decision),
        recommendation_tier=str(recommendation.recommendation_tier or ""),
        outcome=str(recommendation.outcome or ""),
        market_type=str(recommendation.market_type or ""),
        american_odds=int(recommendation.american_odds or 0),
    )


def _locked_recommendation_ids(db: Session, user_id: str, slate_date: date) -> set[str]:
    rows = db.execute(
        select(TicketLeg.recommendation_id)
        .join(Ticket, Ticket.id == TicketLeg.ticket_id)
        .where(
            Ticket.user_id == user_id,
            Ticket.slate_date == slate_date,
            Ticket.status.in_(("placed", "settled")),
        )
    ).all()
    return {str(row[0]) for row in rows if row[0]}


def run_eod_quality_pass(
    db: Session,
    user_id: str,
    *,
    slate_date: date,
) -> EodQualityReport:
    """Build + persist end-of-day quality forensics for one slate date."""
    locked_ids = _locked_recommendation_ids(db, user_id, slate_date)
    recommendations = list(
        db.scalars(
            select(Recommendation).where(
                Recommendation.created_by_user_id == user_id,
                Recommendation.slate_date == slate_date,
                Recommendation.outcome.in_(("WIN", "LOSS", "PUSH", "VOID")),
            )
        ).all()
    )

    report = EodQualityReport(slate_date=slate_date)
    uncalled_play_lean_wins = 0
    uncalled_play_lean_losses = 0

    for recommendation in recommendations:
        outcome = str(recommendation.outcome or "")
        if outcome not in {"WIN", "LOSS"}:
            continue
        locked = str(recommendation.id) in locked_ids
        decision = str(recommendation.decision or "")
        sheet = _is_sheet_menu(recommendation)

        if locked:
            report.locked_graded += 1
            if outcome == "WIN":
                report.locked_wins += 1
            else:
                report.locked_losses += 1
            continue

        if decision in BOARD_CALL_DECISIONS:
            report.board_uncalled_graded += 1
            if outcome == "WIN":
                report.board_uncalled_wins += 1
            else:
                report.board_uncalled_losses += 1

            if decision in PLAY_LEAN:
                if outcome == "WIN":
                    uncalled_play_lean_wins += 1
                    report.missed_winners.append(_pick_ref(recommendation))
                    try:
                        record_hive_action(
                            db=db,
                            source_recommendation_id=str(recommendation.id),
                            action="ignored",
                        )
                    except Exception:  # noqa: BLE001 — never fail settle on Hive tagging
                        pass
                else:
                    uncalled_play_lean_losses += 1

        if sheet and decision in {"SKIP", "REVIEW"}:
            if outcome == "LOSS":
                report.good_dodges.append(_pick_ref(recommendation))
            elif outcome == "WIN":
                report.false_skips.append(_pick_ref(recommendation))

    report.locked_hit_rate = _hit_rate(report.locked_wins, report.locked_losses)
    report.uncalled_play_lean_hit_rate = _hit_rate(
        uncalled_play_lean_wins, uncalled_play_lean_losses
    )
    if (
        report.locked_hit_rate is not None
        and report.uncalled_play_lean_hit_rate is not None
    ):
        report.packaging_gap = round(
            report.uncalled_play_lean_hit_rate - report.locked_hit_rate,
            4,
        )

    report.quality_score, report.headline, report.lessons = _score_day(report)
    primary_sport = next(
        (str(item.sport) for item in recommendations if item.sport),
        "mlb",
    )
    _persist_quality_events(db, user_id, report, sport=primary_sport)
    db.flush()
    return report


def _score_day(report: EodQualityReport) -> tuple[float, str, list[str]]:
    lessons: list[str] = []
    score = 55.0

    if report.locked_hit_rate is not None:
        score += (report.locked_hit_rate - 0.5) * 40
        lessons.append(
            f"Locked legs hit {report.locked_wins}/"
            f"{report.locked_wins + report.locked_losses}."
        )
    else:
        lessons.append("No locked legs graded today — board memory still recorded.")

    missed = len(report.missed_winners)
    if missed:
        score -= min(18.0, missed * 3.0)
        top = ", ".join(item.selection for item in report.missed_winners[:3])
        lessons.append(
            f"Missed {missed} PLAY/LEAN winner(s) left unlocked"
            + (f" (e.g. {top})." if top else ".")
        )
    else:
        score += 4.0
        lessons.append("No missed PLAY/LEAN winners left on the board.")

    if report.false_skips:
        score -= min(10.0, len(report.false_skips) * 2.5)
        lessons.append(
            f"{len(report.false_skips)} Sheet SKIP(s) won — selection filter needs review."
        )
    if report.good_dodges:
        score += min(8.0, len(report.good_dodges) * 2.0)
        lessons.append(
            f"{len(report.good_dodges)} Sheet SKIP(s) lost — good dodge(s) logged."
        )

    if report.packaging_gap is not None:
        if report.packaging_gap >= 0.08:
            score -= 8.0
            lessons.append(
                "Packaging gap: leftover PLAY/LEAN hit higher than locked legs — "
                "ticket construction needs work, not just leg quality."
            )
        elif report.packaging_gap <= -0.05:
            score += 5.0
            lessons.append(
                "Locked package outperformed leftover PLAY/LEAN board — packaging held."
            )

    score = max(0.0, min(100.0, round(score, 1)))
    if score >= 75:
        headline = "Strong process day — keep the same selection + packaging discipline."
    elif score >= 55:
        headline = "Mixed process day — review missed winners and packaging gap."
    else:
        headline = "Weak process day — uncalled board and packaging need a hard look."
    return score, headline, lessons


def _persist_quality_events(
    db: Session,
    user_id: str,
    report: EodQualityReport,
    *,
    sport: str = "mlb",
) -> None:
    recent = list(
        db.scalars(
            select(LearningEvent)
            .where(LearningEvent.event_type == "EOD_QUALITY_PASS")
            .order_by(LearningEvent.created_at.desc())
            .limit(50)
        ).all()
    )
    for event in recent:
        analysis = event.analysis or {}
        if (
            analysis.get("user_id") == user_id
            and analysis.get("slate_date") == report.slate_date.isoformat()
        ):
            event.analysis = {
                **analysis,
                **report.to_dict(),
                "user_id": user_id,
                "refreshed": True,
            }
            event.sport = sport
            return

    record_usage_event(
        db,
        event_type="EOD_QUALITY_PASS",
        sport=sport,
        market_type="day_quality",
        analysis={"user_id": user_id, **report.to_dict()},
    )
    for item in report.missed_winners[:12]:
        record_usage_event(
            db,
            event_type="EOD_MISSED_WINNER",
            sport=sport,
            market_type=item.market_type,
            recommendation_id=item.recommendation_id,
            analysis={
                "user_id": user_id,
                "slate_date": report.slate_date.isoformat(),
                "selection": item.selection,
                "decision": item.decision,
                "recommendation_tier": item.recommendation_tier,
                "american_odds": item.american_odds,
                "lesson": "Board surfaced a winner that was not locked.",
            },
        )
    for item in report.false_skips[:8]:
        record_usage_event(
            db,
            event_type="EOD_FALSE_SKIP",
            sport=sport,
            market_type=item.market_type,
            recommendation_id=item.recommendation_id,
            analysis={
                "user_id": user_id,
                "slate_date": report.slate_date.isoformat(),
                "selection": item.selection,
                "lesson": "Sheet SKIP won — customer-selection / filter miss.",
            },
        )
    for item in report.good_dodges[:8]:
        record_usage_event(
            db,
            event_type="EOD_GOOD_DODGE",
            sport=sport,
            market_type=item.market_type,
            recommendation_id=item.recommendation_id,
            analysis={
                "user_id": user_id,
                "slate_date": report.slate_date.isoformat(),
                "selection": item.selection,
                "lesson": "Sheet SKIP lost — stay-away held.",
            },
        )
