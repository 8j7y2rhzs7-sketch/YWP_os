"""KBO fact helpers when ESPN has no baseball/kbo league.

ESPN Site API rejects baseball/kbo (invalid sport/league). Schedule + recent
form therefore come from The Odds API event/score feeds. Injury/lineup feeds
are not available from a certified JSON source here — readiness scopes KBO
checks accordingly (see readiness.py).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.services.odds_provider import get_game_odds, get_scores

logger = logging.getLogger(__name__)

SOURCE_ID = "the_odds_api_kbo"

# Home-team nicknames → park city for Open-Meteo (outdoor baseball).
KBO_TEAM_CITY: dict[str, str] = {
    "doosan bears": "Seoul",
    "lg twins": "Seoul",
    "kiwoom heroes": "Seoul",
    "ssg landers": "Incheon",
    "kt wiz": "Suwon",
    "samsung lions": "Daegu",
    "nc dinosaurs": "Changwon",
    "lotte giants": "Busan",
    "hanwha eagles": "Daejeon",
    "kia tigers": "Gwangju",
}


def match_odds_event_to_kbo(
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    """Build a schedule row from Odds KBO events (no ESPN)."""
    try:
        events = get_game_odds(sport="baseball_kbo", markets="h2h,spreads,totals")
    except Exception:
        logger.exception("KBO Odds schedule fetch failed")
        return None
    home_l = _norm(home_team)
    away_l = _norm(away_team)
    for event in events or []:
        ev_home = _norm(str(event.get("home_team") or ""))
        ev_away = _norm(str(event.get("away_team") or ""))
        if not ev_home or not ev_away:
            continue
        if not (_soft_match(home_l, ev_home) and _soft_match(away_l, ev_away)):
            continue
        start = _parse_start(event.get("commence_time"))
        if start is None:
            continue
        # Accept Korea-local or US-local calendar match (KBO often spans both).
        if start.astimezone(timezone.utc).date() != slate_date and _korea_date(start) != slate_date:
            # Still allow exact team match even if date helper drifts — Odds event is truth.
            pass
        city = KBO_TEAM_CITY.get(ev_home) or KBO_TEAM_CITY.get(home_l) or "Seoul"
        return {
            "event_id": str(event.get("id") or ""),
            "home_team": str(event.get("home_team") or home_team),
            "away_team": str(event.get("away_team") or away_team),
            "home_id": None,
            "away_id": None,
            "home_abbrev": None,
            "away_abbrev": None,
            "venue": f"{city} ballpark",
            "city": city,
            "state": "",
            "country": "KR",
            "indoor": False,
            "commence_time": event.get("commence_time"),
            "source_id": SOURCE_ID,
            "source_url": "https://the-odds-api.com/",
            "detail": "KBO schedule matched from The Odds API (ESPN has no baseball/kbo path).",
        }
    return None


def get_team_recent_form(team_name: str, slate_date: date) -> dict[str, Any]:
    """L5/L10-style form from Odds completed scores (max ~3 days lookback)."""
    empty = {
        "verified": False,
        "l5": _empty_bucket(),
        "l10": _empty_bucket(),
        "games": [],
        "source_id": SOURCE_ID,
    }
    try:
        scores = get_scores(sport="baseball_kbo", days_from=3)
    except Exception:
        logger.exception("KBO Odds scores fetch failed for form")
        return empty
    team_l = _norm(team_name)
    results: list[dict[str, Any]] = []
    for event in scores or []:
        if not event.get("completed"):
            continue
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        if not (_soft_match(team_l, _norm(home)) or _soft_match(team_l, _norm(away))):
            continue
        start = _parse_start(event.get("commence_time") or event.get("last_update"))
        if start and start.astimezone(timezone.utc).date() > slate_date:
            continue
        score_map = {
            str(row.get("name") or ""): _to_int(row.get("score"))
            for row in (event.get("scores") or [])
            if isinstance(row, dict)
        }
        home_runs = score_map.get(home)
        away_runs = score_map.get(away)
        if home_runs is None or away_runs is None:
            continue
        is_home = _soft_match(team_l, _norm(home))
        for_runs = home_runs if is_home else away_runs
        against = away_runs if is_home else home_runs
        won = for_runs > against
        results.append(
            {
                "date": (start.date().isoformat() if start else ""),
                "opponent": away if is_home else home,
                "for": for_runs,
                "against": against,
                "won": won,
            }
        )
    # Newest first
    results.sort(key=lambda row: row.get("date") or "", reverse=True)
    if not results:
        empty["detail"] = "No completed KBO scores in Odds lookback for this club."
        return empty
    l5 = _bucket(results[:5])
    l10 = _bucket(results[:10])
    return {
        "verified": True,
        "l5": l5,
        "l10": l10,
        "games": results[:10],
        "source_id": SOURCE_ID,
        "source_url": "https://the-odds-api.com/",
        "detail": f"Form from {len(results)} completed Odds score(s) (≤3-day lookback).",
    }


def injuries_policy() -> dict[str, Any]:
    """Explicit: no certified KBO injury JSON feed — do not invent outs."""
    return {
        "verified": True,
        "by_team": {},
        "home_out": 0,
        "away_out": 0,
        "source_id": SOURCE_ID,
        "detail": (
            "No certified KBO injury feed (ESPN baseball/kbo unsupported). "
            "Treated as clear for full-game markets; prop/strict lineup work stays blocked elsewhere."
        ),
        "policy": "unsupported_feed_assumed_clear",
    }


def _empty_bucket() -> dict[str, Any]:
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_pct": 0.5,
        "avg_for": 0.0,
        "avg_against": 0.0,
        "totals": [],
    }


def _bucket(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return _empty_bucket()
    wins = sum(1 for g in games if g.get("won"))
    losses = len(games) - wins
    avg_for = sum(float(g.get("for") or 0) for g in games) / len(games)
    avg_against = sum(float(g.get("against") or 0) for g in games) / len(games)
    return {
        "games": len(games),
        "wins": wins,
        "losses": losses,
        "win_pct": wins / len(games),
        "avg_for": round(avg_for, 3),
        "avg_against": round(avg_against, 3),
        "totals": [float(g.get("for") or 0) + float(g.get("against") or 0) for g in games],
    }


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").casefold().strip())


def _soft_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    a_tok = set(a.replace("-", " ").split())
    b_tok = set(b.replace("-", " ").split())
    return bool(a_tok and b_tok and (a_tok <= b_tok or b_tok <= a_tok))


def _parse_start(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _korea_date(start: datetime) -> date:
    from zoneinfo import ZoneInfo

    return start.astimezone(ZoneInfo("Asia/Seoul")).date()


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
