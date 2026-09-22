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
from app.services.player_prop_research import enrich_player_prop_candidates
from app.services.sport_research import build_event_research, build_verified_candidate

logger = logging.getLogger(__name__)

SPORT_KEY = "basketball_wnba"
# Same menu as Pick Sheet WNBA board — credits scale with markets × events.
WNBA_PROP_MARKETS = (
    "player_points,player_rebounds,player_assists,player_threes,"
    "player_points_rebounds_assists,player_points_rebounds,player_points_assists,"
    "player_rebounds_assists,player_blocks,player_steals,player_blocks_steals,"
    "player_turnovers,player_double_double,player_triple_double,"
    "player_field_goals,player_frees_made"
)

_last_props_status: dict[str, Any] = {
    "enabled": True,
    "events_priced": 0,
    "prop_candidates": 0,
    "model_props": 0,
    "errors": 0,
}


def get_last_wnba_props_status() -> dict[str, Any]:
    return dict(_last_props_status)


def wnba_props_slate_notice() -> str:
    status = get_last_wnba_props_status()
    priced = int(status.get("events_priced") or 0)
    props_n = int(status.get("prop_candidates") or 0)
    model_n = int(status.get("model_props") or 0)
    if props_n == 0:
        if priced == 0:
            return "Player props enabled — no Odds prop lines for this slate date yet."
        return "Player props collected but none flattened for this slate."
    return (
        f"Player props on slate: {props_n} line(s) across {priced} game(s) "
        f"({model_n} ESPN form-modeled for protocol)."
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
        slate_date=slate_date,
        max_events=max(
            0,
            int(
                getattr(settings, "wnba_max_prop_events", None)
                or 10
            ),
        ),
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
    slate_date: date,
    max_events: int,
) -> list[CandidateInput]:
    """Price WNBA player props onto the Run/raw slate and attach ESPN form models."""
    if max_events <= 0 or not contexts:
        _last_props_status.update(
            {"enabled": True, "events_priced": 0, "prop_candidates": 0, "model_props": 0, "errors": 0}
        )
        return []
    chunks = _chunk_csv(WNBA_PROP_MARKETS, size=3)
    out: list[CandidateInput] = []
    priced = 0
    errors = 0
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
                logger.warning(
                    "WNBA props chunk failed for %s (%s)", event_id, chunk, exc_info=True
                )
                errors += 1
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
            errors += 1

    # Always keep collected Odds props on the raw list; upgrade in place to model
    # when ESPN L5/L10 resolves so Strict Mode can PLAY instead of hard-SKIP.
    if out:
        # Keep slate refresh under Render's ~30s proxy — full enrich happens
        # (budgeted again) on LAUNCH for remaining market_implied rows.
        budget = 8.0 if len(out) >= 200 else 14.0
        out = enrich_player_prop_candidates(
            out, slate_date=slate_date, budget_seconds=budget
        )
    model_n = sum(1 for row in out if row.probability_source == "model")
    _last_props_status.update(
        {
            "enabled": True,
            "events_priced": priced,
            "prop_candidates": len(out),
            "model_props": model_n,
            "errors": errors,
        }
    )
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
