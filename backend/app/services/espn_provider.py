"""ESPN Site API fact provider for non-MLB sports.

ESPN's structured Site API is the certified primary facts source for WNBA, NBA,
NFL, NHL, NCAAF, soccer, and related leagues — schedule, form, injuries, venue.
It is not an HTML scrape. Market prices still come only from The Odds API.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# site.api.espn.com is often Akamai-blocked from cloud egress (403 Access Denied).
# site.web.api.espn.com serves the same Site JSON paths and works from Render/VMs.
SOURCE_API = "https://site.web.api.espn.com/apis/site/v2/sports"
SOURCE_API_FALLBACK = "https://site.api.espn.com/apis/site/v2/sports"
SOURCE_ID = "espn_site_api"
TIMEOUT = 15.0
_CACHE: dict[str, tuple[float, Any]] = {}
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# sport code -> ESPN path segment
# KBO is intentionally omitted — ESPN has no baseball/kbo league (400 invalid).
ESPN_SPORT_PATHS: dict[str, str] = {
    "wnba": "basketball/wnba",
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "ncaab": "basketball/mens-college-basketball",
    "nhl": "hockey/nhl",
    "soccer": "soccer/usa.1",
    "mls": "soccer/usa.1",
    "epl": "soccer/eng.1",
}

WEATHER_SPORTS = {"nfl", "ncaaf", "soccer", "mls", "epl", "kbo"}


def espn_path_for(sport: str) -> str | None:
    return ESPN_SPORT_PATHS.get(sport.lower())


def get_scoreboard(sport: str, slate_date: date) -> list[dict[str, Any]]:
    path = espn_path_for(sport)
    if not path:
        return []
    stamp = slate_date.strftime("%Y%m%d")
    try:
        data = _get(f"{SOURCE_API}/{path}/scoreboard", params={"dates": stamp}, cache_ttl=120)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN scoreboard unavailable for %s %s: %s", sport, slate_date, exc)
        return []
    games: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        parsed = _parse_event(event, sport=sport)
        if parsed:
            games.append(parsed)
    return games


def match_odds_event_to_espn(
    sport: str,
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    """Best-effort match Odds API event names to an ESPN scoreboard game."""
    try:
        games = get_scoreboard(sport, slate_date)
        # Also try adjacent days for late/early slate timezone drift.
        if not games:
            for delta in (-1, 1):
                games.extend(get_scoreboard(sport, slate_date + timedelta(days=delta)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN match failed for %s: %s", sport, exc)
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for game in games:
        score = _name_overlap(home_team, game.get("home_team", "")) + _name_overlap(
            away_team, game.get("away_team", "")
        )
        if score > best_score:
            best_score = score
            best = game
    if best is None or best_score < 2:
        return None
    return best


def probe_espn_api(sport: str = "nfl") -> dict[str, Any]:
    path = espn_path_for(sport)
    if not path:
        return {
            "status": "unsupported",
            "sport": sport,
            "error": f"No ESPN path mapped for {sport}",
            "source_id": SOURCE_ID,
        }
    try:
        data = _get(f"{SOURCE_API}/{path}/scoreboard", cache_ttl=60)
        return {
            "status": "connected",
            "sport": sport,
            "events": len(data.get("events") or []),
            "source_id": SOURCE_ID,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "sport": sport, "error": str(exc), "source_id": SOURCE_ID}


def get_team_recent_form(
    sport: str,
    team_id: str | int,
    slate_date: date,
    *,
    last_n: int = 10,
) -> dict[str, Any]:
    path = espn_path_for(sport)
    if not path:
        return _empty_form()
    try:
        data = _get(f"{SOURCE_API}/{path}/teams/{team_id}/schedule", cache_ttl=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN form unavailable for %s team %s: %s", sport, team_id, exc)
        return _empty_form()
    games: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        status = (comp.get("status") or {}).get("type") or {}
        if not status.get("completed"):
            continue
        event_day = str(event.get("date") or "")[:10]
        if event_day and event_day >= slate_date.isoformat():
            continue
        comps = comp.get("competitors") or []
        me = next(
            (c for c in comps if str((c.get("team") or {}).get("id")) == str(team_id)),
            None,
        )
        if me is None:
            continue
        opp = next((c for c in comps if c is not me), None)
        scored = _score_value(me.get("score"))
        opp_scored = _score_value((opp or {}).get("score"))
        if scored is None or opp_scored is None:
            continue
        games.append(
            {
                "date": event_day,
                "opponent": ((opp or {}).get("team") or {}).get("displayName", ""),
                "home": me.get("homeAway") == "home",
                "score_for": scored,
                "score_against": opp_scored,
                "win": bool(me.get("winner")),
            }
        )
    games.sort(key=lambda item: item["date"], reverse=True)
    sample = games[:last_n]
    l5 = sample[:5]

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(items)
        if not count:
            return {
                "games": 0,
                "wins": 0,
                "losses": 0,
                "win_pct": 0.5,
                "avg_for": 0.0,
                "avg_against": 0.0,
                "totals": [],
            }
        wins = sum(1 for item in items if item["win"])
        scored = sum(float(item["score_for"]) for item in items)
        against = sum(float(item["score_against"]) for item in items)
        return {
            "games": count,
            "wins": wins,
            "losses": count - wins,
            "win_pct": round(wins / count, 4),
            "avg_for": round(scored / count, 2),
            "avg_against": round(against / count, 2),
            "totals": [float(item["score_for"]) + float(item["score_against"]) for item in items],
        }

    return {
        "verified": len(sample) >= min(last_n, 5),
        "l5": summarize(l5),
        "l10": summarize(sample),
        "games": sample,
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/{path}/teams/{team_id}/schedule",
    }


def get_league_injuries(sport: str) -> dict[str, Any]:
    path = espn_path_for(sport)
    if not path:
        return {"verified": False, "by_team": {}, "source_id": SOURCE_ID}
    try:
        data = _get(f"{SOURCE_API}/{path}/injuries", cache_ttl=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN injuries unavailable for %s: %s", sport, exc)
        return {"verified": False, "by_team": {}, "source_id": SOURCE_ID, "error": str(exc)}
    by_team: dict[str, list[dict[str, Any]]] = {}
    for team_block in data.get("injuries") or []:
        team_name = str(team_block.get("displayName") or "")
        entries = []
        for item in team_block.get("injuries") or []:
            athlete = item.get("athlete") or {}
            entries.append(
                {
                    "id": athlete.get("id") or item.get("id"),
                    "name": athlete.get("displayName") or item.get("shortComment") or "",
                    "status": item.get("status") or "",
                    "detail": item.get("longComment") or item.get("shortComment") or "",
                }
            )
        if team_name:
            by_team[team_name] = entries
    return {
        "verified": True,
        "by_team": by_team,
        "team_count": len(by_team),
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/{path}/injuries",
    }


def injuries_for_teams(
    injury_feed: dict[str, Any], home_team: str, away_team: str
) -> dict[str, Any]:
    by_team = injury_feed.get("by_team") or {}
    home = _lookup_team_injuries(by_team, home_team)
    away = _lookup_team_injuries(by_team, away_team)
    home_matched = _team_matched(by_team, home_team)
    away_matched = _team_matched(by_team, away_team)
    # Feed HTTP success alone is not enough — both clubs must resolve in the report.
    verified = bool(injury_feed.get("verified")) and home_matched and away_matched
    return {
        "verified": verified,
        "home_matched": home_matched,
        "away_matched": away_matched,
        "home": home,
        "away": away,
        "home_out": sum(1 for item in home if _is_out(item.get("status", ""))),
        "away_out": sum(1 for item in away if _is_out(item.get("status", ""))),
        "source_id": SOURCE_ID,
    }


def _best_team_key(by_team: dict[str, list], team_name: str) -> str | None:
    """Resolve Odds/ESPN team labels onto injury-report keys without State collisions."""
    if not team_name:
        return None
    if team_name in by_team:
        return team_name
    needle = _norm(team_name)
    if not needle:
        return None
    best_key: str | None = None
    best_score = 0
    for name in by_team:
        hay = _norm(name)
        if not hay:
            continue
        if hay == needle or hay in needle or needle in hay:
            score = 10 + _name_overlap(team_name, name)
        else:
            score = _name_overlap(team_name, name)
        if score > best_score:
            best_score = score
            best_key = name
    # Require a real identity signal (mascot bonus or 2+ meaningful tokens).
    return best_key if best_score >= 2 else None


def _team_matched(by_team: dict[str, list], team_name: str) -> bool:
    return _best_team_key(by_team, team_name) is not None


def _lookup_team_injuries(by_team: dict[str, list], team_name: str) -> list[dict[str, Any]]:
    key = _best_team_key(by_team, team_name)
    if key is None:
        return []
    return list(by_team.get(key) or [])


def _parse_event(event: dict[str, Any], *, sport: str) -> dict[str, Any] | None:
    comps_wrap = (event.get("competitions") or [{}])[0]
    competitors = comps_wrap.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    venue = comps_wrap.get("venue") or {}
    address = venue.get("address") or {}
    status = (comps_wrap.get("status") or {}).get("type") or {}
    return {
        "sport": sport.lower(),
        "event_id": str(event.get("id") or ""),
        "name": event.get("name") or "",
        "short_name": event.get("shortName") or "",
        "start_time": event.get("date"),
        "home_team": (home.get("team") or {}).get("displayName") or "",
        "away_team": (away.get("team") or {}).get("displayName") or "",
        "home_id": str((home.get("team") or {}).get("id") or ""),
        "away_id": str((away.get("team") or {}).get("id") or ""),
        "home_score": _score_value(home.get("score")),
        "away_score": _score_value(away.get("score")),
        "status": status.get("name") or status.get("description") or "",
        "completed": bool(status.get("completed")),
        "venue": venue.get("fullName") or "",
        "venue_id": venue.get("id"),
        "indoor": bool(venue.get("indoor")),
        "city": address.get("city") or "",
        "state": address.get("state") or "",
        "country": address.get("country") or "",
        "latitude": _coord_value(venue.get("latitude") or address.get("latitude")),
        "longitude": _coord_value(venue.get("longitude") or address.get("longitude")),
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/{espn_path_for(sport)}/scoreboard",
    }


def _score_value(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        if raw.get("value") is not None:
            return float(raw["value"])
        display = raw.get("displayValue")
        if display is not None and str(display).replace(".", "", 1).isdigit():
            return float(display)
    if isinstance(raw, str) and raw.replace(".", "", 1).isdigit():
        return float(raw)
    return None


_GENERIC_NAME_TOKENS = frozenset(
    {
        "fc",
        "sc",
        "the",
        "at",
        "of",
        "and",
        "club",
        "city",
        "town",
        "university",
        "univ",
        "college",
        "st",
        "state",
        "team",
        "football",
        "basketball",
        "soccer",
        "hockey",
    }
)


def _name_tokens(value: str) -> set[str]:
    return {token for token in _norm(value).split() if token and token not in _GENERIC_NAME_TOKENS}


def _name_overlap(a: str, b: str) -> int:
    """Score school/club name overlap without weak tokens like 'state'/'university'."""
    na = _name_tokens(a)
    nb = _name_tokens(b)
    if not na or not nb:
        return 0
    shared = na & nb
    score = len(shared)
    # Bonus when the distinctive last token (mascot / nickname) matches.
    a_last = (_norm(a).split() or [""])[-1]
    b_last = (_norm(b).split() or [""])[-1]
    if a_last and a_last == b_last and a_last not in _GENERIC_NAME_TOKENS:
        score += 2
    return score


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()


def _coord_value(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _is_out(status: str) -> bool:
    text = (status or "").lower()
    return any(token in text for token in ("out", "injured reserve", "ir", "doubtful"))


def _empty_form() -> dict[str, Any]:
    empty = {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_pct": 0.5,
        "avg_for": 0.0,
        "avg_against": 0.0,
        "totals": [],
    }
    return {"verified": False, "l5": empty, "l10": empty, "games": [], "source_id": SOURCE_ID}


def _get(url: str, params: dict[str, Any] | None = None, *, cache_ttl: int = 120) -> dict[str, Any]:
    key = f"{url}?{sorted((params or {}).items())}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < cache_ttl:
        return cached[1]

    urls = [url]
    if url.startswith(SOURCE_API):
        urls.append(url.replace(SOURCE_API, SOURCE_API_FALLBACK, 1))
    elif url.startswith(SOURCE_API_FALLBACK):
        urls.append(url.replace(SOURCE_API_FALLBACK, SOURCE_API, 1))

    last_error: Exception | None = None
    for candidate in urls:
        try:
            response = httpx.get(
                candidate, params=params, timeout=TIMEOUT, headers=_HEADERS
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("unexpected ESPN payload")
            _CACHE[key] = (now, data)
            return data
        except Exception as exc:  # noqa: BLE001 — try fallback host before failing
            last_error = exc
            logger.warning("ESPN fetch failed for %s: %s", candidate, exc)
    assert last_error is not None
    raise last_error


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
