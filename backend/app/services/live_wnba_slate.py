"""
Live WNBA slate: Odds API prices + ESPN trusted facts + independent model.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.schemas import CandidateInput
from app.services.facts_cascade import league_injuries
from app.services.market_board import _flatten_prop_markets
from app.services.odds_provider import extract_best_odds, get_game_odds, get_player_props
from app.services.sport_research import build_event_research, build_verified_candidate

logger = logging.getLogger(__name__)

SPORT_KEY = "basketball_wnba"
# Same menu as Pick Sheet WNBA board — credits scale with markets × events.
WNBA_PROP_MARKETS = (
    "player_points,player_rebounds,player_assists,player_threes,"
    "player_points_rebounds_assists"
)


def live_wnba_slate(slate_date: date) -> list[CandidateInput]:
    try:
        odds_events = get_game_odds(sport=SPORT_KEY, markets="h2h,spreads,totals")
    except Exception:
        logger.exception("Failed to fetch WNBA odds")
        return []

    if not odds_events:
        logger.warning("No WNBA events found for %s", slate_date)
        return []

    injury_feed = league_injuries("wnba")
    candidates: list[CandidateInput] = []
    now = datetime.now(UTC)
    matched_events = 0
    prop_event_contexts: list[dict[str, Any]] = []

    for event in odds_events:
        start_time = _parse_start(event.get("commence_time"), slate_date)
        # Same gate as /sports/analyze: America/New_York calendar date (or UTC match).
        if start_time.astimezone(UTC).date() != slate_date and _event_local_date(
            start_time
        ) != slate_date:
            continue
        matched_events += 1
        event_id = str(event.get("id") or "")
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        event_name = f"{away} @ {home}"
        bookmakers = event.get("bookmakers", [])
        research = build_event_research(
            sport="wnba",
            slate_date=slate_date,
            home_team=home,
            away_team=away,
            bookmakers=bookmakers,
            injury_feed=injury_feed,
        )
        if event_id:
            prop_event_contexts.append(
                {
                    "event": event,
                    "event_id": event_id,
                    "start_time": start_time,
                }
            )

        for team in (home, away):
            ml = extract_best_odds(bookmakers, "h2h", team)
            if not ml:
                continue
            side = "home" if team == home else "away"
            candidates.append(
                build_verified_candidate(
                    sport="wnba",
                    league="WNBA",
                    candidate_id=f"wnba-ml-{side}-{event_id[:12]}",
                    event_id=event_id,
                    event_name=event_name,
                    home_team=home,
                    away_team=away,
                    start_time=start_time,
                    market_type="moneyline",
                    selection=f"{team} ML",
                    odds=ml["american_odds"],
                    line=None,
                    thesis_key=f"wnba-{_slug(team)}-ml-{slate_date}",
                    script_key=f"wnba-{_slug(event_name)}-{side}-control",
                    reason_codes=["HOME_FIELD", "CURRENT_FORM"]
                    if side == "home"
                    else ["CURRENT_FORM"],
                    reasoning=[f"{team} moneyline from ESPN form + injury research."],
                    research=research,
                    now=now,
                )
            )

        for team in (home, away):
            spread = extract_best_odds(bookmakers, "spreads", team)
            if not spread or spread.get("point") is None:
                continue
            spread_line = Decimal(str(spread["point"]))
            side = "home" if team == home else "away"
            candidates.append(
                build_verified_candidate(
                    sport="wnba",
                    league="WNBA",
                    candidate_id=f"wnba-spread-{side}-{event_id[:12]}",
                    event_id=event_id,
                    event_name=event_name,
                    home_team=home,
                    away_team=away,
                    start_time=start_time,
                    market_type="spread",
                    selection=f"{team} {spread_line:+}",
                    odds=spread["american_odds"],
                    line=spread_line,
                    thesis_key=f"wnba-{_slug(team)}-spread-{spread_line}-{slate_date}",
                    script_key=f"wnba-{_slug(event_name)}-{side}-margin",
                    reason_codes=["GAME_SCRIPT", "CURRENT_FORM"],
                    reasoning=[f"{team} spread {spread_line:+} from independent form model."],
                    research=research,
                    now=now,
                )
            )

        for label in ("Over", "Under"):
            total = extract_best_odds(bookmakers, "totals", label)
            if not total or total.get("point") is None:
                continue
            line_val = Decimal(str(total["point"]))
            mtype = "game_total_over" if label == "Over" else "game_total_under"
            candidates.append(
                build_verified_candidate(
                    sport="wnba",
                    league="WNBA",
                    candidate_id=f"wnba-{label.lower()}-{event_id[:12]}",
                    event_id=event_id,
                    event_name=event_name,
                    home_team=home,
                    away_team=away,
                    start_time=start_time,
                    market_type=mtype,
                    selection=f"{label} {line_val}",
                    odds=total["american_odds"],
                    line=line_val,
                    thesis_key=f"wnba-{_slug(event_name)}-{label.lower()}-{line_val}-{slate_date}",
                    script_key=f"wnba-{_slug(event_name)}-pace",
                    reason_codes=["GAME_SCRIPT", "L10_CUSHION"],
                    reasoning=[f"Game total {label} {line_val} vs ESPN expected scoring."],
                    research=research,
                    now=now,
                )
            )

    prop_candidates = _append_wnba_player_props(
        prop_event_contexts,
        now=now,
        max_events=max(0, int(settings.mlb_board_max_prop_events or 4)),
    )
    candidates.extend(prop_candidates)

    logger.info(
        "Built %d live WNBA candidates (%d props) from %d date-matched events for %s",
        len(candidates),
        len(prop_candidates),
        matched_events,
        slate_date,
    )
    return candidates


def _append_wnba_player_props(
    contexts: list[dict[str, Any]],
    *,
    now: datetime,
    max_events: int,
) -> list[CandidateInput]:
    """Price WNBA player props onto the Run/raw slate (credit-capped)."""
    if max_events <= 0 or not contexts:
        return []
    chunks = _chunk_csv(WNBA_PROP_MARKETS, size=3)
    out: list[CandidateInput] = []
    priced = 0
    for ctx in contexts:
        if priced >= max_events:
            break
        event_id = str(ctx["event_id"])
        start_time = ctx["start_time"]
        prop_books: list[dict[str, Any]] = []
        got = False
        for chunk in chunks:
            try:
                payload = get_player_props(event_id, sport=SPORT_KEY, markets=chunk)
            except Exception:
                logger.warning("WNBA props chunk failed for %s (%s)", event_id, chunk, exc_info=True)
                continue
            if not payload:
                continue
            got = True
            prop_books.extend(payload.get("bookmakers") or [])
        if not got or not prop_books:
            continue
        priced += 1
        merged = dict(ctx["event"])
        merged["bookmakers"] = prop_books
        try:
            out.extend(
                _flatten_prop_markets(
                    event=merged,
                    sport="wnba",
                    start_time=start_time,
                    now=now,
                    league="WNBA",
                )
            )
        except Exception:
            logger.exception("Flatten WNBA prop markets failed for %s", event_id)
    return out


def _chunk_csv(markets_csv: str, *, size: int) -> list[str]:
    parts = [p.strip() for p in markets_csv.split(",") if p.strip()]
    if size <= 0:
        return [",".join(parts)] if parts else []
    return [",".join(parts[i : i + size]) for i in range(0, len(parts), size)]


def upcoming_wnba_dates(*, limit: int = 5) -> list[str]:
    """Nearest America/New_York slate dates that currently have WNBA Odds events."""
    try:
        odds_events = get_game_odds(sport=SPORT_KEY, markets="h2h,spreads,totals")
    except Exception:
        logger.exception("Failed to fetch WNBA odds for upcoming dates")
        return []
    dates: list[str] = []
    for event in odds_events or []:
        start = _parse_start(event.get("commence_time"), date.today())
        stamp = _event_local_date(start).isoformat()
        if stamp not in dates:
            dates.append(stamp)
        if len(dates) >= limit:
            break
    return sorted(dates)[:limit]


def _event_local_date(start_time: datetime) -> date:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
    return start_time.astimezone(ZoneInfo("America/New_York")).date()


def _parse_start(commence_time: str | None, slate_date: date) -> datetime:
    if commence_time:
        try:
            return datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return datetime(slate_date.year, slate_date.month, slate_date.day, 23, 0, tzinfo=UTC)


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("@", "at").replace(".", "")[:60]
