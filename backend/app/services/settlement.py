"""Pull final scores/stats and settle recommendations for memory.

Grades:
1. Placed ticket legs (vault settle)
2. Board picks the user was shown (PLAY/LEAN/WATCH) even if never locked

Outcome settlement is automatic for memory (WIN/LOSS/PUSH/VOID).
Process audit grades stay UNCLASSIFIED until the user completes a full
manual grade — learning still records RESULT_GRADED with auto defaults.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import utcnow
from app.models import LearningEvent, Recommendation, Result, Ticket, TicketLeg, User
from app.hive.service import resolve_hive_outcome
from app.services.learning import apply_micro_learning
from app.services.lock_refresh import _game_pk
from app.services.mlb_provider import get_live_feed

logger = logging.getLogger(__name__)


@dataclass
class SettlementItem:
    recommendation_id: str
    ticket_id: str
    selection: str
    status: str
    outcome: str | None = None
    final_score: str | None = None
    actual_value: Decimal | None = None
    detail: str | None = None


BOARD_DECISIONS = frozenset({"PLAY", "LEAN", "WATCH"})


def _local_today(timezone_name: str | None = None) -> date:
    name = (timezone_name or "America/New_York").strip() or "America/New_York"
    try:
        return datetime.now(ZoneInfo(name)).date()
    except Exception:  # noqa: BLE001 — fall back if timezone string is invalid
        return datetime.now(ZoneInfo("America/New_York")).date()


def settle_user_day(
    db: Session, user_id: str, *, as_of: date | None = None, timezone_name: str | None = None
) -> list[SettlementItem]:
    """Settle placed tickets, then grade remaining board picks for the user.

    Future slate dates (tomorrow+) are ignored so Sync stays quiet until those
    games can actually final.
    """
    if as_of is None:
        if timezone_name is None:
            user = db.get(User, user_id)
            timezone_name = user.timezone if user else "America/New_York"
        as_of = _local_today(timezone_name)
    items = settle_user_placed_tickets(db, user_id, as_of=as_of)
    items.extend(settle_user_board_recommendations(db, user_id, as_of=as_of))
    return items


def settle_user_placed_tickets(
    db: Session, user_id: str, *, as_of: date | None = None
) -> list[SettlementItem]:
    """Settle ungraded active legs on placed tickets for one user."""
    tickets = list(
        db.scalars(
            select(Ticket)
            .where(Ticket.user_id == user_id, Ticket.status == "placed")
            .options(
                joinedload(Ticket.legs).joinedload(TicketLeg.recommendation).joinedload(
                    Recommendation.result
                )
            )
            .order_by(Ticket.created_at.desc())
        ).unique()
    )
    items: list[SettlementItem] = []
    for ticket in tickets:
        if as_of is not None and ticket.slate_date > as_of:
            continue
        items.extend(_settle_ticket(db, ticket))
    db.commit()
    return items


def settle_user_board_recommendations(
    db: Session, user_id: str, *, as_of: date | None = None
) -> list[SettlementItem]:
    """Grade ungraded PLAY/LEAN/WATCH board picks even if never locked into a ticket.

    Locked tickets still matter for exposure/P&L, but every pick the protocol
    surfaced for the day is training data for the next day.
    Future slate dates are skipped until their calendar day arrives.
    """
    query = (
        select(Recommendation)
        .where(
            Recommendation.created_by_user_id == user_id,
            Recommendation.outcome.is_(None),
            Recommendation.decision.in_(BOARD_DECISIONS),
        )
        .options(joinedload(Recommendation.result))
        .order_by(Recommendation.slate_date.desc(), Recommendation.rank.asc())
    )
    if as_of is not None:
        query = query.where(Recommendation.slate_date <= as_of)
    recommendations = list(db.scalars(query).unique())
    items: list[SettlementItem] = []
    for recommendation in recommendations:
        if recommendation.result:
            continue
        try:
            graded = _grade_recommendation(
                db,
                recommendation,
                stake=Decimal("0.00"),
                extra_tags=["BOARD_SETTLED", "NOT_LOCKED"],
                lesson=(
                    "Auto-settled board pick (never locked). "
                    "Outcome still trains next-day weights."
                ),
            )
        except Exception as exc:  # noqa: BLE001 — keep batch settling resilient
            logger.exception("Board settlement failed for %s", recommendation.id)
            items.append(
                SettlementItem(
                    recommendation_id=recommendation.id,
                    ticket_id="",
                    selection=recommendation.selection,
                    status="error",
                    detail=str(exc),
                )
            )
            continue
        if graded["status"] == "already_graded":
            continue
        items.append(
            SettlementItem(
                recommendation_id=recommendation.id,
                ticket_id="",
                selection=recommendation.selection,
                status=graded["status"],
                outcome=graded.get("outcome"),
                final_score=graded.get("final_score"),
                actual_value=graded.get("actual_value"),
                detail=graded.get("detail")
                or (
                    "Board pick graded for memory (not on a locked ticket)."
                    if graded["status"] == "graded"
                    else None
                ),
            )
        )
    db.commit()
    return items


def _settle_ticket(db: Session, ticket: Ticket) -> list[SettlementItem]:
    items: list[SettlementItem] = []
    active = [leg for leg in ticket.legs if leg.action in {"follow", "replace"}]
    ungraded = [
        leg
        for leg in active
        if leg.recommendation and not leg.recommendation.outcome and not leg.recommendation.result
    ]
    if not ungraded:
        if active and all(leg.recommendation and leg.recommendation.outcome for leg in active):
            money = _finalize_ticket_wager(ticket)
            if ticket.status != "settled":
                ticket.status = "settled"
            items.append(
                SettlementItem(
                    recommendation_id="",
                    ticket_id=ticket.id,
                    selection=ticket.label,
                    status="ticket_settled",
                    detail=(
                        "All active legs already graded; ticket marked settled."
                        + (
                            f" Wager P&L {money}."
                            if money is not None
                            else ""
                        )
                    ),
                )
            )
        return items

    # Recommendation Results stay research-memory (0 stake on multi-leg).
    # Actual bankroll P&L is finalized once on the ticket.
    stake_per_leg = (
        Decimal(str(ticket.stake)).quantize(Decimal("0.01"))
        if len(active) == 1
        else Decimal("0.00")
    )

    for leg in ungraded:
        recommendation = leg.recommendation
        assert recommendation is not None
        try:
            graded = _grade_recommendation(db, recommendation, stake=stake_per_leg)
        except Exception as exc:  # noqa: BLE001 — keep batch settling resilient
            logger.exception("Settlement failed for %s", recommendation.id)
            items.append(
                SettlementItem(
                    recommendation_id=recommendation.id,
                    ticket_id=ticket.id,
                    selection=recommendation.selection,
                    status="error",
                    detail=str(exc),
                )
            )
            continue
        items.append(
            SettlementItem(
                recommendation_id=recommendation.id,
                ticket_id=ticket.id,
                selection=recommendation.selection,
                status=graded["status"],
                outcome=graded.get("outcome"),
                final_score=graded.get("final_score"),
                actual_value=graded.get("actual_value"),
                detail=graded.get("detail"),
            )
        )

    db.flush()
    db.refresh(ticket)
    active_after = [leg for leg in ticket.legs if leg.action in {"follow", "replace"}]
    if active_after and all(
        leg.recommendation and leg.recommendation.outcome for leg in active_after
    ):
        money = _finalize_ticket_wager(ticket)
        ticket.status = "settled"
        items.append(
            SettlementItem(
                recommendation_id="",
                ticket_id=ticket.id,
                selection=ticket.label,
                status="ticket_settled",
                detail=(
                    "Ticket marked settled after all active legs graded."
                    + (f" Wager P&L {money}." if money is not None else "")
                ),
            )
        )
    return items


def _american_decimal(odds: int) -> Decimal:
    if odds > 0:
        return Decimal("1") + (Decimal(odds) / Decimal("100"))
    return Decimal("1") + (Decimal("100") / Decimal(abs(odds)))


def _finalize_ticket_wager(ticket: Ticket) -> Decimal | None:
    """Idempotently record ticket-level payout/P&L from active leg outcomes."""
    if ticket.settled_profit_loss is not None and ticket.settled_at is not None:
        return ticket.settled_profit_loss

    active = [leg for leg in ticket.legs if leg.action in {"follow", "replace"}]
    if not active:
        return None
    if any(not leg.recommendation or not leg.recommendation.outcome for leg in active):
        return None

    stake = Decimal(str(ticket.stake or 0)).quantize(Decimal("0.01"))
    outcomes = [leg.recommendation.outcome for leg in active]  # type: ignore[union-attr]

    if any(outcome == "LOSS" for outcome in outcomes):
        ticket.settled_outcome = "LOSS"
        ticket.settled_payout = Decimal("0.00")
        ticket.settled_profit_loss = (-stake).quantize(Decimal("0.01"))
    else:
        scoring = [
            leg
            for leg in active
            if leg.recommendation and leg.recommendation.outcome == "WIN"
        ]
        if not scoring:
            ticket.settled_outcome = "PUSH" if "PUSH" in outcomes else "VOID"
            ticket.settled_payout = stake
            ticket.settled_profit_loss = Decimal("0.00")
        else:
            combined = Decimal("1")
            for leg in scoring:
                combined *= _american_decimal(int(leg.american_odds))
            payout = (stake * combined).quantize(Decimal("0.01"))
            ticket.settled_outcome = "WIN"
            ticket.settled_payout = payout
            ticket.settled_profit_loss = (payout - stake).quantize(Decimal("0.01"))

    ticket.settled_at = utcnow()
    return ticket.settled_profit_loss

def _grade_recommendation(
    db: Session,
    recommendation: Recommendation,
    *,
    stake: Decimal,
    extra_tags: list[str] | None = None,
    lesson: str | None = None,
) -> dict[str, Any]:
    if recommendation.result or recommendation.outcome:
        return {"status": "already_graded", "outcome": recommendation.outcome}

    sport = (recommendation.sport or "").lower()
    if sport != "mlb":
        return {
            "status": "skipped",
            "detail": "Automatic settlement currently supports MLB finals only.",
        }

    if recommendation.data_source in {"YWP_DEMO_PROVIDER", "EXTERNAL_BOOK_LOG"}:
        return {"status": "skipped", "detail": "Demo/external picks are graded manually."}

    game_pk = _game_pk(recommendation)
    if game_pk is None:
        return {"status": "skipped", "detail": "No MLB game_pk on recommendation snapshot."}

    feed = get_live_feed(game_pk)
    box = _final_box(feed)
    if box is None:
        status = (
            feed.get("gameData", {}).get("status", {}).get("detailedState")
            or feed.get("gameData", {}).get("status", {}).get("abstractGameState")
            or "unknown"
        )
        return {
            "status": "pending",
            "detail": f"Game not final yet ({status}).",
        }

    derived = _derive_outcome(recommendation, box)
    if derived is None:
        return {
            "status": "skipped",
            "detail": f"No settlement rule for market {recommendation.market_type}.",
        }

    outcome = derived["outcome"]
    actual_value = derived.get("actual_value")
    final_score = derived.get("final_score")
    bet_line = recommendation.line
    miss_distance = _signed_margin(recommendation, actual_value, bet_line)
    profit_loss = _american_profit(stake, recommendation.american_odds, outcome)
    tags = list(dict.fromkeys(["AUTO_SETTLED", *(extra_tags or [])]))
    lesson_text = (
        lesson
        or "Auto-settled from MLB final score/stats. Complete process audit when ready."
    )

    result = Result(
        recommendation_id=recommendation.id,
        outcome=outcome,
        final_score=final_score,
        stake=stake,
        profit_loss=profit_loss,
        closing_odds=None,
        closing_line=None,
        clv_probability=None,
        line_value=None,
        actual_value=actual_value,
        bet_line=bet_line,
        miss_distance=miss_distance,
        killed_ticket=False,
        last_losing_leg=False,
        process_outcome_class="UNCLASSIFIED",
        error_category=None,
        assumptions_review=[],
        unexpected_events=[],
        quick_cash_result=None,
        chain_reaction_result=None,
        live_trigger_result=None,
        cashout_action="NOT_APPLICABLE",
        cashout_offer=None,
        cashout_reason=None,
        cashout_time=None,
        process_grade="C",
        variance_grade="MEDIUM",
        root_cause_tags=tags,
        lesson=lesson_text,
        result_time=utcnow(),
    )
    recommendation.outcome = outcome
    db.add(result)
    db.add(
        LearningEvent(
            recommendation_id=recommendation.id,
            event_type="RESULT_GRADED",
            sport=recommendation.sport,
            market_type=recommendation.market_type,
            analysis={
                "outcome": outcome,
                "stake": str(stake),
                "profit_loss": str(profit_loss),
                "actual_value": str(actual_value) if actual_value is not None else None,
                "bet_line": str(bet_line) if bet_line is not None else None,
                "miss_distance": str(miss_distance) if miss_distance is not None else None,
                "final_score": final_score,
                "auto_settled": True,
                "board_settled": "BOARD_SETTLED" in tags,
                "not_locked": "NOT_LOCKED" in tags,
                "process_outcome_class": "UNCLASSIFIED",
                "process_grade": "C",
                "variance_grade": "MEDIUM",
                "root_cause_tags": tags,
            },
        )
    )
    apply_micro_learning(db, result, recommendation)
    try:
        resolve_hive_outcome(
            db=db,
            source_recommendation_id=str(recommendation.id),
            outcome=outcome,
            verified=True,
            result_source="official_mlb",
            resolved_at=result.result_time,
        )
    except (RuntimeError, ValueError):
        pass
    db.flush()
    return {
        "status": "graded",
        "outcome": outcome,
        "final_score": final_score,
        "actual_value": actual_value,
        "detail": derived.get("detail"),
    }


def _final_box(feed: dict[str, Any]) -> dict[str, Any] | None:
    game_data = feed.get("gameData") or {}
    live_data = feed.get("liveData") or {}
    status = game_data.get("status") or {}
    abstract = str(status.get("abstractGameState") or "").lower()
    detailed = str(status.get("detailedState") or "").lower()
    if abstract not in {"final"} and "final" not in detailed and "game over" not in detailed:
        return None

    teams = game_data.get("teams") or {}
    home_team = (teams.get("home") or {}).get("name") or ""
    away_team = (teams.get("away") or {}).get("name") or ""
    linescore = live_data.get("linescore") or {}
    line_teams = linescore.get("teams") or {}
    home_runs = int((line_teams.get("home") or {}).get("runs") or 0)
    away_runs = int((line_teams.get("away") or {}).get("runs") or 0)

    # Fallback when linescore is thin but boxscore team batting totals exist.
    boxscore = (live_data.get("boxscore") or {}).get("teams") or {}
    if not home_runs and not away_runs:
        for side, key in (("home", "home_runs"), ("away", "away_runs")):
            batting = ((boxscore.get(side) or {}).get("teamStats") or {}).get("batting") or {}
            runs = batting.get("runs")
            if runs is not None:
                if side == "home":
                    home_runs = int(runs)
                else:
                    away_runs = int(runs)

    pitchers: dict[int, dict[str, Any]] = {}
    for side in ("home", "away"):
        players = (boxscore.get(side) or {}).get("players") or {}
        for record in players.values():
            person = record.get("person") or {}
            pid = person.get("id")
            if not isinstance(pid, int):
                continue
            pitching = ((record.get("stats") or {}).get("pitching")) or {}
            if not pitching:
                continue
            pitchers[pid] = {
                "id": pid,
                "name": person.get("fullName") or "",
                "strikeouts": int(pitching.get("strikeOuts") or 0),
                "innings_pitched": pitching.get("inningsPitched"),
                "side": side,
            }

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_runs": home_runs,
        "away_runs": away_runs,
        "total_runs": home_runs + away_runs,
        "final_score": f"{away_team} {away_runs} @ {home_team} {home_runs}",
        "pitchers": pitchers,
        "boxscore": boxscore,
    }


def _derive_outcome(
    recommendation: Recommendation, box: dict[str, Any]
) -> dict[str, Any] | None:
    market = (recommendation.market_type or "").lower()
    selection = recommendation.selection or ""
    selection_l = selection.lower()
    line = recommendation.line
    home = str(box["home_team"])
    away = str(box["away_team"])
    home_runs = int(box["home_runs"])
    away_runs = int(box["away_runs"])
    total = int(box["total_runs"])
    final_score = str(box["final_score"])

    if "moneyline" in market or market in {"h2h", "ml"} or selection_l.endswith(" ml"):
        team = _selected_team(selection, home, away, recommendation)
        if team is None:
            return None
        team_runs = home_runs if team == home else away_runs
        opp_runs = away_runs if team == home else home_runs
        if team_runs > opp_runs:
            outcome = "WIN"
        elif team_runs < opp_runs:
            outcome = "LOSS"
        else:
            outcome = "PUSH"
        return {
            "outcome": outcome,
            "actual_value": Decimal(team_runs - opp_runs),
            "final_score": final_score,
            "detail": f"{team} scored {team_runs}, opponent {opp_runs}.",
        }

    if "total" in market:
        if line is None:
            return None
        actual = Decimal(total)
        direction = "under" if "under" in selection_l else "over"
        if actual == line:
            outcome = "PUSH"
        elif direction == "over":
            outcome = "WIN" if actual > line else "LOSS"
        else:
            outcome = "WIN" if actual < line else "LOSS"
        return {
            "outcome": outcome,
            "actual_value": actual,
            "final_score": final_score,
            "detail": f"Game total {total} vs line {line} ({direction}).",
        }

    if "run_line" in market or "spread" in market or "handicap" in market:
        if line is None:
            return None
        team = _selected_team(selection, home, away, recommendation)
        if team is None:
            return None
        team_runs = home_runs if team == home else away_runs
        opp_runs = away_runs if team == home else home_runs
        covered = Decimal(team_runs) + Decimal(line)
        if covered == Decimal(opp_runs):
            outcome = "PUSH"
        elif covered > Decimal(opp_runs):
            outcome = "WIN"
        else:
            outcome = "LOSS"
        return {
            "outcome": outcome,
            "actual_value": Decimal(team_runs - opp_runs),
            "final_score": final_score,
            "detail": f"{team} {team_runs} with line {line:+} vs {opp_runs}.",
        }

    if "strikeout" in market or "pitcher" in market:
        if line is None:
            return None
        pitcher = _match_pitcher(recommendation, box)
        if pitcher is None:
            return {
                "outcome": "VOID",
                "actual_value": None,
                "final_score": final_score,
                "detail": "Pitcher strikeout total not found in final boxscore.",
            }
        actual = Decimal(int(pitcher["strikeouts"]))
        direction = "under" if "under" in selection_l else "over"
        if actual == line:
            outcome = "PUSH"
        elif direction == "over":
            outcome = "WIN" if actual > line else "LOSS"
        else:
            outcome = "WIN" if actual < line else "LOSS"
        return {
            "outcome": outcome,
            "actual_value": actual,
            "final_score": f"{final_score} • {pitcher['name']} {actual} K",
            "detail": f"{pitcher['name']} struck out {actual} vs line {line} ({direction}).",
        }

    return None


def _selected_team(
    selection: str,
    home: str,
    away: str,
    recommendation: Recommendation,
) -> str | None:
    snap = recommendation.snapshot or {}
    for key in ("home_team", "away_team"):
        name = snap.get(key)
        if isinstance(name, str) and name and name.lower() in selection.lower():
            return name
    for name in (home, away):
        if name and name.lower() in selection.lower():
            return name
    # Strip trailing market tokens and fuzzy-match last remaining words.
    cleaned = re.sub(
        r"\b(ml|moneyline|over|under|runs?|strikeouts?)\b",
        "",
        selection,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[+\-]?\d+(\.\d+)?", "", cleaned).strip(" -")
    for name in (home, away):
        if cleaned and cleaned.lower() in name.lower():
            return name
        if name and name.lower() in cleaned.lower():
            return name
    return None


def _match_pitcher(recommendation: Recommendation, box: dict[str, Any]) -> dict[str, Any] | None:
    player_key = recommendation.player_key or ""
    pitcher_id = None
    match = re.search(r"(\d+)$", player_key)
    if match:
        pitcher_id = int(match.group(1))
    pitchers: dict[int, dict[str, Any]] = box.get("pitchers") or {}
    if pitcher_id and pitcher_id in pitchers:
        return pitchers[pitcher_id]

    selection = recommendation.selection or ""
    name_guess = re.sub(
        r"\b(over|under)\b.*$",
        "",
        selection,
        flags=re.IGNORECASE,
    ).strip()
    for pitcher in pitchers.values():
        full = str(pitcher.get("name") or "")
        if full and full.lower() in selection.lower():
            return pitcher
        if name_guess and full and (
            name_guess.lower() in full.lower() or full.lower() in name_guess.lower()
        ):
            return pitcher
    return None


def _signed_margin(
    recommendation: Recommendation, actual_value: Decimal | None, bet_line: Decimal | None
) -> Decimal | None:
    if actual_value is None or bet_line is None:
        return None
    descriptor = f"{recommendation.market_type} {recommendation.selection}".lower()
    if "under" in descriptor:
        return bet_line - actual_value
    return actual_value - bet_line


def _american_profit(stake: Decimal, odds: int, outcome: str) -> Decimal:
    if stake <= 0:
        return Decimal("0.00")
    if outcome in {"PUSH", "VOID"}:
        return Decimal("0.00")
    if outcome == "LOSS":
        return (-stake).quantize(Decimal("0.01"))
    if odds > 0:
        return (stake * Decimal(odds) / Decimal(100)).quantize(Decimal("0.01"))
    return (stake * Decimal(100) / Decimal(abs(odds))).quantize(Decimal("0.01"))
