"""Two pulls before anyone opens the app.

Pull 1 is the Eastern-time schedule from ESPN and the MLB Stats API. It does
not call The Odds API. Pull 2 is one priced slate for the sports that have
games, timed off the earliest start and a per-sport lead that moves when past
pulls were early or late.

Approved plays are engine PLAY and LEAN rows. They are copied onto the signed-in
user when the Ready board opens so a saved ticket still belongs to that user.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    DayPrepClaim,
    DayPrepDay,
    DayPrepGame,
    DayPrepLead,
    DayPrepPlay,
    Recommendation,
)
from app.schemas import CandidateInput, ReadyBoardResponse, RecommendationOut, RiskProfile
from app.services.decision_engine import decision_engine, money
from app.services.ticket_builder import build_cards, preview_custom_card

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
DEFAULT_LEAD_MINUTES = 75
MIN_LEAD_MINUTES = 25
MAX_LEAD_MINUTES = 180
LEAD_LATER_STEP = 15
LEAD_EARLIER_STEP = 10
PRICING_STALE = timedelta(minutes=20)
MAX_PLAYS_PER_SPORT = 24
MAX_PROP_CANDIDATES = 60
PREP_SPORTS = ("nfl", "nba", "wnba", "nhl", "mlb", "ncaaf", "ncaab")
APPROVED = {"PLAY", "LEAN"}
_FINISHED = ("final", "postpon", "cancel")
_NICK_SKIP = {"fc", "the", "de", "club"}

ScheduleLoader = Callable[[date], list["ScheduledGame"]]
SlateLoader = Callable[[str, date], list[CandidateInput]]
Grader = Callable[[Session, list[CandidateInput]], list[dict[str, Any]]]

_advance_lock = threading.Lock()


@dataclass(frozen=True)
class ScheduledGame:
    sport: str
    event_id: str
    event_name: str
    home_team: str
    away_team: str
    commence_time: datetime


def learn_next_lead(current: int, completeness: float, minutes_before: float) -> int:
    """Move the next priced pull toward the minute that actually had the board.

    Low completeness with time still on the clock means the pull was early:
    wait longer next time (smaller lead). A full board cut close to tip means
    start a little earlier so the list is waiting.
    """
    lead = min(MAX_LEAD_MINUTES, max(MIN_LEAD_MINUTES, int(current)))
    if completeness < 0.5 and minutes_before > MIN_LEAD_MINUTES + LEAD_LATER_STEP:
        return max(MIN_LEAD_MINUTES, lead - LEAD_LATER_STEP)
    if completeness >= 0.85 and minutes_before < 40:
        return min(MAX_LEAD_MINUTES, lead + LEAD_EARLIER_STEP)
    return lead


def binding_pull_time(
    games: list[ScheduledGame],
    leads: dict[str, int],
    slate_date: date,
) -> tuple[datetime | None, int | None, str | None]:
    """One priced pull: the earliest start minus that sport's learned lead."""
    if not games:
        return None, None, None
    best_at: datetime | None = None
    best_lead: int | None = None
    best_sport: str | None = None
    for game in games:
        lead = int(leads.get(game.sport, DEFAULT_LEAD_MINUTES))
        target = game.commence_time - timedelta(minutes=lead)
        if best_at is None or target < best_at:
            best_at = target
            best_lead = lead
            best_sport = game.sport
    if best_at is None:
        return None, None, None
    floor = datetime.combine(slate_date, datetime.min.time(), tzinfo=ET) + timedelta(minutes=10)
    if best_at < floor:
        best_at = floor
    return best_at, best_lead, best_sport


def coverage(games: list[ScheduledGame], candidates: list[CandidateInput]) -> float:
    """Share of scheduled games that have a real price in the candidate list.

    ESPN ids and Odds ids do not match, so this joins on team nicknames.
    Prop sports that only have full-game prices stay below 0.5 so the next
    pull waits until player markets are up, while a complete board stays high.
    """
    if not games:
        return 1.0
    priced = [item for item in candidates if _is_priced(item)]
    if not priced:
        return 0.0
    covered = 0
    for game in games:
        if any(_covers(item.event_name, game.home_team, game.away_team) for item in priced):
            covered += 1
    ratio = covered / len(games)
    prop_sport = games[0].sport in {"nba", "wnba", "nfl", "ncaaf", "mlb"}
    has_props = any(str(item.market_type).startswith("player_") for item in priced)
    if prop_sport and ratio >= 0.5 and not has_props:
        return min(ratio, 0.45)
    return ratio


def advance_day_prep(
    db: Session,
    *,
    now: datetime | None = None,
    schedule_loader: ScheduleLoader | None = None,
    slate_loader: SlateLoader | None = None,
    grader: Grader | None = None,
) -> dict[str, Any]:
    """Run whichever pull is due. Safe to call on a timer and on app open."""
    if not settings.day_prep_enabled:
        return {"status": "disabled", "notice": "Day prep is off."}
    moment = _aware(now or datetime.now(UTC))
    with _advance_lock:
        return _advance_locked(
            db,
            now=moment,
            schedule_loader=schedule_loader or default_schedule,
            slate_loader=slate_loader or default_priced_slate,
            grader=grader or grade_candidates,
        )


def kick_day_prep() -> None:
    """Start a catch-up pull without holding the request open."""

    def _run() -> None:
        db = SessionLocal()
        try:
            advance_day_prep(db)
        except Exception:
            logger.exception("day prep catch-up failed")
            db.rollback()
        finally:
            db.close()

    threading.Thread(target=_run, name="ywp-day-prep", daemon=True).start()


def prep_work_due(db: Session, now: datetime | None = None) -> bool:
    if not settings.day_prep_enabled:
        return False
    moment = _aware(now or datetime.now(UTC))
    day = db.get(DayPrepDay, slate_date_for(moment))
    if day is None or day.schedule_pulled_at is None:
        return True
    if day.status == "pricing" and _pricing_fresh(day, moment):
        return False
    if day.status in {"priced", "missed", "no_games"}:
        return False
    if day.pull2_at is not None and moment < _aware(day.pull2_at):
        return False
    if day.status == "waiting_for_prices" and not settings.odds_api_key and not settings.demo_mode:
        return False
    if day.priced_pulled_at is None:
        return True
    return day.status == "pricing" and not _pricing_fresh(day, moment)


def ready_board_for_user(
    db: Session,
    user_id: str,
    *,
    now: datetime | None = None,
) -> ReadyBoardResponse:
    moment = _aware(now or datetime.now(UTC))
    slate_date = slate_date_for(moment)
    if prep_work_due(db, moment):
        kick_day_prep()
    day = db.get(DayPrepDay, slate_date)
    games = list(
        db.scalars(
            select(DayPrepGame)
            .where(DayPrepGame.slate_date == slate_date)
            .order_by(DayPrepGame.commence_time)
        ).all()
    )
    analysis_id: str | None = None
    plays: list[Recommendation] = []
    cards: dict = {}
    cross: dict = {}
    if day is not None and day.status == "priced":
        analysis_id, plays = materialize_plays(db, user_id, slate_date)
        try:
            built, _quarantine = build_cards(
                plays,
                max_legs=5,
                min_rating=6.5,
            )
            cards = built
        except Exception:
            logger.exception("ready board cards failed")
            cards = {}
        cross = cross_sport_parlays(plays)
    notice = (
        day.notice
        if day is not None
        else ("Matchups have not been pulled yet. The free schedule pull is starting.")
    )
    return ReadyBoardResponse(
        slate_date=slate_date,
        status=day.status if day is not None else "idle",
        notice=notice,
        schedule_pulled_at=day.schedule_pulled_at if day is not None else None,
        priced_pulled_at=day.priced_pulled_at if day is not None else None,
        pull2_at=day.pull2_at if day is not None else None,
        earliest_start=day.earliest_start if day is not None else None,
        lead_minutes=day.lead_minutes if day is not None else None,
        binding_sport=day.binding_sport if day is not None else None,
        completeness=day.completeness if day is not None else None,
        analysis_id=analysis_id,
        games=[
            {
                "sport": game.sport,
                "event_id": game.event_id,
                "event_name": game.event_name,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "commence_time": game.commence_time,
            }
            for game in games
        ],
        plays=[RecommendationOut.model_validate(item) for item in plays],
        cards=cards,
        cross_parlays=cross,
    )


def materialize_plays(
    db: Session, user_id: str, slate_date: date
) -> tuple[str, list[Recommendation]]:
    claim = db.scalar(
        select(DayPrepClaim).where(
            DayPrepClaim.user_id == user_id,
            DayPrepClaim.slate_date == slate_date,
        )
    )
    if claim is not None:
        rows = list(
            db.scalars(
                select(Recommendation)
                .where(
                    Recommendation.analysis_id == claim.analysis_id,
                    Recommendation.created_by_user_id == user_id,
                )
                .order_by(Recommendation.rank)
            ).all()
        )
        if rows or not _system_plays(db, slate_date):
            return claim.analysis_id, rows
    analysis_id = str(uuid4())
    records: list[Recommendation] = []
    for play in _system_plays(db, slate_date):
        record = recommendation_from_payload(
            play.payload,
            analysis_id=analysis_id,
            user_id=user_id,
        )
        if record is None:
            continue
        db.add(record)
        records.append(record)
    if claim is None:
        db.add(
            DayPrepClaim(
                user_id=user_id,
                slate_date=slate_date,
                analysis_id=analysis_id,
            )
        )
    else:
        claim.analysis_id = analysis_id
    db.commit()
    for record in records:
        db.refresh(record)
    return analysis_id, records


def cross_sport_parlays(recommendations: list[Recommendation]) -> dict:
    """One approved play from each sport. Same-game stacks are not recommended."""
    safe = [
        item
        for item in recommendations
        if item.decision in APPROVED and float(item.miss_by_one_risk) < 0.55
    ]
    best: dict[str, Recommendation] = {}
    used_events: set[str] = set()
    for item in sorted(safe, key=_cross_priority):
        if item.sport in best or item.event_id in used_events:
            continue
        best[item.sport] = item
        used_events.add(item.event_id)
    ordered = sorted(best.values(), key=_cross_priority)
    if len(ordered) < 2:
        return {}
    note = (
        "Different sports and different games. This is a recommendation from "
        "today's approved plays — tap it, or build your own mix above."
    )
    cards = {
        "cross_2": _cross_card(
            "cross_2",
            "Cross-Sport 2 — best approved play from two sports",
            ordered[:2],
            note,
        )
    }
    if len(ordered) >= 3:
        cards["cross_3"] = _cross_card(
            "cross_3",
            "Cross-Sport 3 — one approved play from three sports",
            ordered[:3],
            note,
        )
    if len(ordered) >= 4:
        cards["cross_board"] = _cross_card(
            "cross_board",
            "Cross-Sport Board — approved plays across today's sports",
            ordered[:4],
            note,
        )
    return cards


def grade_candidates(db: Session, candidates: list[CandidateInput]) -> list[dict[str, Any]]:
    """Score a capped slate and keep PLAY/LEAN only."""
    from app.hive.self_improve import get_active_policy
    from app.hive.service import blend_hive_probability, get_hive_signal, hive_bucket_key
    from app.services.learning import load_feature_weights
    from app.services.metacognition import reflect_on_decision

    capped = _cap_candidates(candidates)
    weight_cache: dict[tuple[str, str], dict[str, float]] = {}
    hive_policy = None
    try:
        hive_policy = get_active_policy(db=db)
    except Exception:
        logger.exception("day prep hive policy unavailable")
    raw = []
    for candidate in capped:
        try:
            evaluation = decision_engine.evaluate(
                candidate,
                RiskProfile.balanced,
                learned_weights=weight_cache.setdefault(
                    (candidate.sport.lower(), candidate.market_type),
                    load_feature_weights(db, candidate.sport.lower(), candidate.market_type),
                ),
            )
        except Exception:
            logger.exception("day prep skipped a candidate")
            continue
        if hive_policy is not None:
            _apply_hive(
                db,
                evaluation,
                candidate,
                hive_policy=hive_policy,
                blend_hive_probability=blend_hive_probability,
                get_hive_signal=get_hive_signal,
                hive_bucket_key=hive_bucket_key,
                reflect_on_decision=reflect_on_decision,
            )
        raw.append(evaluation)
    ranked = decision_engine.rank(raw)
    plays: list[dict[str, Any]] = []
    per_sport: dict[str, int] = defaultdict(int)
    for rank, evaluation in enumerate(ranked, start=1):
        if evaluation.decision not in APPROVED:
            continue
        sport = evaluation.candidate.sport.lower()
        if per_sport[sport] >= MAX_PLAYS_PER_SPORT:
            continue
        per_sport[sport] += 1
        plays.append(_play_payload(evaluation, rank))
    return plays


def recommendation_from_payload(
    payload: dict[str, Any],
    *,
    analysis_id: str,
    user_id: str,
) -> Recommendation | None:
    try:
        snapshot = dict(payload.get("snapshot") or {})
        return Recommendation(
            analysis_id=analysis_id,
            created_by_user_id=user_id,
            candidate_id=str(payload["candidate_id"])[:100],
            event_id=str(payload["event_id"])[:100],
            event_name=str(payload["event_name"])[:180],
            sport=str(payload["sport"]).lower()[:24],
            league=str(payload.get("league") or payload["sport"])[:40],
            slate_date=_as_date(payload["slate_date"]),
            mode=str(payload.get("mode") or "pregame")[:16],
            market_type=str(payload["market_type"])[:50],
            market_period=str(payload.get("market_period") or "full_game")[:32],
            selection=str(payload["selection"])[:180],
            line=_as_decimal(payload.get("line"), "0.001"),
            american_odds=int(payload["american_odds"]),
            estimated_probability=money(payload["estimated_probability"]),
            implied_probability=money(payload["implied_probability"]),
            adjusted_probability=money(payload["adjusted_probability"]),
            edge=money(payload["edge"]),
            expected_value=money(payload["expected_value"]),
            confidence_score=int(payload["confidence_score"]),
            ywp_rating=money(payload["ywp_rating"], "0.01"),
            vision_score=money(payload["vision_score"], "0.01"),
            miss_by_one_risk=money(payload["miss_by_one_risk"], "0.0001"),
            reliability=money(payload.get("reliability") or 0, "0.0001"),
            stability=money(payload.get("stability") or 0, "0.0001"),
            variance=money(payload.get("variance") or 0, "0.0001"),
            data_quality=money(payload.get("data_quality") or 0, "0.0001"),
            risk=str(payload.get("risk") or "medium")[:20],
            risk_tier=str(payload.get("risk_tier") or "Moderate")[:20],
            variance_rating=str(payload.get("variance_rating") or "Medium")[:20],
            edge_class=str(payload.get("edge_class") or "No Edge")[:20],
            expected_value_label=str(payload.get("expected_value_label") or "Neutral")[:16],
            suggested_stake_pct=money(payload.get("suggested_stake_pct") or 0, "0.0001"),
            decision=str(payload["decision"])[:20],
            recommendation_tier=str(payload.get("recommendation_tier") or "support")[:32],
            rank=int(payload.get("rank") or 0),
            reason_codes=list(payload.get("reason_codes") or []),
            reasoning_summary=str(payload.get("reasoning_summary") or ""),
            warnings=list(payload.get("warnings") or []),
            safer_alternative=payload.get("safer_alternative"),
            higher_upside=payload.get("higher_upside"),
            invalidation_conditions=list(payload.get("invalidation_conditions") or []),
            live_trigger=payload.get("live_trigger"),
            hedge=payload.get("hedge"),
            quick_cash=bool(payload.get("quick_cash")),
            chain_reaction_key=payload.get("chain_reaction_key"),
            thesis_key=str(payload["thesis_key"])[:160],
            script_key=str(payload["script_key"])[:160],
            player_key=payload.get("player_key"),
            data_source=str(payload.get("data_source") or "DAY_PREP")[:64],
            source_timestamp=_as_datetime(payload.get("source_timestamp")) or datetime.now(UTC),
            model_version=str(payload.get("model_version") or settings.model_version)[:64],
            protocol_version=str(payload.get("protocol_version") or settings.protocol_version)[:32],
            input_hash=str(payload.get("input_hash") or uuid4().hex)[:64],
            snapshot=snapshot,
        )
    except (KeyError, TypeError, ValueError):
        logger.exception("day prep play payload could not be copied")
        return None


def default_schedule(slate_date: date) -> list[ScheduledGame]:
    """Free matchups and start times. No Odds API call."""
    games: list[ScheduledGame] = []
    for sport in PREP_SPORTS:
        try:
            games.extend(_schedule_sport(sport, slate_date))
        except Exception:
            logger.exception("day prep schedule failed for %s", sport)
    return games


def default_priced_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    """The one priced pull. Inactive sports are skipped so they do not bill."""
    if settings.demo_mode:
        from app.services.providers import demo_slate

        return list(demo_slate(sport, slate_date))
    if not settings.odds_api_key:
        return []
    from app.services.odds_provider import app_sport_in_season

    if sport != "mlb" and app_sport_in_season(sport) is False:
        return []
    try:
        if sport == "mlb":
            from app.services.live_mlb_slate import live_mlb_slate

            return list(live_mlb_slate(slate_date) or [])
        if sport == "wnba":
            from app.services.live_wnba_slate import live_wnba_slate

            return list(live_wnba_slate(slate_date) or [])
        from app.services.live_generic_slate import live_generic_slate

        return list(live_generic_slate(sport, slate_date) or [])
    except Exception:
        logger.exception("day prep priced slate failed for %s", sport)
        return []


def slate_date_for(moment: datetime) -> date:
    return _aware(moment).astimezone(ET).date()


def _advance_locked(
    db: Session,
    *,
    now: datetime,
    schedule_loader: ScheduleLoader,
    slate_loader: SlateLoader,
    grader: Grader,
) -> dict[str, Any]:
    slate_date = slate_date_for(now)
    day = db.get(DayPrepDay, slate_date)
    if day is None:
        day = DayPrepDay(slate_date=slate_date, status="scheduled", notice="")
        db.add(day)
        db.flush()
    if day.schedule_pulled_at is None:
        _pull_schedule(db, day, slate_date, schedule_loader)
        db.commit()
    if day.status in {"priced", "missed", "no_games"}:
        return _public_status(day)
    if day.status == "pricing" and _pricing_fresh(day, now):
        return _public_status(day)
    if day.pull2_at is not None and now < _aware(day.pull2_at):
        return _public_status(day)
    no_matchups = (
        day.schedule_pulled_at is not None
        and day.earliest_start is None
        and not _games(db, slate_date)
    )
    if day.status == "no_games" or no_matchups:
        day.status = "no_games"
        day.notice = "No matchups on the free schedule for this Eastern-time slate."
        day.priced_pulled_at = now
        db.commit()
        return _public_status(day)
    if day.latest_start is not None and now > _aware(day.latest_start):
        day.status = "missed"
        day.priced_pulled_at = now
        day.notice = (
            "The priced pull did not run before the last start. "
            "No Odds credits were spent. Run the slate yourself for anything still open."
        )
        db.commit()
        return _public_status(day)
    if not settings.odds_api_key and not settings.demo_mode:
        day.status = "waiting_for_prices"
        day.notice = (
            "Matchups and start times are in. The priced pull waits until the Odds key "
            "is configured. You can still Run from the app."
        )
        db.commit()
        return _public_status(day)

    day.status = "pricing"
    day.pricing_started_at = now
    db.commit()
    try:
        _pull_prices(db, day, slate_date, now, slate_loader, grader)
    except Exception:
        logger.exception("day prep priced pull failed")
        day.status = "scheduled"
        day.pricing_started_at = None
        day.notice = "The priced pull failed before it finished. The next check will try once."
        db.commit()
    return _public_status(day)


def _pull_schedule(
    db: Session,
    day: DayPrepDay,
    slate_date: date,
    schedule_loader: ScheduleLoader,
) -> None:
    games = schedule_loader(slate_date)
    db.execute(delete(DayPrepGame).where(DayPrepGame.slate_date == slate_date))
    for game in games:
        db.add(
            DayPrepGame(
                slate_date=slate_date,
                sport=game.sport,
                event_id=game.event_id[:100],
                event_name=game.event_name[:180],
                home_team=game.home_team[:80],
                away_team=game.away_team[:80],
                commence_time=_aware(game.commence_time),
            )
        )
    leads = _lead_map(db)
    pull2_at, lead, binding = binding_pull_time(games, leads, slate_date)
    day.schedule_pulled_at = datetime.now(UTC)
    day.pull2_at = pull2_at
    day.lead_minutes = lead
    day.binding_sport = binding
    if games:
        day.earliest_start = min(game.commence_time for game in games)
        day.latest_start = max(game.commence_time for game in games)
        sports = ", ".join(sorted({game.sport.upper() for game in games}))
        when = pull2_at.astimezone(ET).strftime("%-I:%M %p ET") if pull2_at else "later"
        day.status = "scheduled"
        day.notice = (
            f"Matchups are in for {sports}. "
            f"The priced pull is set for {when}, {lead} minutes before the first "
            f"{(binding or 'game').upper()} start. You can still Run yourself."
        )
    else:
        day.earliest_start = None
        day.latest_start = None
        day.status = "no_games"
        day.priced_pulled_at = datetime.now(UTC)
        day.notice = "No matchups on the free schedule for this Eastern-time slate."


def _pull_prices(
    db: Session,
    day: DayPrepDay,
    slate_date: date,
    now: datetime,
    slate_loader: SlateLoader,
    grader: Grader,
) -> None:
    games = _games(db, slate_date)
    by_sport: dict[str, list[ScheduledGame]] = defaultdict(list)
    for game in games:
        by_sport[game.sport].append(game)
    candidates_by_sport: dict[str, list[CandidateInput]] = {}
    for sport in by_sport:
        candidates_by_sport[sport] = list(slate_loader(sport, slate_date))
    all_candidates = [item for rows in candidates_by_sport.values() for item in rows]
    payloads = grader(db, all_candidates)
    db.execute(delete(DayPrepPlay).where(DayPrepPlay.slate_date == slate_date))
    for payload in payloads:
        if str(payload.get("decision")) not in APPROVED:
            continue
        db.add(
            DayPrepPlay(
                slate_date=slate_date,
                sport=str(payload.get("sport") or "")[:24],
                decision=str(payload["decision"])[:20],
                rank=int(payload.get("rank") or 0),
                event_id=str(payload.get("event_id") or "")[:100],
                selection=str(payload.get("selection") or "")[:180],
                market_type=str(payload.get("market_type") or "")[:50],
                payload=payload,
            )
        )
    scores: list[float] = []
    for sport, sport_games in by_sport.items():
        score = coverage(sport_games, candidates_by_sport.get(sport) or [])
        scores.append(score)
        first = min(_aware(game.commence_time) for game in sport_games)
        minutes_before = (first - now).total_seconds() / 60
        if minutes_before < 0:
            continue
        current = _lead_map(db).get(sport, DEFAULT_LEAD_MINUTES)
        nxt = learn_next_lead(current, score, minutes_before)
        _remember_lead(db, sport, nxt, score, int(minutes_before))
    overall = sum(scores) / len(scores) if scores else 0.0
    day.status = "priced"
    day.priced_pulled_at = now
    day.pricing_started_at = None
    day.completeness = Decimal(str(round(overall, 4)))
    approved = len(payloads)
    day.notice = (
        f"{approved} approved play{'s' if approved != 1 else ''} are waiting "
        f"across {len(by_sport)} sport{'s' if len(by_sport) != 1 else ''}. "
        f"Board completeness {overall:.0%}. You can still Run a fresh slate."
    )
    db.commit()


def _remember_lead(
    db: Session,
    sport: str,
    lead: int,
    completeness: float,
    minutes_before: int,
) -> None:
    row = db.get(DayPrepLead, sport)
    if row is None:
        row = DayPrepLead(sport=sport, lead_minutes=lead, samples=0)
        db.add(row)
    row.lead_minutes = lead
    row.samples = int(row.samples or 0) + 1
    row.last_completeness = Decimal(str(round(completeness, 4)))
    row.last_minutes_before = minutes_before
    row.updated_at = datetime.now(UTC)


def _lead_map(db: Session) -> dict[str, int]:
    leads = {sport: DEFAULT_LEAD_MINUTES for sport in PREP_SPORTS}
    for row in db.scalars(select(DayPrepLead)).all():
        leads[row.sport] = int(row.lead_minutes)
    return leads


def _games(db: Session, slate_date: date) -> list[ScheduledGame]:
    rows = db.scalars(select(DayPrepGame).where(DayPrepGame.slate_date == slate_date)).all()
    return [
        ScheduledGame(
            sport=row.sport,
            event_id=row.event_id,
            event_name=row.event_name,
            home_team=row.home_team,
            away_team=row.away_team,
            commence_time=_aware(row.commence_time),
        )
        for row in rows
    ]


def _system_plays(db: Session, slate_date: date) -> list[DayPrepPlay]:
    return list(
        db.scalars(
            select(DayPrepPlay)
            .where(DayPrepPlay.slate_date == slate_date)
            .order_by(DayPrepPlay.rank)
        ).all()
    )


def _schedule_sport(sport: str, slate_date: date) -> list[ScheduledGame]:
    if sport == "mlb":
        from app.services.mlb_provider import get_schedule

        games: list[ScheduledGame] = []
        for row in get_schedule(slate_date):
            start = _parse_time(row.get("game_date"))
            if start is None:
                continue
            away = str(row.get("away_team") or "")
            home = str(row.get("home_team") or "")
            games.append(
                ScheduledGame(
                    sport="mlb",
                    event_id=str(row.get("game_pk") or ""),
                    event_name=f"{away} at {home}".strip(),
                    home_team=home,
                    away_team=away,
                    commence_time=start,
                )
            )
        return games
    from app.services.espn_provider import get_scoreboard

    games = []
    for row in get_scoreboard(sport, slate_date):
        if row.get("completed"):
            continue
        status = str(row.get("status") or "").lower()
        if any(token in status for token in _FINISHED):
            continue
        start = _parse_time(row.get("start_time"))
        if start is None:
            continue
        away = str(row.get("away_team") or "")
        home = str(row.get("home_team") or "")
        name = str(row.get("name") or f"{away} at {home}")
        games.append(
            ScheduledGame(
                sport=sport,
                event_id=str(row.get("event_id") or name),
                event_name=name,
                home_team=home,
                away_team=away,
                commence_time=start,
            )
        )
    return games


def _apply_hive(db: Session, evaluation, candidate: CandidateInput, **helpers) -> None:
    try:
        base_probability = (
            float(evaluation.adjusted_probability)
            if candidate.probability_source in {"model", "manual_verified", "demo"}
            else None
        )
        hive_signal = helpers["get_hive_signal"](
            db=db,
            sport=candidate.sport,
            league=candidate.league,
            market=candidate.market_type,
            market_scope=candidate.market_period,
            model_version=settings.model_version,
        )
        hive_adjusted, hive_meta = helpers["blend_hive_probability"](
            base_probability=base_probability,
            hive_signal=hive_signal,
            policy=helpers["hive_policy"].to_dict(),
            bucket_key=helpers["hive_bucket_key"](
                candidate.sport,
                candidate.league,
                candidate.market_type,
                candidate.market_period,
                settings.model_version,
            ),
        )
        evaluation.payload["model_probability"] = base_probability
        evaluation.payload["hive_adjusted_probability"] = hive_adjusted
        evaluation.payload["hive"] = hive_meta
        if hive_meta.get("used") and hive_adjusted is not None and base_probability is not None:
            updated = decision_engine.apply_hive_calibration(
                evaluation,
                float(hive_adjusted),
                shift_applied=float(hive_meta.get("shift_applied") or 0.0),
            )
            evaluation.decision = updated.decision
            evaluation.reason_codes = updated.reason_codes
            evaluation.warnings = updated.warnings
            evaluation.reasoning_summary = updated.reasoning_summary
            evaluation.adjusted_probability = updated.adjusted_probability
            evaluation.edge = updated.edge
            evaluation.expected_value = updated.expected_value
            evaluation.confidence_score = updated.confidence_score
            evaluation.payload = updated.payload
        evaluation.payload["metacognition"] = helpers["reflect_on_decision"](
            decision=evaluation.decision,
            reason_codes=evaluation.reason_codes,
            warnings=evaluation.warnings,
            reasoning_summary=evaluation.reasoning_summary,
            selection=candidate.selection,
            hive_meta=hive_meta if isinstance(hive_meta, dict) else None,
            probability_source=candidate.probability_source,
        )
    except Exception:
        logger.exception("day prep hive blend skipped")


def _play_payload(evaluation, rank: int) -> dict[str, Any]:
    candidate = evaluation.candidate
    snapshot = dict(evaluation.payload or {})
    snapshot.setdefault("home_team", candidate.home_team)
    snapshot.setdefault("away_team", candidate.away_team)
    snapshot.setdefault("start_time", _iso(candidate.start_time))
    snapshot.setdefault("probability_source", candidate.probability_source)
    snapshot.setdefault("game_status", candidate.game_status)
    snapshot.setdefault("market_status", candidate.market_status)
    snapshot["day_prep"] = True
    reason_codes = list(evaluation.reason_codes or [])
    if "DAY_PREP" not in reason_codes:
        reason_codes.append("DAY_PREP")
    slate_date = candidate.start_time.astimezone(ET).date()
    return _jsonable(
        {
            "candidate_id": candidate.candidate_id,
            "event_id": candidate.event_id,
            "event_name": candidate.event_name,
            "sport": candidate.sport.lower(),
            "league": candidate.league,
            "slate_date": slate_date.isoformat(),
            "mode": "pregame",
            "market_type": candidate.market_type,
            "market_period": candidate.market_period,
            "selection": candidate.selection,
            "line": candidate.line,
            "american_odds": candidate.american_odds,
            "estimated_probability": candidate.estimated_probability,
            "implied_probability": evaluation.implied_probability,
            "adjusted_probability": evaluation.adjusted_probability,
            "edge": evaluation.edge,
            "expected_value": evaluation.expected_value,
            "confidence_score": evaluation.confidence_score,
            "ywp_rating": evaluation.ywp_intelligence_score,
            "vision_score": evaluation.vision_score,
            "miss_by_one_risk": evaluation.miss_by_one_risk,
            "reliability": evaluation.reliability,
            "stability": evaluation.stability,
            "variance": candidate.variance,
            "data_quality": candidate.data_quality,
            "risk": evaluation.risk,
            "risk_tier": evaluation.risk_tier,
            "variance_rating": evaluation.variance_rating,
            "edge_class": evaluation.edge_class,
            "expected_value_label": evaluation.expected_value_label,
            "suggested_stake_pct": evaluation.suggested_stake_pct,
            "decision": evaluation.decision,
            "recommendation_tier": evaluation.recommendation_tier,
            "rank": rank,
            "reason_codes": reason_codes,
            "reasoning_summary": evaluation.reasoning_summary,
            "warnings": list(evaluation.warnings or []),
            "safer_alternative": candidate.safer_alternative,
            "higher_upside": candidate.higher_upside,
            "invalidation_conditions": list(candidate.invalidation_conditions or []),
            "live_trigger": candidate.live_trigger,
            "hedge": candidate.hedge,
            "quick_cash": candidate.quick_cash,
            "chain_reaction_key": candidate.chain_reaction_key,
            "thesis_key": candidate.thesis_key,
            "script_key": candidate.script_key,
            "player_key": candidate.player_key,
            "data_source": candidate.data_source,
            "source_timestamp": _iso(candidate.source_timestamp),
            "model_version": settings.model_version,
            "protocol_version": settings.protocol_version,
            "input_hash": evaluation.input_hash,
            "snapshot": snapshot,
        }
    )


def _cross_card(key: str, label: str, legs: list[Recommendation], note: str):
    card = preview_custom_card(legs, key=key, label=label)
    card.warnings = [*card.warnings, note]
    return card


def _cross_priority(item: Recommendation) -> tuple:
    rank = int(item.rank or 0) or 10_000
    return (rank, -int(item.confidence_score), -float(item.ywp_rating))


def _cap_candidates(candidates: list[CandidateInput]) -> list[CandidateInput]:
    main = [item for item in candidates if not str(item.market_type).startswith("player_")]
    props = [item for item in candidates if str(item.market_type).startswith("player_")]
    return main[:20] + props[:MAX_PROP_CANDIDATES]


def _is_priced(candidate: CandidateInput) -> bool:
    if str(candidate.market_type) == "schedule":
        return False
    try:
        odds = int(candidate.american_odds)
    except (TypeError, ValueError):
        return False
    return odds != 0


def _covers(event_name: str, home: str, away: str) -> bool:
    text = event_name.lower()
    home_nick = _nickname(home)
    away_nick = _nickname(away)
    if len(home_nick) < 3 or len(away_nick) < 3:
        return False
    return home_nick in text and away_nick in text


def _nickname(name: str) -> str:
    parts = [
        part for part in re.split(r"[^a-z0-9]+", name.lower()) if part and part not in _NICK_SKIP
    ]
    return parts[-1] if parts else ""


def _pricing_fresh(day: DayPrepDay, now: datetime) -> bool:
    started = day.pricing_started_at
    if started is None:
        return False
    return now - _aware(started) < PRICING_STALE


def _public_status(day: DayPrepDay) -> dict[str, Any]:
    return {
        "slate_date": day.slate_date.isoformat(),
        "status": day.status,
        "notice": day.notice,
        "pull2_at": _iso(day.pull2_at),
        "lead_minutes": day.lead_minutes,
        "binding_sport": day.binding_sport,
    }


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _as_datetime(value: object) -> datetime | None:
    return _parse_time(value)


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_decimal(value: object, places: str) -> Decimal | None:
    if value is None or value == "":
        return None
    return money(value, places)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _aware(value).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
