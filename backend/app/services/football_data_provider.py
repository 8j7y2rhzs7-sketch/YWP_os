"""Football-Data.org — primary soccer schedule/form when FOOTBALL_DATA_API_KEY is set.

Free tier covers major European competitions. Never supplies sportsbook prices.
ESPN remains a last-resort fallback in facts_cascade only.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SOURCE_ID = "football_data_org"
SOURCE_API = "https://api.football-data.org/v4"
TIMEOUT = 20.0
_CACHE: dict[str, tuple[float, Any]] = {}

# App sport → Football-Data competition code.
_COMP_BY_SPORT: dict[str, str] = {
    "epl": "PL",
    "mls": "MLS",
    "soccer": "PL",  # primary domestic slate; broaden via match search
}

_GENERIC = frozenset({"fc", "afc", "cf", "sc", "the", "united", "city", "town", "club"})


def football_data_configured() -> bool:
    return bool((settings.football_data_api_key or "").strip())


def probe_football_data() -> dict[str, Any]:
    if not football_data_configured():
        return {
            "ok": False,
            "status": "not_configured",
            "source_id": SOURCE_ID,
            "detail": "FOOTBALL_DATA_API_KEY is not set.",
        }
    try:
        data = _get("/competitions", cache_ttl=3_600)
        count = int((data or {}).get("count") or len((data or {}).get("competitions") or []))
        return {
            "ok": count > 0,
            "status": "connected" if count else "empty",
            "competitions": count,
            "source_id": SOURCE_ID,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "unavailable",
            "source_id": SOURCE_ID,
            "detail": str(exc)[:200],
        }


def match_odds_event_to_football_data(
    sport: str,
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    if not football_data_configured():
        return None
    sport_l = sport.lower()
    codes = [_COMP_BY_SPORT.get(sport_l, "PL")]
    if sport_l == "soccer":
        codes = ["PL", "PD", "SA", "BL1", "FL1", "CL", "MLS"]
    best: dict[str, Any] | None = None
    best_score = 0
    for code in codes:
        for delta in (0, -1, 1):
            day = slate_date + timedelta(days=delta)
            for game in _matches_for_day(code, day):
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
    sport: str,
    team_name: str,
    slate_date: date,
    *,
    last_n: int = 10,
) -> dict[str, Any]:
    if not football_data_configured() or not team_name.strip():
        return _empty_form()
    sport_l = sport.lower()
    code = _COMP_BY_SPORT.get(sport_l, "PL")
    try:
        data = _get(
            f"/competitions/{code}/matches",
            params={"status": "FINISHED", "limit": 50},
            cache_ttl=900,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Football-Data form miss: %s", exc)
        return _empty_form()
    rows: list[dict[str, Any]] = []
    needle = _norm(team_name)
    for match in data.get("matches") or []:
        home = ((match.get("homeTeam") or {}).get("name")) or ""
        away = ((match.get("awayTeam") or {}).get("name")) or ""
        score = (match.get("score") or {}).get("fullTime") or {}
        hg, ag = score.get("home"), score.get("away")
        if hg is None or ag is None:
            continue
        stamp = str(match.get("utcDate") or "")[:10]
        if not stamp or stamp > slate_date.isoformat():
            continue
        home_n, away_n = _norm(home), _norm(away)
        if needle not in {home_n, away_n} and not (
            _name_overlap(team_name, home) >= 2 or _name_overlap(team_name, away) >= 2
        ):
            continue
        is_home = _name_overlap(team_name, home) >= _name_overlap(team_name, away)
        gf = int(hg if is_home else ag)
        ga = int(ag if is_home else hg)
        if gf > ga:
            result = "W"
        elif gf < ga:
            result = "L"
        else:
            result = "D"
        rows.append(
            {
                "date": stamp,
                "opponent": away if is_home else home,
                "goals_for": gf,
                "goals_against": ga,
                "result": result,
                "home": is_home,
            }
        )
    rows.sort(key=lambda row: row["date"], reverse=True)
    sample = rows[:last_n]
    verified = len(sample) >= 5
    return {
        "verified": verified,
        "l5": _summarize(sample[:5]),
        "l10": _summarize(sample),
        "games": sample,
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/competitions/{code}/matches",
    }


def _matches_for_day(code: str, day: date) -> list[dict[str, Any]]:
    try:
        data = _get(
            f"/competitions/{code}/matches",
            params={"dateFrom": day.isoformat(), "dateTo": day.isoformat()},
            cache_ttl=600,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for match in data.get("matches") or []:
        home = ((match.get("homeTeam") or {}).get("name")) or ""
        away = ((match.get("awayTeam") or {}).get("name")) or ""
        if not home or not away:
            continue
        rows.append(
            {
                "sport": "soccer",
                "event_id": str(match.get("id") or ""),
                "name": f"{away} @ {home}",
                "start_time": match.get("utcDate"),
                "home_team": home,
                "away_team": away,
                "home_id": str(((match.get("homeTeam") or {}).get("id")) or ""),
                "away_id": str(((match.get("awayTeam") or {}).get("id")) or ""),
                "venue": "",
                "source_id": SOURCE_ID,
                "source_url": f"{SOURCE_API}/competitions/{code}/matches",
                "competition": code,
            }
        )
    return rows


def _summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "win_pct": 0.5,
            "avg_for": 0.0,
            "avg_against": 0.0,
            "totals": [],
        }
    wins = sum(1 for g in games if g.get("result") == "W")
    losses = sum(1 for g in games if g.get("result") == "L")
    draws = sum(1 for g in games if g.get("result") == "D")
    avg_for = sum(float(g.get("goals_for") or 0) for g in games) / len(games)
    avg_against = sum(float(g.get("goals_against") or 0) for g in games) / len(games)
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_pct": wins / len(games),
        "avg_for": round(avg_for, 3),
        "avg_against": round(avg_against, 3),
        "totals": [float(g.get("goals_for") or 0) + float(g.get("goals_against") or 0) for g in games],
    }


def _empty_form() -> dict[str, Any]:
    empty = {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "win_pct": 0.5,
        "avg_for": 0.0,
        "avg_against": 0.0,
        "totals": [],
    }
    return {
        "verified": False,
        "l5": dict(empty),
        "l10": dict(empty),
        "games": [],
        "source_id": SOURCE_ID,
    }


def _get(path: str, *, params: dict[str, Any] | None = None, cache_ttl: float = 300) -> dict[str, Any]:
    key = f"{path}|{sorted((params or {}).items())}"
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < cache_ttl:
        return cached[1]
    headers = {
        "X-Auth-Token": (settings.football_data_api_key or "").strip(),
        "Accept": "application/json",
        "User-Agent": "YWP-OS/3.3 football-data research",
    }
    with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
        response = client.get(f"{SOURCE_API}{path}", params=params or {})
        response.raise_for_status()
        data = response.json()
    _CACHE[key] = (time.time(), data)
    return data


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).strip()


def _tokens(value: str) -> set[str]:
    return {t for t in _norm(value).split() if t and t not in _GENERIC and len(t) > 1}


def _name_overlap(a: str, b: str) -> int:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0
    return len(ta & tb)
