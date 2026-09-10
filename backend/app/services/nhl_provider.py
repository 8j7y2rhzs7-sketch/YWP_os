"""Official NHL Web API fact provider (api-web.nhle.com).

Used as a primary schedule/form source for NHL when ESPN is blocked or empty.
Market prices still come only from The Odds API.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE_API = "https://api-web.nhle.com/v1"
SOURCE_ID = "nhl_web_api"
TIMEOUT = 15.0
_CACHE: dict[str, tuple[float, Any]] = {}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 YWP-OS/3.3 NHL research",
    "Accept": "application/json",
}


def probe_nhl_api() -> dict[str, Any]:
    try:
        stamp = date.today().isoformat()
        data = _get(f"{SOURCE_API}/schedule/{stamp}", cache_ttl=60)
        week = data.get("gameWeek") or []
        games = sum(len(day.get("games") or []) for day in week)
        return {"status": "connected", "events": games, "source_id": SOURCE_ID}
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "error": str(exc), "source_id": SOURCE_ID}


def match_odds_event_to_nhl(
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    try:
        games = _games_for_date(slate_date)
        if not games:
            for delta in (-1, 1):
                games.extend(_games_for_date(slate_date + timedelta(days=delta)))
    except Exception as exc:  # noqa: BLE001
        logger.warning("NHL schedule unavailable: %s", exc)
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


def get_team_recent_form(
    team_abbrev: str,
    slate_date: date,
    *,
    last_n: int = 10,
) -> dict[str, Any]:
    abbrev = (team_abbrev or "").upper().strip()
    if not abbrev:
        return _empty_form()
    season = _season_id(slate_date)
    try:
        data = _get(f"{SOURCE_API}/club-schedule-season/{abbrev}/{season}", cache_ttl=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NHL club schedule failed for %s: %s", abbrev, exc)
        return _empty_form()

    games: list[dict[str, Any]] = []
    for item in data.get("games") or []:
        state = str(item.get("gameState") or "")
        if state not in {"OFF", "FINAL"} and not item.get("gameOutcome"):
            continue
        start = str(item.get("startTimeUTC") or "")[:10]
        if start and start >= slate_date.isoformat():
            continue
        home = item.get("homeTeam") or {}
        away = item.get("awayTeam") or {}
        home_abbr = str(home.get("abbrev") or "").upper()
        away_abbr = str(away.get("abbrev") or "").upper()
        if abbrev not in {home_abbr, away_abbr}:
            continue
        is_home = abbrev == home_abbr
        me = home if is_home else away
        opp = away if is_home else home
        scored = _score(me.get("score"))
        against = _score(opp.get("score"))
        if scored is None or against is None:
            continue
        games.append(
            {
                "date": start,
                "opponent": opp.get("placeName", {}).get("default")
                or opp.get("commonName", {}).get("default")
                or opp.get("abbrev")
                or "",
                "home": is_home,
                "score_for": scored,
                "score_against": against,
                "win": scored > against,
            }
        )
    games.sort(key=lambda row: row["date"], reverse=True)
    sample = games[:last_n]
    l5 = sample[:5]
    return {
        "verified": bool(sample),
        "l5": _summarize(l5),
        "l10": _summarize(sample),
        "games": sample,
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/club-schedule-season/{abbrev}/{season}",
        "team_abbrev": abbrev,
    }


def _games_for_date(slate_date: date) -> list[dict[str, Any]]:
    data = _get(f"{SOURCE_API}/schedule/{slate_date.isoformat()}", cache_ttl=120)
    out: list[dict[str, Any]] = []
    for day in data.get("gameWeek") or []:
        if day.get("date") != slate_date.isoformat():
            continue
        for game in day.get("games") or []:
            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            out.append(
                {
                    "id": str(game.get("id") or ""),
                    "home_team": _team_name(home),
                    "away_team": _team_name(away),
                    "home_abbrev": str(home.get("abbrev") or "").upper(),
                    "away_abbrev": str(away.get("abbrev") or "").upper(),
                    "home_id": str(home.get("id") or home.get("abbrev") or ""),
                    "away_id": str(away.get("id") or away.get("abbrev") or ""),
                    "venue": (game.get("venue") or {}).get("default") or "",
                    "indoor": True,
                    "city": "",
                    "state": "",
                    "country": "US",
                    "source_id": SOURCE_ID,
                    "source_url": f"{SOURCE_API}/schedule/{slate_date.isoformat()}",
                }
            )
    return out


def _team_name(team: dict[str, Any]) -> str:
    place = (team.get("placeName") or {}).get("default") or ""
    common = (team.get("commonName") or {}).get("default") or ""
    abbrev = team.get("abbrev") or ""
    joined = f"{place} {common}".strip()
    return joined or str(abbrev)


def _season_id(slate_date: date) -> str:
    # NHL season label is startYear+endYear, flipping around July.
    year = slate_date.year
    if slate_date.month >= 7:
        return f"{year}{year + 1}"
    return f"{year - 1}{year}"


def _summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
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


def _score(raw: Any) -> float | None:
    try:
        if raw is None or raw == "":
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _name_overlap(a: str, b: str) -> int:
    stop = {"fc", "sc", "the", "club", "city", "town", "university", "univ", "team"}
    a_tokens = {t for t in re.findall(r"[a-z0-9]+", (a or "").lower()) if t not in stop}
    b_tokens = {t for t in re.findall(r"[a-z0-9]+", (b or "").lower()) if t not in stop}
    if not a_tokens or not b_tokens:
        return 0
    return len(a_tokens & b_tokens)


def _get(url: str, params: dict[str, Any] | None = None, *, cache_ttl: int = 120) -> dict[str, Any]:
    key = f"{url}?{sorted((params or {}).items())}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and now - cached[0] < cache_ttl:
        return cached[1]
    response = httpx.get(url, params=params, timeout=TIMEOUT, headers=_HEADERS)
    response.raise_for_status()
    data = response.json()
    _CACHE[key] = (now, data)
    return data


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
