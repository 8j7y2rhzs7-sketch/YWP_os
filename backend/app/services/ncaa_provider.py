"""NCAA public scoreboard JSON — free, no auth.

Validated live (HTTP 200) at:
  https://data.ncaa.com/casablanca/scoreboard/football/fbs/{year}/{week}/scoreboard.json

Used as NCAAF schedule tertiary backup after ESPN + CFBD. Never prices markets.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE_ID = "ncaa_data_api"
SOURCE_API = "https://data.ncaa.com"
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


def get_fbs_scoreboard(*, year: int, week: int) -> list[dict[str, Any]]:
    """Return normalized FBS games for one NCAA week, or [] on miss."""
    if week < 1 or week > 16:
        return []
    path = f"/casablanca/scoreboard/football/fbs/{year}/{week:02d}/scoreboard.json"
    data = _get(path, cache_ttl=1_800)
    if not isinstance(data, dict):
        return []
    rows: list[dict[str, Any]] = []
    for entry in data.get("games") or []:
        game = entry.get("game") if isinstance(entry, dict) else None
        if not isinstance(game, dict):
            continue
        parsed = _parse_game(game, year=year, week=week)
        if parsed:
            rows.append(parsed)
    return rows


def match_odds_event_to_ncaa(
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    """Best-effort Odds team-name match against NCAA FBS scoreboard weeks."""
    year = slate_date.year if slate_date.month >= 7 else slate_date.year - 1
    best: dict[str, Any] | None = None
    best_score = 0
    for week in _candidate_weeks(slate_date, year=year):
        for game in get_fbs_scoreboard(year=year, week=week):
            start = str(game.get("start_date") or "")
            if start:
                try:
                    day = date.fromisoformat(start)
                except ValueError:
                    day = None
                if day is not None and abs((day - slate_date).days) > 1:
                    continue
            score = _overlap(home_team, game.get("home_team") or "") + _overlap(
                away_team, game.get("away_team") or ""
            )
            if score > best_score:
                best_score = score
                best = game
    if best is None or best_score < 2:
        return None
    return best


def probe_ncaa_api(*, year: int | None = None, week: int = 1) -> dict[str, Any]:
    season = year or date.today().year
    try:
        games = get_fbs_scoreboard(year=season, week=week)
        return {
            "status": "connected" if games else "empty",
            "year": season,
            "week": week,
            "games": len(games),
            "source_id": SOURCE_ID,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unavailable",
            "year": season,
            "week": week,
            "error": str(exc)[:200],
            "source_id": SOURCE_ID,
        }


def _candidate_weeks(slate_date: date, *, year: int) -> list[int]:
    # FBS roughly opens late August; map calendar date → week ±1.
    season_start = date(year, 8, 24)
    delta_days = (slate_date - season_start).days
    week = max(1, min(16, delta_days // 7 + 1))
    return sorted({max(1, week - 1), week, min(16, week + 1)})


def _parse_game(game: dict[str, Any], *, year: int, week: int) -> dict[str, Any] | None:
    home = game.get("home") or {}
    away = game.get("away") or {}
    home_names = home.get("names") if isinstance(home, dict) else {}
    away_names = away.get("names") if isinstance(away, dict) else {}
    if not isinstance(home_names, dict) or not isinstance(away_names, dict):
        return None
    home_team = str(home_names.get("short") or home_names.get("full") or "").strip()
    away_team = str(away_names.get("short") or away_names.get("full") or "").strip()
    if not home_team or not away_team:
        return None
    start_epoch = game.get("startTimeEpoch")
    start_date = ""
    start_iso: str | None = None
    try:
        if start_epoch is not None:
            start_dt = datetime.fromtimestamp(int(start_epoch), tz=timezone.utc)
            start_date = start_dt.date().isoformat()
            start_iso = start_dt.isoformat()
    except (TypeError, ValueError, OSError):
        start_iso = str(game.get("startTime") or "") or None
    return {
        "sport": "ncaaf",
        "event_id": str(game.get("gameID") or game.get("url") or ""),
        "name": f"{away_team} @ {home_team}",
        "start_time": start_iso,
        "start_date": start_date,
        "home_team": home_team,
        "away_team": away_team,
        "home_id": str(home_names.get("seo") or ""),
        "away_id": str(away_names.get("seo") or ""),
        "venue": "",
        "indoor": False,
        "city": "",
        "state": "",
        "country": "USA",
        "latitude": None,
        "longitude": None,
        "year": year,
        "week": week,
        "source_id": SOURCE_ID,
        "source_url": (
            f"{SOURCE_API}/casablanca/scoreboard/football/fbs/"
            f"{year}/{week:02d}/scoreboard.json"
        ),
    }


def _get(path: str, *, cache_ttl: int) -> Any:
    cached = _CACHE.get(path)
    now = time.time()
    if cached and now - cached[0] < cache_ttl:
        return cached[1]
    response = httpx.get(
        f"{SOURCE_API}{path}",
        headers={
            "User-Agent": "YWP-OS/3.2 trusted-research",
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
        follow_redirects=True,
    )
    if response.status_code == 404:
        _CACHE[path] = (now, {})
        return {}
    response.raise_for_status()
    data = response.json()
    _CACHE[path] = (now, data)
    return data


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()


def _overlap(a: str, b: str) -> int:
    na = {t for t in _norm(a).split() if t and t not in _GENERIC}
    nb = {t for t in _norm(b).split() if t and t not in _GENERIC}
    if not na or not nb:
        return 0
    score = len(na & nb)
    a_tokens = _norm(a).split()
    b_tokens = _norm(b).split()
    if a_tokens and b_tokens and a_tokens[0] == b_tokens[0] and a_tokens[0] not in _GENERIC:
        score += 2
    return score
