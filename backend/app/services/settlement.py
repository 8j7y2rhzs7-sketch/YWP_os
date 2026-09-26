"""Pull final scores/stats and settle recommendations for memory.

Grades:
1. Placed ticket legs (vault settle)
2. Board picks the user was shown (PLAY/LEAN/WATCH) even if never locked
3. Pick Sheet sportsbook-menu legs (incl. SKIP) so Hive can learn customer picks

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

from sqlalchemy import func, select
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
# Sheet sportsbook-menu legs are Hive-captured even on SKIP — settle them too.
SHEET_LEARNING_DECISIONS = frozenset({"PLAY", "LEAN", "WATCH", "SKIP", "REVIEW"})


@dataclass
class SettleDayResult:
    """Full Sync Scores payload: tickets + board games + Hive + EOD quality."""

    items: list[SettlementItem]
    hive_outcomes_mapped: int = 0
    eod_quality: dict[str, Any] | None = None

    @property
    def board_graded(self) -> int:
        return sum(
            1 for item in self.items if item.status == "graded" and not item.ticket_id
        )

    @property
    def ticket_legs_graded(self) -> int:
        return sum(
            1 for item in self.items if item.status == "graded" and bool(item.ticket_id)
        )


def _local_today(timezone_name: str | None = None) -> date:
    name = (timezone_name or "America/New_York").strip() or "America/New_York"
    try:
        return datetime.now(ZoneInfo(name)).date()
    except Exception:  # noqa: BLE001 — fall back if timezone string is invalid
        return datetime.now(ZoneInfo("America/New_York")).date()


def settle_user_day(
    db: Session, user_id: str, *, as_of: date | None = None, timezone_name: str | None = None
) -> SettleDayResult:
    """Sync Scores: read finals for locked tickets AND every board-shown pick.

    For each PLAY/LEAN/WATCH recommendation (even never locked), pull the game
    feed, map WIN/LOSS/PUSH/VOID when final, then resolve matching Hive captures
    so optimum-accuracy can advance from the full board universe.
    Future slate dates (tomorrow+) are ignored until their calendar day arrives.
    """
    from app.hive.models import HiveLearningEvent

    if as_of is None:
        if timezone_name is None:
            user = db.get(User, user_id)
            timezone_name = user.timezone if user else "America/New_York"
        as_of = _local_today(timezone_name)

    pending_before = int(
        db.scalar(
            select(func.count())
            .select_from(HiveLearningEvent)
            .where(HiveLearningEvent.outcome.is_(None))
        )
        or 0
    )
    items = settle_user_placed_tickets(db, user_id, as_of=as_of)
    items.extend(settle_user_board_recommendations(db, user_id, as_of=as_of))
    sync_hive_outcomes_for_graded(db, user_id)
    pending_after = int(
        db.scalar(
            select(func.count())
            .select_from(HiveLearningEvent)
            .where(HiveLearningEvent.outcome.is_(None))
        )
        or 0
    )
    mapped = max(0, pending_before - pending_after)
    coverage = _settlement_coverage_snapshot(items)
    if mapped > 0 or coverage.get("gaps"):
        from app.hive.service import record_hive_progress_report

        record_hive_progress_report(
            db=db,
            trigger="settle_day",
            extra={
                "hive_outcomes_mapped": mapped,
                "settled_items": len(items),
                "settlement_coverage": coverage,
            },
        )
        # Second loop: after fresh evidence lands, Hive invents/tests tactics.
        from app.hive.config import settings as hive_settings
        from app.hive.self_improve import run_self_improvement_cycle

        if hive_settings.self_improve_enabled and (
            mapped >= int(hive_settings.self_improve_min_mapped) or coverage.get("gaps")
        ):
            run_self_improvement_cycle(
                db=db,
                trigger="settle_day",
            )

    # End-of-day quality: called vs uncalled board, missed winners, packaging gap.
    eod_quality: dict[str, Any] | None = None
    try:
        from app.services.eod_quality import run_eod_quality_pass

        eod_report = run_eod_quality_pass(db, user_id, slate_date=as_of)
        eod_quality = eod_report.to_dict()
        db.flush()
    except Exception:  # noqa: BLE001 — settle must still return grades if EOD fails
        logger.exception("EOD quality pass failed for user=%s date=%s", user_id, as_of)
        eod_quality = None

    return SettleDayResult(
        items=items,
        hive_outcomes_mapped=mapped,
        eod_quality=eod_quality,
    )

def _settlement_coverage_snapshot(items: list[SettlementItem]) -> dict[str, Any]:
    """Summarize which sports/markets settled vs still need engine coverage."""
    graded = [item for item in items if item.status == "graded"]
    pending = [item for item in items if item.status == "pending"]
    gaps = [
        item
        for item in items
        if item.status == "skipped"
        and item.detail
        and (
            "does not support" in item.detail.lower()
            or "no settlement rule" in item.detail.lower()
            or "no odds-scores settlement" in item.detail.lower()
        )
    ]
    return {
        "graded": len(graded),
        "pending": len(pending),
        "gaps": [
            {
                "selection": item.selection,
                "detail": item.detail,
            }
            for item in gaps[:25]
        ],
        "gap_count": len(gaps),
        "supported_engines": [
            "mlb_stats_api",
            "espn_site_api",
            "the_odds_api_scores",
        ],
    }


def sync_hive_outcomes_for_graded(db: Session, user_id: str) -> int:
    """Map graded board/ticket results onto pending Hive captures for this user.

    Sync must settle the same board/Sheet universe Hive captured — not only
    locked tickets — so optimum-accuracy can advance from live evidence.
    """
    from app.hive.models import HiveLearningEvent

    pending = list(
        db.scalars(
            select(HiveLearningEvent).where(HiveLearningEvent.outcome.is_(None))
        ).all()
    )
    if not pending:
        return 0

    by_rec = {event.source_recommendation_id: event for event in pending}
    recommendations = list(
        db.scalars(
            select(Recommendation)
            .where(
                Recommendation.created_by_user_id == user_id,
                Recommendation.id.in_(list(by_rec.keys())),
                Recommendation.outcome.isnot(None),
            )
            .options(joinedload(Recommendation.result))
        ).unique()
    )
    updated = 0
    for recommendation in recommendations:
        event = by_rec.get(str(recommendation.id))
        if event is None or recommendation.outcome is None:
            continue
        result = recommendation.result
        try:
            resolve_hive_outcome(
                db=db,
                source_recommendation_id=str(recommendation.id),
                outcome=str(recommendation.outcome),
                verified=True,
                result_source=(
                    "official_mlb"
                    if result is not None
                    else "board_sync"
                ),
                resolved_at=getattr(result, "result_time", None) or utcnow(),
            )
            updated += 1
        except (RuntimeError, ValueError):
            continue
    if updated:
        db.commit()
    return updated


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


def _is_sheet_menu_recommendation(recommendation: Recommendation) -> bool:
    """True when this row came from Pick Sheet sportsbook menu (not Run slate)."""
    if (recommendation.data_source or "") == "THE_ODDS_API_BOARD":
        return True
    snap = recommendation.snapshot or {}
    if snap.get("data_source") == "THE_ODDS_API_BOARD":
        return True
    reasons = snap.get("reason_codes") or recommendation.reason_codes or []
    return "SPORTSBOOK_MENU" in reasons


def settle_user_board_recommendations(
    db: Session, user_id: str, *, as_of: date | None = None
) -> list[SettlementItem]:
    """Grade ungraded board + Sheet-menu picks even if never locked into a ticket.

    Locked tickets still matter for exposure/P&L, but every pick the protocol
    surfaced (and every Sheet sportsbook-menu leg the customer checked,
    including SKIP) is training data for the next day.
    Future slate dates are skipped until their calendar day arrives.
    """
    query = (
        select(Recommendation)
        .where(
            Recommendation.created_by_user_id == user_id,
            Recommendation.outcome.is_(None),
            Recommendation.decision.in_(SHEET_LEARNING_DECISIONS),
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
        # Official Run/board: PLAY/LEAN/WATCH only. Sheet menu: all decisions.
        if recommendation.decision not in BOARD_DECISIONS and not _is_sheet_menu_recommendation(
            recommendation
        ):
            continue
        sheet_menu = _is_sheet_menu_recommendation(recommendation)
        tags = ["BOARD_SETTLED", "NOT_LOCKED"]
        if sheet_menu:
            tags.append("SHEET_MENU_SETTLED")
        lesson = (
            "Auto-settled Pick Sheet sportsbook-menu leg (incl. SKIP). "
            "Outcome trains Hive customer-selection calibration."
            if sheet_menu
            else (
                "Auto-settled board pick (never locked). "
                "Outcome still trains next-day weights."
            )
        )
        try:
            graded = _grade_recommendation(
                db,
                recommendation,
                stake=Decimal("0.00"),
                extra_tags=tags,
                lesson=lesson,
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

    if recommendation.data_source in {"YWP_DEMO_PROVIDER", "EXTERNAL_BOOK_LOG"}:
        return {"status": "skipped", "detail": "Demo/external picks are graded manually."}

    sport = (recommendation.sport or "").lower()
    if sport == "mlb":
        mlb_result = _grade_mlb_recommendation(
            db,
            recommendation,
            stake=stake,
            extra_tags=extra_tags,
            lesson=lesson,
        )
        if mlb_result.get("status") != "skipped":
            return mlb_result
        # Team markets: Odds completed scores when Stats API pk is missing.
        odds_result = _grade_odds_scores_recommendation(
            db,
            recommendation,
            stake=stake,
            extra_tags=extra_tags,
            lesson=lesson,
        )
        if odds_result.get("status") != "skipped":
            return odds_result
        detail = mlb_result.get("detail") or odds_result.get("detail") or (
            f"Automatic settlement does not support MLB {recommendation.market_type}."
        )
        _record_settlement_gap(db, recommendation, detail=str(detail))
        return {"status": "skipped", "detail": str(detail)}

    from app.services.espn_provider import ESPN_SPORT_PATHS, resolve_espn_path

    snap = recommendation.snapshot or {}
    league_hint = str(
        snap.get("league")
        or snap.get("odds_key")
        or snap.get("competition")
        or recommendation.league
        or ""
    )
    espn_result: dict[str, Any] | None = None
    if sport in ESPN_SPORT_PATHS or resolve_espn_path(sport, league_hint=league_hint):
        espn_result = _grade_espn_recommendation(
            db,
            recommendation,
            stake=stake,
            extra_tags=extra_tags,
            lesson=lesson,
            league_hint=league_hint,
        )
        if espn_result.get("status") != "skipped":
            return espn_result
        # Fall through to Odds scores for team markets when ESPN can't map a prop.

    odds_result = _grade_odds_scores_recommendation(
        db,
        recommendation,
        stake=stake,
        extra_tags=extra_tags,
        lesson=lesson,
    )
    if odds_result.get("status") != "skipped":
        return odds_result

    detail = (espn_result or {}).get("detail") or odds_result.get("detail") or (
        f"Automatic settlement does not support {sport.upper()} {recommendation.market_type}."
    )
    _record_settlement_gap(db, recommendation, detail=str(detail))
    return {
        "status": "skipped",
        "detail": str(detail),
    }


def _grade_mlb_recommendation(
    db: Session,
    recommendation: Recommendation,
    *,
    stake: Decimal,
    extra_tags: list[str] | None = None,
    lesson: str | None = None,
) -> dict[str, Any]:
    game_pk = _game_pk(recommendation)
    if game_pk is None:
        try:
            from app.services.mlb_provider import find_game_pk_for_teams

            game_pk = find_game_pk_for_teams(
                recommendation.slate_date,
                home_team=recommendation.home_team,
                away_team=recommendation.away_team,
                event_name=recommendation.event_name,
            )
        except Exception:  # noqa: BLE001 — settle must continue without schedule lookup
            logger.exception(
                "MLB schedule game_pk lookup failed for recommendation=%s",
                recommendation.id,
            )
            game_pk = None
        if game_pk is not None:
            # Persist so later Hive sync / re-settle does not re-query.
            snap = dict(recommendation.snapshot or {})
            snap["game_pk"] = game_pk
            snap["mlb_game_pk"] = game_pk
            recommendation.snapshot = snap
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
    return _persist_auto_grade(
        db,
        recommendation,
        derived=derived,
        stake=stake,
        extra_tags=extra_tags,
        lesson=lesson
        or "Auto-settled from MLB final score/stats. Complete process audit when ready.",
        result_source="official_mlb",
    )


def _grade_espn_recommendation(
    db: Session,
    recommendation: Recommendation,
    *,
    stake: Decimal,
    extra_tags: list[str] | None = None,
    lesson: str | None = None,
    league_hint: str | None = None,
) -> dict[str, Any]:
    """Settle ESPN-backed sports from official finals (all app ESPN leagues)."""
    from app.services.board_metrics import parse_event_teams
    from app.services.espn_provider import (
        get_event_summary,
        match_odds_event_to_espn,
        parse_boxscore_player_stats,
    )

    sport = (recommendation.sport or "").lower()
    snap = recommendation.snapshot or {}
    home = str(snap.get("home_team") or recommendation.home_team or "")
    away = str(snap.get("away_team") or recommendation.away_team or "")
    if not home or not away:
        parsed_away, parsed_home = parse_event_teams(recommendation.event_name or "")
        home = home or (parsed_home or "")
        away = away or (parsed_away or "")
    if not home or not away:
        return {
            "status": "skipped",
            "detail": "Missing home/away teams for ESPN settlement match.",
        }

    game = match_odds_event_to_espn(
        sport,
        recommendation.slate_date,
        home_team=home,
        away_team=away,
        league_hint=league_hint,
    )
    if game is None:
        return {
            "status": "pending",
            "detail": "ESPN final not matched yet for this event.",
        }
    if not game.get("completed"):
        return {
            "status": "pending",
            "detail": f"Game not final yet ({game.get('status') or 'in progress'}).",
        }

    home_score = game.get("home_score")
    away_score = game.get("away_score")
    if home_score is None or away_score is None:
        return {
            "status": "pending",
            "detail": "ESPN final is marked complete but scores are missing.",
        }

    box = {
        "home_team": str(game.get("home_team") or home),
        "away_team": str(game.get("away_team") or away),
        "home_runs": int(home_score),
        "away_runs": int(away_score),
        "total_runs": int(home_score) + int(away_score),
        "final_score": f"{game.get('away_team') or away} {int(away_score)} @ "
        f"{game.get('home_team') or home} {int(home_score)}",
        "pitchers": [],
        "batters": [],
    }

    market = (recommendation.market_type or "").lower()
    if _is_player_prop_market(market, recommendation.selection or ""):
        summary = get_event_summary(
            sport,
            str(game.get("event_id") or ""),
            league_hint=league_hint,
            espn_path=str(game.get("espn_path") or "") or None,
        )
        players = parse_boxscore_player_stats(summary)
        derived = _derive_espn_player_prop(recommendation, box, players)
    else:
        derived = _derive_outcome(recommendation, box)

    if derived is None:
        return {
            "status": "skipped",
            "detail": f"No settlement rule for market {recommendation.market_type}.",
        }
    return _persist_auto_grade(
        db,
        recommendation,
        derived=derived,
        stake=stake,
        extra_tags=extra_tags,
        lesson=lesson
        or "Auto-settled from ESPN final score/stats. Complete process audit when ready.",
        result_source="official_espn",
    )


def _grade_odds_scores_recommendation(
    db: Session,
    recommendation: Recommendation,
    *,
    stake: Decimal,
    extra_tags: list[str] | None = None,
    lesson: str | None = None,
) -> dict[str, Any]:
    """Universal team-market fallback via The Odds API completed scores (incl. KBO)."""
    market = (recommendation.market_type or "").lower()
    selection_l = (recommendation.selection or "").lower()
    if _is_player_prop_market(market, recommendation.selection or ""):
        return {
            "status": "skipped",
            "detail": "Odds scores fallback covers team markets only (ML/spread/total).",
        }
    if not (
        "moneyline" in market
        or market in {"h2h", "ml"}
        or selection_l.endswith(" ml")
        or "total" in market
        or "spread" in market
        or "run_line" in market
        or "handicap" in market
    ):
        return {
            "status": "skipped",
            "detail": f"No Odds-scores settlement rule for market {recommendation.market_type}.",
        }

    from app.services.board_metrics import parse_event_teams
    from app.services.odds_provider import (
        APP_SPORT_TO_ODDS_KEY,
        get_scores,
        odds_keys_for_app_sport,
        _norm_team,
    )

    sport = (recommendation.sport or "").lower()
    snap = recommendation.snapshot or {}
    home = str(snap.get("home_team") or recommendation.home_team or "")
    away = str(snap.get("away_team") or recommendation.away_team or "")
    if not home or not away:
        parsed_away, parsed_home = parse_event_teams(recommendation.event_name or "")
        home = home or (parsed_home or "")
        away = away or (parsed_away or "")
    if not home or not away:
        return {
            "status": "skipped",
            "detail": "Missing home/away teams for Odds scores settlement.",
        }

    keys = odds_keys_for_app_sport(sport) or []
    primary = APP_SPORT_TO_ODDS_KEY.get(sport)
    if primary and primary not in keys:
        keys = [primary, *keys]
    if not keys:
        return {
            "status": "skipped",
            "detail": f"No Odds sport key mapped for {sport.upper()}.",
        }

    home_n = _norm_team(home)
    away_n = _norm_team(away)
    matched = None
    for odds_key in keys:
        for event in get_scores(odds_key, days_from=3) or []:
            if not event.get("completed"):
                continue
            scores = {
                _norm_team(str(row.get("name") or "")): row.get("score")
                for row in (event.get("scores") or [])
                if isinstance(row, dict)
            }
            home_score = scores.get(home_n)
            away_score = scores.get(away_n)
            # Also try event home/away team fields.
            if home_score is None or away_score is None:
                event_home = _norm_team(str(event.get("home_team") or ""))
                event_away = _norm_team(str(event.get("away_team") or ""))
                if event_home == home_n and event_away == away_n:
                    home_score = scores.get(event_home)
                    away_score = scores.get(event_away)
            if home_score is None or away_score is None:
                continue
            try:
                matched = {
                    "home_team": home,
                    "away_team": away,
                    "home_runs": int(float(home_score)),
                    "away_runs": int(float(away_score)),
                    "total_runs": int(float(home_score)) + int(float(away_score)),
                    "final_score": f"{away} {int(float(away_score))} @ {home} {int(float(home_score))}",
                    "pitchers": [],
                    "batters": [],
                    "odds_key": odds_key,
                }
            except (TypeError, ValueError):
                continue
            break
        if matched:
            break

    if matched is None:
        return {
            "status": "pending",
            "detail": "Odds completed score not found yet for this event.",
        }

    derived = _derive_outcome(recommendation, matched)
    if derived is None:
        return {
            "status": "skipped",
            "detail": f"No settlement rule for market {recommendation.market_type}.",
        }
    return _persist_auto_grade(
        db,
        recommendation,
        derived=derived,
        stake=stake,
        extra_tags=extra_tags,
        lesson=lesson
        or "Auto-settled from Odds API completed scores. Complete process audit when ready.",
        result_source="odds_scores",
    )


def _is_player_prop_market(market: str, selection: str) -> bool:
    market_l = (market or "").lower()
    selection_l = (selection or "").lower()
    if market_l.startswith("player_") or market_l.startswith("batter_") or market_l.startswith(
        "pitcher_"
    ):
        return True
    tokens = (
        "points",
        "rebounds",
        "assists",
        "threes",
        "three",
        "pra",
        "steals",
        "blocks",
        "turnovers",
        "passing",
        "rushing",
        "receiving",
        "receptions",
        "yards",
        "touchdown",
        "strikeout",
        "hits",
        "rbi",
        "shots",
        "saves",
        "goals",
        "anytime",
    )
    return any(token in market_l or token in selection_l for token in tokens)


def _derive_espn_player_prop(
    recommendation: Recommendation,
    box: dict[str, Any],
    players: list[dict[str, Any]],
) -> dict[str, Any] | None:
    line = recommendation.line
    if line is None:
        return None
    selection = recommendation.selection or ""
    selection_l = selection.lower()
    market = (recommendation.market_type or "").lower()
    player_name = _player_name_from_selection(selection)
    if not player_name:
        return None

    from app.services.espn_provider import _name_overlap

    best = None
    best_score = 0
    for row in players:
        score = _name_overlap(player_name, str(row.get("name") or ""))
        if score > best_score:
            best_score = score
            best = row
    if best is None or best_score < 2:
        return {
            "outcome": "VOID",
            "actual_value": None,
            "final_score": box.get("final_score"),
            "detail": f"Player '{player_name}' not found in ESPN final boxscore.",
        }

    stat_key, label = _espn_stat_for_market(
        market,
        selection_l,
        sport=str((recommendation.sport or "")).lower(),
    )
    raw = _lookup_player_stat(
        best,
        market,
        selection_l,
        preferred=stat_key,
        sport=str((recommendation.sport or "")).lower(),
    )
    if raw is None:
        return {
            "outcome": "VOID",
            "actual_value": None,
            "final_score": box.get("final_score"),
            "detail": f"{best.get('name')} final boxscore missing {label}.",
        }
    actual = Decimal(str(raw))
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
        "final_score": f"{box.get('final_score')} • {best.get('name')} {actual} {label}",
        "detail": f"{best.get('name')} had {actual} {label} vs line {line} ({direction}).",
    }


def _lookup_player_stat(
    player: dict[str, Any],
    market: str,
    selection_l: str,
    *,
    preferred: str,
    sport: str = "",
) -> float | None:
    text = f"{market} {selection_l}".lower()
    if "anytime" in text and "touchdown" in text:
        total = 0.0
        found = False
        for key in ("RUSH_TD", "REC_TD", "PASS_TD", "TD"):
            value = player.get(key)
            if value is not None:
                total += float(value)
                found = True
        return total if found else None

    candidates = [preferred]
    # Friendly aliases across sports / group prefixes.
    aliases = {
        "PASS_YDS": ["PASS_YDS", "YDS"],
        "RUSH_YDS": ["RUSH_YDS", "YDS"],
        "REC_YDS": ["REC_YDS", "YDS"],
        "PASS_TD": ["PASS_TD", "TD"],
        "RUSH_TD": ["RUSH_TD", "TD"],
        "REC_TD": ["REC_TD", "TD"],
        "PASS_INT": ["PASS_INT", "INT"],
        "REC": ["REC", "REC_REC"],
        "RUSH_CAR": ["RUSH_CAR", "CAR"],
        "REC_TGTS": ["REC_TGTS", "TGTS"],
        "SOG": ["SOG", "S", "SHOTS"],
        "POINTS": ["POINTS", "G+A", "PTS"],
        "AST": ["AST", "A"],
        "G": ["G", "GOALS"],
        "PITCH_K": ["PITCH_K", "K", "SO"],
        "BAT_H": ["BAT_H", "H", "HITS"],
        "BAT_RBI": ["BAT_RBI", "RBI"],
    }
    candidates.extend(aliases.get(preferred, []))
    for key in candidates:
        value = player.get(key)
        if value is not None:
            return float(value)
    return None


def _player_name_from_selection(selection: str) -> str:
    text = selection.strip()
    for token in (" over ", " under ", " Over ", " Under "):
        if token in text:
            return text.split(token, 1)[0].strip()
    # Fallback: strip trailing line fragments.
    return re.split(r"\s+[+-]?\d", text, maxsplit=1)[0].strip()


def _espn_stat_for_market(
    market: str, selection_l: str, *, sport: str = ""
) -> tuple[str, str]:
    """Map market/selection language → ESPN boxscore keys (multi-sport)."""
    text = f"{market} {selection_l}".lower()
    sport_l = (sport or "").lower()

    # Football
    if sport_l in {"nfl", "ncaaf"} or any(
        token in text for token in ("pass", "rush", "receiv", "reception", "touchdown")
    ):
        if "pass" in text and ("yard" in text or "yds" in text):
            return "PASS_YDS", "PASS YDS"
        if "rush" in text and ("yard" in text or "yds" in text):
            return "RUSH_YDS", "RUSH YDS"
        if ("receiv" in text or "reception" in text) and ("yard" in text or "yds" in text):
            return "REC_YDS", "REC YDS"
        if "reception" in text:
            return "REC", "REC"
        if "pass" in text and ("td" in text or "touchdown" in text):
            return "PASS_TD", "PASS TD"
        if "rush" in text and ("td" in text or "touchdown" in text):
            return "RUSH_TD", "RUSH TD"
        if "receiv" in text and ("td" in text or "touchdown" in text):
            return "REC_TD", "REC TD"
        if "anytime" in text and "touchdown" in text:
            return "RUSH_TD", "TD"
        if "interception" in text:
            return "PASS_INT", "INT"
        if "target" in text:
            return "REC_TGTS", "TGTS"
        if "carry" in text or "carries" in text:
            return "RUSH_CAR", "CAR"

    # Hockey
    if sport_l == "nhl":
        if "save" in text:
            return "SV", "SV"
        if "shot" in text:
            return "SOG", "SOG"
        if "goalie" in text and "goal" in text:
            return "GA", "GA"
        if "point" in text:
            return "POINTS", "PTS"
        if "assist" in text:
            return "A", "A"
        if "goal" in text:
            return "G", "G"

    # Soccer
    if sport_l in {"soccer", "mls", "epl"}:
        if "shot" in text:
            return "SOG", "SOT"
        if "goal" in text or "scorer" in text:
            return "G", "G"
        if "assist" in text:
            return "A", "A"

    # Basketball / generic
    if "pra" in text or "points_rebounds_assists" in text:
        return "PRA", "PRA"
    if "rebounds" in text:
        return "REB", "REB"
    if "assists" in text:
        return "AST", "AST"
    if "three" in text or "threes" in text or "3pt" in text or "3-pt" in text:
        return "3PT", "3PT"
    if "steals" in text:
        return "STL", "STL"
    if "blocks" in text:
        return "BLK", "BLK"
    if "turnover" in text:
        return "TO", "TO"
    if "points" in text:
        return "PTS", "PTS"

    if "strikeout" in text:
        return "PITCH_K", "K"
    if "hits" in text:
        return "BAT_H", "H"
    if "rbi" in text:
        return "BAT_RBI", "RBI"

    return "PTS", "PTS"


def _record_settlement_gap(
    db: Session,
    recommendation: Recommendation,
    *,
    detail: str,
) -> None:
    """Persist unsupported settle markets so Hive self-improve can close gaps."""
    try:
        db.add(
            LearningEvent(
                recommendation_id=recommendation.id,
                event_type="SETTLEMENT_COVERAGE_GAP",
                sport=recommendation.sport,
                market_type=recommendation.market_type,
                analysis={
                    "detail": detail,
                    "selection": recommendation.selection,
                    "sport": recommendation.sport,
                    "market_type": recommendation.market_type,
                    "slate_date": str(recommendation.slate_date),
                },
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001 — never block settle batch
        logger.exception("Failed to record settlement coverage gap")


def _persist_auto_grade(
    db: Session,
    recommendation: Recommendation,
    *,
    derived: dict[str, Any],
    stake: Decimal,
    extra_tags: list[str] | None,
    lesson: str,
    result_source: str,
) -> dict[str, Any]:
    outcome = derived["outcome"]
    actual_value = derived.get("actual_value")
    final_score = derived.get("final_score")
    bet_line = recommendation.line
    miss_distance = _signed_margin(recommendation, actual_value, bet_line)
    profit_loss = _american_profit(stake, recommendation.american_odds, outcome)
    tags = list(dict.fromkeys(["AUTO_SETTLED", *(extra_tags or [])]))

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
        lesson=lesson,
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
                "result_source": result_source,
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
            result_source=result_source,
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
    batters: dict[int, dict[str, Any]] = {}
    for side in ("home", "away"):
        players = (boxscore.get(side) or {}).get("players") or {}
        for record in players.values():
            person = record.get("person") or {}
            pid = person.get("id")
            if not isinstance(pid, int):
                continue
            stats = record.get("stats") or {}
            pitching = stats.get("pitching") or {}
            if pitching:
                pitchers[pid] = {
                    "id": pid,
                    "name": person.get("fullName") or "",
                    "strikeouts": int(pitching.get("strikeOuts") or 0),
                    "outs": int(pitching.get("outs") or 0),
                    "hits_allowed": int(pitching.get("hits") or 0),
                    "earned_runs": int(pitching.get("earnedRuns") or 0),
                    "walks": int(pitching.get("baseOnBalls") or 0),
                    "innings_pitched": pitching.get("inningsPitched"),
                    "side": side,
                }
            batting = stats.get("batting") or {}
            if batting:
                hits = int(batting.get("hits") or 0)
                runs = int(batting.get("runs") or 0)
                rbi = int(batting.get("rbi") or 0)
                hr = int(batting.get("homeRuns") or 0)
                tb = int(batting.get("totalBases") or 0)
                batters[pid] = {
                    "id": pid,
                    "name": person.get("fullName") or "",
                    "hits": hits,
                    "runs": runs,
                    "rbi": rbi,
                    "home_runs": hr,
                    "total_bases": tb,
                    "hits_runs_rbis": hits + runs + rbi,
                    "stolen_bases": int(batting.get("stolenBases") or 0),
                    "walks": int(batting.get("baseOnBalls") or 0),
                    "at_bats": int(batting.get("atBats") or 0),
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
        "batters": batters,
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

    if "strikeout" in market and "batter" not in market:
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

    if "pitcher" in market:
        if line is None:
            return None
        pitcher = _match_pitcher(recommendation, box)
        if pitcher is None:
            return {
                "outcome": "VOID",
                "actual_value": None,
                "final_score": final_score,
                "detail": "Pitcher prop total not found in final boxscore.",
            }
        if "outs" in market:
            actual = Decimal(int(pitcher.get("outs") or 0))
            label = "outs"
        elif "earned" in market:
            actual = Decimal(int(pitcher.get("earned_runs") or 0))
            label = "ER"
        elif "walks" in market:
            actual = Decimal(int(pitcher.get("walks") or 0))
            label = "BB"
        else:
            actual = Decimal(int(pitcher.get("hits_allowed") or 0))
            label = "HA"
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
            "final_score": f"{final_score} • {pitcher['name']} {actual} {label}",
            "detail": f"{pitcher['name']} {label} {actual} vs line {line} ({direction}).",
        }

    if (
        "hits" in market
        or "rbi" in market
        or "runs" in market
        or "hr" in market
        or "bases" in market
        or "hrr" in market
        or "stolen" in market
        or "walks" in market
    ):
        if line is None:
            return None
        batter = _match_batter(recommendation, box)
        if batter is None:
            return {
                "outcome": "VOID",
                "actual_value": None,
                "final_score": final_score,
                "detail": "Batter prop total not found in final boxscore.",
            }
        stat_key, label = _batter_stat_for_market(market, selection_l)
        actual = Decimal(int(batter.get(stat_key) or 0))
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
            "final_score": f"{final_score} • {batter['name']} {actual} {label}",
            "detail": f"{batter['name']} had {actual} {label} vs line {line} ({direction}).",
        }

    return None


def _batter_stat_for_market(market: str, selection_l: str) -> tuple[str, str]:
    if "hrr" in market or "hits_runs_rbis" in market or "hits+runs" in selection_l:
        return "hits_runs_rbis", "H+R+RBI"
    if "total_bases" in market or "total bases" in selection_l:
        return "total_bases", "TB"
    if "home_run" in market or "hr" in market or "home runs" in selection_l:
        return "home_runs", "HR"
    if "rbi" in market:
        return "rbi", "RBI"
    if "stolen" in market or "sb" in market:
        return "stolen_bases", "SB"
    if "walks" in market:
        return "walks", "BB"
    if "runs" in market and "hits" not in market:
        return "runs", "R"
    return "hits", "H"


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


def _match_batter(recommendation: Recommendation, box: dict[str, Any]) -> dict[str, Any] | None:
    player_key = recommendation.player_key or ""
    batter_id = None
    match = re.search(r"(\d+)$", player_key)
    if match:
        batter_id = int(match.group(1))
    batters: dict[int, dict[str, Any]] = box.get("batters") or {}
    if batter_id and batter_id in batters:
        return batters[batter_id]

    selection = recommendation.selection or ""
    name_guess = re.sub(
        r"\b(over|under)\b.*$",
        "",
        selection,
        flags=re.IGNORECASE,
    ).strip()
    name_guess = re.sub(r"\bhits?\b.*$", "", name_guess, flags=re.IGNORECASE).strip()
    for batter in batters.values():
        full = str(batter.get("name") or "")
        if full and full.lower() in selection.lower():
            return batter
        if name_guess and full and (
            name_guess.lower() in full.lower() or full.lower() in name_guess.lower()
        ):
            return batter
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
