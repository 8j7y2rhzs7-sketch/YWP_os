"""CollegeFootballData (CFBD) — free/paid JSON API for NCAA football facts.

Free tier requires CFBD_API_KEY (Bearer). Used as NCAAF schedule/form backup when
ESPN matching is thin. Never supplies sportsbook prices.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SOURCE_ID = "college_football_data"
SOURCE_API = "https://api.collegefootballdata.com"
TIMEOUT = 20.0
_CACHE: dict[str, tuple[float, Any]] = {}

_GENERIC = frozenset(
    {
        "the",
        "of",
        "and",
        "at",
        "university",
        "univ",
        "college",
        "st",
        "state",
        "football",
        "team",
    }
)


def cfbd_configured() -> bool:
    return bool((settings.cfbd_api_key or "").strip())


def get_teams(*, year: int | None = None) -> list[dict[str, Any]]:
    if not cfbd_configured():
        return []
    params: dict[str, Any] = {}
    if year:
        params["year"] = year
    data = _get("/teams", params=params, cache_ttl=86_400)
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def get_games(
    *,
    year: int,
    team: str | None = None,
    week: int | None = None,
    season_type: str = "regular",
) -> list[dict[str, Any]]:
    if not cfbd_configured():
        return []
    params: dict[str, Any] = {"year": year, "seasonType": season_type}
    if team:
        params["team"] = team
    if week is not None:
        params["week"] = week
    data = _get("/games", params=params, cache_ttl=3_600)
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def resolve_team_name(label: str, *, year: int | None = None) -> str | None:
    """Map Odds/ESPN labels onto a CFBD school name."""
    teams = get_teams(year=year)
    if not teams or not label:
        return None
    needle = _norm(label)
    best: str | None = None
    best_score = 0
    for row in teams:
        school = str(row.get("school") or "")
        mascot = str(row.get("mascot") or "")
        display = f"{school} {mascot}".strip()
        for candidate in (school, display, str(row.get("alt_name1") or ""), str(row.get("alt_name2") or "")):
            if not candidate:
                continue
            hay = _norm(candidate)
            if hay == needle or hay in needle or needle in hay:
                score = 10 + _overlap(label, candidate)
            else:
                score = _overlap(label, candidate)
            if score > best_score:
                best_score = score
                best = school
    return best if best_score >= 2 else None


def get_team_recent_form(team_label: str, slate_date: date) -> dict[str, Any]:
    """Build L5/L10 form from completed CFBD games for one school."""
    if not cfbd_configured():
        return _empty_form("cfbd_api_key_missing")
    school = resolve_team_name(team_label, year=slate_date.year)
    if not school:
        return _empty_form("team_unresolved")
    games = get_games(year=slate_date.year, team=school)
    # Include prior season tail when early in the year.
    if slate_date.month <= 2:
        games = get_games(year=slate_date.year - 1, team=school) + games
    completed: list[dict[str, Any]] = []
    for game in games:
        if not game.get("completed"):
            continue
        start = str(game.get("startDate") or game.get("start_date") or "")[:10]
        if start and start >= slate_date.isoformat():
            continue
        home = str(game.get("homeTeam") or game.get("home_team") or "")
        away = str(game.get("awayTeam") or game.get("away_team") or "")
        home_points = game.get("homePoints", game.get("home_points"))
        away_points = game.get("awayPoints", game.get("away_points"))
        if home_points is None or away_points is None:
            continue
        is_home = _norm(home) == _norm(school) or school.lower() in home.lower()
        scored = float(home_points if is_home else away_points)
        against = float(away_points if is_home else home_points)
        completed.append(
            {
                "date": start,
                "opponent": away if is_home else home,
                "home": is_home,
                "score_for": scored,
                "score_against": against,
                "win": scored > against,
            }
        )
    completed.sort(key=lambda item: item["date"], reverse=True)
    sample = completed[:10]
    l5 = sample[:5]
    if len(sample) < 5:
        return {
            **_empty_form("insufficient_games"),
            "school": school,
            "games": sample,
            "source_id": SOURCE_ID,
        }

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        count = len(items)
        wins = sum(1 for item in items if item["win"])
        return {
            "games": count,
            "wins": wins,
            "losses": count - wins,
            "win_pct": (wins / count) if count else 0.5,
            "avg_for": (sum(item["score_for"] for item in items) / count) if count else 0.0,
            "avg_against": (sum(item["score_against"] for item in items) / count) if count else 0.0,
            "totals": [item["score_for"] + item["score_against"] for item in items],
        }

    return {
        "verified": True,
        "school": school,
        "l5": summarize(l5),
        "l10": summarize(sample),
        "games": sample,
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/games",
    }


def match_odds_event_to_cfbd(
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    if not cfbd_configured():
        return None
    year = slate_date.year if slate_date.month >= 7 else slate_date.year - 1
    home = resolve_team_name(home_team, year=year)
    away = resolve_team_name(away_team, year=year)
    if not home or not away:
        return None
    games = get_games(year=year, team=home)
    target = slate_date.isoformat()
    for game in games:
        start = str(game.get("startDate") or game.get("start_date") or "")[:10]
        if start != target:
            continue
        game_home = str(game.get("homeTeam") or game.get("home_team") or "")
        game_away = str(game.get("awayTeam") or game.get("away_team") or "")
        if _norm(game_home) != _norm(home) and home.lower() not in game_home.lower():
            continue
        if _norm(game_away) != _norm(away) and away.lower() not in game_away.lower():
            continue
        venue = game.get("venue") or {}
        if isinstance(venue, str):
            venue = {"name": venue}
        return {
            "sport": "ncaaf",
            "event_id": str(game.get("id") or ""),
            "name": f"{game_away} @ {game_home}",
            "start_time": game.get("startDate") or game.get("start_date"),
            "home_team": game_home,
            "away_team": game_away,
            "home_id": str(game.get("homeId") or game.get("home_id") or ""),
            "away_id": str(game.get("awayId") or game.get("away_id") or ""),
            "venue": venue.get("name") or game.get("venue") or "",
            "indoor": bool(venue.get("dome") or game.get("neutralSite") is False and False),
            "city": venue.get("city") or "",
            "state": venue.get("state") or "",
            "country": "USA",
            "latitude": _float_or_none(venue.get("latitude")),
            "longitude": _float_or_none(venue.get("longitude")),
            "source_id": SOURCE_ID,
            "source_url": f"{SOURCE_API}/games",
        }
    return None


def _get(path: str, params: dict[str, Any] | None = None, *, cache_ttl: int) -> Any:
    key = f"{path}?{sorted((params or {}).items())}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < cache_ttl:
        return cached[1]
    headers = {
        "Authorization": f"Bearer {settings.cfbd_api_key}",
        "Accept": "application/json",
    }
    response = httpx.get(
        f"{SOURCE_API}{path}",
        params=params,
        headers=headers,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    _CACHE[key] = (now, data)
    return data


def _empty_form(detail: str) -> dict[str, Any]:
    empty = {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_pct": 0.5,
        "avg_for": 0.0,
        "avg_against": 0.0,
        "totals": [],
    }
    return {
        "verified": False,
        "l5": empty,
        "l10": empty,
        "games": [],
        "source_id": SOURCE_ID,
        "detail": detail,
    }


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()


def _overlap(a: str, b: str) -> int:
    na = {t for t in _norm(a).split() if t not in _GENERIC}
    nb = {t for t in _norm(b).split() if t not in _GENERIC}
    if not na or not nb:
        return 0
    score = len(na & nb)
    a_last = (_norm(a).split() or [""])[-1]
    b_last = (_norm(b).split() or [""])[-1]
    if a_last and a_last == b_last and a_last not in _GENERIC:
        score += 2
    return score


def _float_or_none(raw: Any) -> float | None:
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
