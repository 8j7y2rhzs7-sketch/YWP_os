"""BallDontLie NBA API — primary NBA schedule/form when BALLDONTLIE_API_KEY is set.

Free tier requires an API key (Authorization: Bearer). Never prices markets.
ESPN remains last-resort fallback only.
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

SOURCE_ID = "balldontlie"
SOURCE_API = "https://api.balldontlie.io/v1"
TIMEOUT = 20.0
_CACHE: dict[str, tuple[float, Any]] = {}
_GENERIC = frozenset({"the", "of", "and", "at", "city", "town"})


def balldontlie_configured() -> bool:
    return bool((settings.balldontlie_api_key or "").strip())


def probe_balldontlie() -> dict[str, Any]:
    if not balldontlie_configured():
        return {
            "ok": False,
            "status": "not_configured",
            "source_id": SOURCE_ID,
            "detail": "BALLDONTLIE_API_KEY is not set.",
        }
    try:
        data = _get("/teams", cache_ttl=3_600)
        teams = data.get("data") or []
        return {
            "ok": bool(teams),
            "status": "connected" if teams else "empty",
            "teams": len(teams),
            "source_id": SOURCE_ID,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "unavailable",
            "source_id": SOURCE_ID,
            "detail": str(exc)[:200],
        }


def match_odds_event_to_balldontlie(
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    if not balldontlie_configured():
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for delta in (0, -1, 1):
        day = slate_date + timedelta(days=delta)
        for game in _games_on_day(day):
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
    team_name: str,
    slate_date: date,
    *,
    last_n: int = 10,
) -> dict[str, Any]:
    if not balldontlie_configured() or not team_name.strip():
        return _empty_form()
    team = _resolve_team(team_name)
    if not team:
        return _empty_form()
    team_id = team.get("id")
    try:
        # Pull completed games for this club near the slate window.
        end = slate_date.isoformat()
        start = (slate_date - timedelta(days=120)).isoformat()
        data = _get(
            "/games",
            params={
                "team_ids[]": team_id,
                "start_date": start,
                "end_date": end,
                "per_page": 100,
            },
            cache_ttl=900,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("BallDontLie form miss: %s", exc)
        return _empty_form()
    rows: list[dict[str, Any]] = []
    for game in data.get("data") or []:
        if not game.get("status") or "Final" not in str(game.get("status")):
            # Also accept numeric scores as completed.
            if game.get("home_team_score") is None or game.get("visitor_team_score") is None:
                continue
        stamp = str(game.get("date") or "")[:10]
        if not stamp or stamp > slate_date.isoformat():
            continue
        home = (game.get("home_team") or {}).get("full_name") or ""
        away = (game.get("visitor_team") or {}).get("full_name") or ""
        hs = int(game.get("home_team_score") or 0)
        as_ = int(game.get("visitor_team_score") or 0)
        is_home = int((game.get("home_team") or {}).get("id") or -1) == int(team_id)
        gf = hs if is_home else as_
        ga = as_ if is_home else hs
        rows.append(
            {
                "date": stamp,
                "opponent": away if is_home else home,
                "goals_for": gf,
                "goals_against": ga,
                "result": "W" if gf > ga else ("L" if gf < ga else "D"),
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
        "source_url": f"{SOURCE_API}/games",
        "team_id": team_id,
    }


def _games_on_day(day: date) -> list[dict[str, Any]]:
    try:
        data = _get(
            "/games",
            params={"dates[]": day.isoformat(), "per_page": 100},
            cache_ttl=600,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for game in data.get("data") or []:
        home = (game.get("home_team") or {}).get("full_name") or ""
        away = (game.get("visitor_team") or {}).get("full_name") or ""
        if not home or not away:
            continue
        rows.append(
            {
                "sport": "nba",
                "event_id": str(game.get("id") or ""),
                "name": f"{away} @ {home}",
                "start_time": game.get("date"),
                "home_team": home,
                "away_team": away,
                "home_id": str(((game.get("home_team") or {}).get("id")) or ""),
                "away_id": str(((game.get("visitor_team") or {}).get("id")) or ""),
                "venue": "",
                "source_id": SOURCE_ID,
                "source_url": f"{SOURCE_API}/games",
            }
        )
    return rows


def _resolve_team(team_name: str) -> dict[str, Any] | None:
    try:
        data = _get("/teams", cache_ttl=3_600)
    except Exception:
        return None
    best = None
    best_score = 0
    for team in data.get("data") or []:
        full = str(team.get("full_name") or "")
        score = _name_overlap(team_name, full)
        if score > best_score:
            best_score = score
            best = team
    return best if best and best_score >= 2 else None


def _summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "win_pct": 0.5,
            "avg_for": 0.0,
            "avg_against": 0.0,
            "totals": [],
        }
    wins = sum(1 for g in games if g.get("result") == "W")
    losses = sum(1 for g in games if g.get("result") == "L")
    avg_for = sum(float(g.get("goals_for") or 0) for g in games) / len(games)
    avg_against = sum(float(g.get("goals_against") or 0) for g in games) / len(games)
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
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
        "Authorization": (settings.balldontlie_api_key or "").strip(),
        "Accept": "application/json",
        "User-Agent": "YWP-OS/3.3 balldontlie research",
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
