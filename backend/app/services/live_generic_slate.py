"""
Generic live slate builder for Odds API sports with multi-source fact cascade.

Covers NFL, NBA, NHL, NCAAF, NCAAB, soccer/MLS/EPL, KBO.
Odds prices are required to show a play. Fact sources (NHL Web API, ESPN, …)
enrich research; if they fail, priced plays still return as PARTIAL.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from app.schemas import CandidateInput
from app.core.config import settings
from app.services.espn_provider import espn_path_for
from app.services.facts_cascade import league_injuries
from app.services.market_board import _PROP_MARKETS_BY_SPORT, _flatten_prop_markets
from app.services.odds_provider import (
    active_odds_keys_for_app_sport,
    extract_best_odds,
    get_game_odds,
    get_player_props,
    soccer_league_label,
    soccer_odds_regions,
)
from app.services.player_prop_research import enrich_player_prop_candidates
from app.services.sport_research import build_event_research, build_verified_candidate

logger = logging.getLogger(__name__)

SPORT_KEYS: dict[str, str] = {
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "nhl": "icehockey_nhl",
    "ncaaf": "americanfootball_ncaaf",
    "ncaab": "basketball_ncaab",
    # soccer primary key retained for SPORT_KEYS membership; multi-league via
    # active_odds_keys_for_app_sport("soccer").
    "soccer": "soccer_epl",
    "epl": "soccer_epl",
    "mls": "soccer_usa_mls",
    "kbo": "baseball_kbo",
}

SPORT_DISPLAY: dict[str, tuple[str, str]] = {
    "nfl": ("nfl", "NFL"),
    "nba": ("nba", "NBA"),
    "nhl": ("nhl", "NHL"),
    "ncaaf": ("ncaaf", "NCAAF"),
    "ncaab": ("ncaab", "NCAAB"),
    "soccer": ("soccer", "Soccer"),
    "epl": ("soccer", "EPL"),
    "mls": ("soccer", "MLS"),
    "kbo": ("kbo", "KBO"),
}

SOCCER_KEYS = {"soccer", "epl", "mls"}


def live_generic_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    sport_lower = sport.lower()
    if sport_lower not in SPORT_KEYS:
        logger.warning("No Odds API sport key for %s", sport)
        return []

    sport_code, default_league = SPORT_DISPLAY.get(sport_lower, (sport_lower, sport.upper()))
    odds_keys = active_odds_keys_for_app_sport(sport_lower)
    if not odds_keys:
        # Fall back to legacy single mapping when catalog filtering returned nothing.
        odds_keys = [SPORT_KEYS[sport_lower]]

    odds_events: list[dict] = []
    leagues_fetched: list[str] = []
    regions = soccer_odds_regions(sport_lower)
    for odds_key in odds_keys:
        try:
            batch = get_game_odds(
                sport=odds_key, markets="h2h,spreads,totals", regions=regions
            )
        except Exception:
            logger.exception("Failed to fetch %s odds (%s)", sport, odds_key)
            continue
        if not batch:
            continue
        leagues_fetched.append(soccer_league_label(odds_key) if sport_lower in SOCCER_KEYS else default_league)
        for event in batch:
            enriched = dict(event)
            enriched["_ywp_odds_key"] = odds_key
            enriched["_ywp_league"] = (
                soccer_league_label(odds_key) if sport_lower in SOCCER_KEYS else default_league
            )
            odds_events.append(enriched)

    if not odds_events:
        logger.warning("No %s events found across keys %s", sport, odds_keys)
        return []

    injury_feed = (
        league_injuries(sport_code)
        if (espn_path_for(sport_code) or sport_lower == "kbo")
        else {"verified": False}
    )
    candidates: list[CandidateInput] = []
    now = datetime.now(UTC)
    matched_events = 0
    prop_event_contexts: list[dict] = []

    for event in odds_events:
        start_time = _parse_start(event.get("commence_time"))
        if start_time is None:
            continue
        if start_time.astimezone(UTC).date() != slate_date and _event_local_date(
            start_time, sport=sport_lower
        ) != slate_date:
            continue
        matched_events += 1
        event_id = event.get("id", "")
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        league = str(event.get("_ywp_league") or default_league)
        event_name = f"{away} @ {home}"
        if sport_lower == "soccer" and league and league != "Soccer":
            event_name = f"{away} @ {home} ({league})"
        bookmakers = event.get("bookmakers", [])
        try:
            research = build_event_research(
                sport=sport_code,
                slate_date=slate_date,
                home_team=home,
                away_team=away,
                bookmakers=bookmakers,
                injury_feed=injury_feed,
            )
        except Exception:
            logger.exception("Research failed for %s %s — keeping Odds-priced play", sport, event_name)
            research = _odds_only_research(bookmakers, home_team=home, sport=sport)

        if event_id and sport_lower in {"nfl", "ncaaf"}:
            prop_event_contexts.append(
                {
                    "event": event,
                    "event_id": str(event_id),
                    "start_time": start_time,
                    "odds_key": str(event.get("_ywp_odds_key") or odds_keys[0]),
                    "league": league,
                }
            )

        try:
            _append_event_candidates(
                candidates,
                sport_lower=sport_lower,
                sport_code=sport_code,
                league=league,
                event_id=event_id,
                event_name=event_name,
                home=home,
                away=away,
                start_time=start_time,
                bookmakers=bookmakers,
                research=research,
                slate_date=slate_date,
                now=now,
            )
        except Exception:
            logger.exception("Failed building candidates for %s %s", sport, event_name)

    prop_candidates: list[CandidateInput] = []
    if sport_lower in {"nfl", "ncaaf"} and prop_event_contexts:
        max_events = int(
            getattr(settings, "nfl_max_prop_events", None)
            if sport_lower == "nfl"
            else 4
        )
        prop_candidates = _append_football_player_props(
            prop_event_contexts,
            sport=sport_lower,
            now=now,
            slate_date=slate_date,
            max_events=max(0, max_events),
        )
        candidates.extend(prop_candidates)

    logger.info(
        "Built %d live %s candidates (%d props) from %d Odds events on %s "
        "(%d date-matched; leagues=%s)",
        len(candidates),
        sport,
        len(prop_candidates),
        len(odds_events),
        slate_date,
        matched_events,
        ",".join(leagues_fetched) or default_league,
    )
    return candidates


def _chunk_csv(markets_csv: str, *, size: int) -> list[str]:
    parts = [p.strip() for p in markets_csv.split(",") if p.strip()]
    if size <= 0:
        return [",".join(parts)] if parts else []
    return [",".join(parts[i : i + size]) for i in range(0, len(parts), size)]


def _append_football_player_props(
    contexts: list[dict],
    *,
    sport: str,
    now: datetime,
    slate_date: date,
    max_events: int,
) -> list[CandidateInput]:
    """Price NFL/NCAAF player props onto the Run slate and attach ESPN form models."""
    markets = _PROP_MARKETS_BY_SPORT.get(sport)
    if max_events <= 0 or not contexts or not markets:
        return []
    chunks = _chunk_csv(markets, size=4)
    out: list[CandidateInput] = []
    priced = 0
    for ctx in contexts:
        if priced >= max_events:
            break
        event_id = str(ctx["event_id"])
        odds_key = str(ctx["odds_key"])
        start_time = ctx["start_time"]
        prop_books: list = []
        got = False
        for chunk in chunks:
            try:
                payload = get_player_props(event_id, sport=odds_key, markets=chunk)
            except Exception:
                logger.warning(
                    "%s props chunk failed for %s (%s)", sport.upper(), event_id, chunk, exc_info=True
                )
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
                    sport=sport,
                    start_time=start_time,
                    now=now,
                    league=str(ctx.get("league") or sport.upper()),
                )
            )
        except Exception:
            logger.exception("Flatten %s prop markets failed for %s", sport, event_id)

    if out:
        out = enrich_player_prop_candidates(out, slate_date=slate_date)
    return out


def upcoming_odds_dates(sport: str, *, limit: int = 5) -> list[str]:
    """Nearest UTC slate dates that currently have Odds events for this sport.

    Uses the same market bundle as the live slate so a prior paid fetch can be
    served from the short Odds TTL cache (0 extra credits).
    """
    sport_lower = sport.lower()
    odds_keys = active_odds_keys_for_app_sport(sport_lower)
    if not odds_keys:
        odds_key = SPORT_KEYS.get(sport_lower)
        odds_keys = [odds_key] if odds_key else []
    if not odds_keys:
        return []
    dates: list[str] = []
    regions = soccer_odds_regions(sport_lower)
    for odds_key in odds_keys:
        try:
            events = get_game_odds(
                sport=odds_key, markets="h2h,spreads,totals", regions=regions
            )
        except Exception:
            continue
        for event in events:
            start = _parse_start(event.get("commence_time"))
            if start is None:
                continue
            stamp = start.astimezone(UTC).date().isoformat()
            if stamp not in dates:
                dates.append(stamp)
            if len(dates) >= limit:
                return sorted(dates)[:limit]
    return sorted(dates)[:limit]


def _append_event_candidates(
    candidates: list[CandidateInput],
    *,
    sport_lower: str,
    sport_code: str,
    league: str,
    event_id: str,
    event_name: str,
    home: str,
    away: str,
    start_time: datetime,
    bookmakers: list,
    research: dict,
    slate_date: date,
    now: datetime,
) -> None:
    for team in (home, away):
        ml = extract_best_odds(bookmakers, "h2h", team)
        if not ml:
            continue
        side = "home" if team == home else "away"
        candidates.append(
            build_verified_candidate(
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-ml-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                home_team=home,
                away_team=away,
                start_time=start_time,
                market_type="moneyline",
                selection=f"{team} ML",
                odds=ml["american_odds"],
                line=None,
                thesis_key=f"{sport_lower}-{_slug(team)}-ml-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-{side}",
                reason_codes=["MATCHUP_EDGE", "CURRENT_FORM"],
                reasoning=[
                    f"{team} moneyline from available form sources + trusted market price.",
                    *(
                        ["Modeled as 90-minute 1X2 (home/draw/away)."]
                        if sport_lower in SOCCER_KEYS
                        else []
                    ),
                ],
                research=research,
                now=now,
            )
        )

    if sport_lower in SOCCER_KEYS:
        draw = extract_best_odds(bookmakers, "h2h", "Draw")
        if draw:
            candidates.append(
                build_verified_candidate(
                    sport=sport_code,
                    league=league,
                    candidate_id=f"{sport_lower}-ml-draw-{event_id[:12]}",
                    event_id=event_id,
                    event_name=event_name,
                    home_team=home,
                    away_team=away,
                    start_time=start_time,
                    market_type="moneyline_draw",
                    selection="Draw (90 min)",
                    odds=draw["american_odds"],
                    line=None,
                    thesis_key=f"{sport_lower}-{_slug(event_name)}-draw-{slate_date}",
                    script_key=f"{sport_lower}-{_slug(event_name)}-draw",
                    reason_codes=["MATCHUP_EDGE", "CURRENT_FORM"],
                    reasoning=["Regulation draw priced as a 1X2 outcome (not ET/pens)."],
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
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-spread-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                home_team=home,
                away_team=away,
                start_time=start_time,
                market_type="spread",
                selection=f"{team} {spread_line:+}",
                odds=spread["american_odds"],
                line=spread_line,
                thesis_key=f"{sport_lower}-{_slug(team)}-spread-{spread_line}-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-{side}-margin",
                reason_codes=["GAME_SCRIPT", "MATCHUP_EDGE"],
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
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-{label.lower()}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                home_team=home,
                away_team=away,
                start_time=start_time,
                market_type=mtype,
                selection=f"{label} {line_val}",
                odds=total["american_odds"],
                line=line_val,
                thesis_key=f"{sport_lower}-{_slug(event_name)}-{label.lower()}-{line_val}-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-scoring",
                reason_codes=["GAME_SCRIPT", "CURRENT_FORM"],
                reasoning=[f"Game total {label} {line_val} vs modeled expected scoring."],
                research=research,
                now=now,
            )
        )


def _odds_only_research(bookmakers: list, *, home_team: str, sport: str | None = None) -> dict:
    from app.services.research_searchers import search_market_consensus

    market = search_market_consensus(bookmakers, "h2h", home_team)
    sport_l = (sport or "").lower()
    team_market = sport_l in {
        "nfl",
        "ncaaf",
        "nba",
        "ncaab",
        "wnba",
        "nhl",
        "soccer",
        "mls",
        "epl",
        "kbo",
    }
    na = "n/a" if team_market else "unknown"
    indoor = sport_l in {"nba", "ncaab", "wnba", "nhl"}
    return {
        "espn_game": None,
        "home_form": {"verified": False},
        "away_form": {"verified": False},
        "injuries": {"verified": False, "home_out": 0, "away_out": 0},
        "weather": {"verified": indoor},
        "market": market,
        "flags": {
            "schedule_verified": False,
            "current_form_verified": False,
            "l5_l10_verified": False,
            "lineup_confirmed": False,
            "injuries_verified": False,
            "weather_verified": indoor,
            "starter_confirmed": False,
            "motivation_rotation_verified": False,
            "home_away_verified": False,
            "market_movement_verified": False,
            "sport_specific_sweep_complete": False,
            "venue_verified": False,
            "market_consensus_available": bool(market.get("verified")),
        },
        "source_status": {
            "schedule": "unknown",
            "market": "confirmed" if market.get("verified") else "unknown",
            "current_form": "unknown",
            "injuries": "unknown",
            "starter": na,
            "lineup": na,
            # Indoor team sports never need weather — do not inflate unknown labels.
            "weather": ("n/a" if indoor else "unknown"),
            "venue": "unknown",
            "bullpen": na,
        },
        "source_urls": [],
        "missing": ["schedule", "form", "injuries"],
    }


def _parse_start(commence_time: str | None) -> datetime | None:
    if not commence_time:
        return None
    try:
        return datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _event_local_date(start_time: datetime, *, sport: str | None = None) -> date:
    from zoneinfo import ZoneInfo

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
    zone = "Asia/Seoul" if (sport or "").lower() == "kbo" else "America/New_York"
    return start_time.astimezone(ZoneInfo(zone)).date()


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("@", "at").replace(".", "")[:60]
