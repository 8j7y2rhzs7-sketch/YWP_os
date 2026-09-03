"""Live MLB data provider using official MLB Stats API public endpoints.

The endpoints used here are currently accessible without an API key. Product
owners remain responsible for reviewing MLB's terms and any licensing needs.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from threading import RLock
from time import monotonic
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE = "https://statsapi.mlb.com/api"
TIMEOUT = 15.0
SOURCE_HOME = "https://www.mlb.com"
SOURCE_API = "https://statsapi.mlb.com"
USER_AGENT = "YWP-OS/3.0 (official MLB data adapter; contact the app owner)"

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = RLock()


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


def _get_sync(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    cache_ttl: int = 60,
) -> dict[str, Any]:
    clean_params = params or {}
    cache_key = f"{path}?{sorted(clean_params.items())}"
    now = monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(f"{BASE}{path}", params=clean_params)
        resp.raise_for_status()
        payload = resp.json()

    with _cache_lock:
        if len(_cache) >= 512:
            expired = [key for key, value in _cache.items() if value[0] <= now]
            for key in expired:
                _cache.pop(key, None)
            if len(_cache) >= 512:
                _cache.pop(next(iter(_cache)))
        _cache[cache_key] = (now + max(0, cache_ttl), payload)
    return payload


def probe_mlb_api() -> dict[str, Any]:
    """Return a secret-free connectivity result for the provider health route."""
    try:
        payload = _get_sync("/v1/sports/1", cache_ttl=60)
        sports = payload.get("sports", [])
        return {
            "ok": bool(sports),
            "status": "connected" if sports else "unexpected_payload",
            "provider": "MLB Stats API",
            "base_url": SOURCE_API,
        }
    except Exception as exc:
        logger.warning("MLB Stats API health probe failed: %s", exc)
        return {
            "ok": False,
            "status": "unavailable",
            "provider": "MLB Stats API",
            "base_url": SOURCE_API,
        }


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def player_headshot_url(player_id: int | None) -> str | None:
    if not player_id:
        return None
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        "d_people:generic:headshot:67:current.png/w_180,q_auto:best/"
        f"v1/people/{player_id}/headshot/silo/current"
    )


def team_logo_url(team_id: int | None) -> str | None:
    if not team_id:
        return None
    return f"https://midfield.mlbstatic.com/v1/team/{team_id}/spots/96"


def get_schedule(slate_date: date) -> list[dict[str, Any]]:
    """Return today's MLB games with probable pitchers and venue."""
    data = _get_sync(
        "/v1/schedule",
        {
            "sportId": 1,
            "date": slate_date.isoformat(),
            "hydrate": "probablePitcher,team,venue,linescore,weather,officials",
        },
        cache_ttl=45,
    )
    games: list[dict[str, Any]] = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            status_data = g.get("status", {})
            status = status_data.get("abstractGameState", "")
            # Pregame slate only. Live/final games belong to lock-check and grading, not new cards.
            if status in ("Final", "Live", "Postponed", "Cancelled"):
                continue
            away = g.get("teams", {}).get("away", {})
            home = g.get("teams", {}).get("home", {})
            away_record = away.get("leagueRecord", {})
            home_record = home.get("leagueRecord", {})
            venue = g.get("venue", {}) or {}
            location = venue.get("location", {}) or {}
            games.append(
                {
                    "game_pk": g["gamePk"],
                    "game_date": g.get("gameDate"),
                    "status": status,
                    "detailed_status": status_data.get("detailedState", status),
                    "away_team": away.get("team", {}).get("name", ""),
                    "away_id": away.get("team", {}).get("id"),
                    "away_record": (f"{away_record.get('wins', 0)}-{away_record.get('losses', 0)}"),
                    "away_pitcher": _pitcher_info(away.get("probablePitcher")),
                    "home_team": home.get("team", {}).get("name", ""),
                    "home_id": home.get("team", {}).get("id"),
                    "home_record": (f"{home_record.get('wins', 0)}-{home_record.get('losses', 0)}"),
                    "home_pitcher": _pitcher_info(home.get("probablePitcher")),
                    "venue": venue.get("name", ""),
                    "venue_id": venue.get("id"),
                    "venue_lat": location.get("defaultCoordinates", {}).get("latitude")
                    if isinstance(location.get("defaultCoordinates"), dict)
                    else location.get("lat"),
                    "venue_lon": location.get("defaultCoordinates", {}).get("longitude")
                    if isinstance(location.get("defaultCoordinates"), dict)
                    else location.get("lng") or location.get("lon"),
                    "officials": g.get("officials") or [],
                    "weather": g.get("weather") or {},
                    "mlb_game_url": f"https://www.mlb.com/gameday/{g['gamePk']}",
                }
            )
    return games


def _pitcher_info(p: dict[str, Any] | None) -> dict[str, Any] | None:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "name": p.get("fullName", ""),
        "era": p.get("stats", [{}])[0].get("stats", {}).get("era") if p.get("stats") else None,
    }


# ---------------------------------------------------------------------------
# Player game logs (L5 / L10)
# ---------------------------------------------------------------------------


def get_player_game_log(
    player_id: int, season: int | None = None, last_n: int = 10
) -> list[dict[str, Any]]:
    """Fetch a batter's recent game log."""
    season = season or date.today().year
    data = _get_sync(
        f"/v1/people/{player_id}/stats",
        {"stats": "gameLog", "group": "hitting", "season": season},
    )
    logs: list[dict[str, Any]] = []
    for split in _extract_splits(data):
        stat = split.get("stat", {})
        logs.append(
            {
                "date": split.get("date"),
                "opponent": split.get("opponent", {}).get("name", ""),
                "hits": stat.get("hits", 0),
                "at_bats": stat.get("atBats", 0),
                "home_runs": stat.get("homeRuns", 0),
                "rbi": stat.get("rbi", 0),
                "strikeouts": stat.get("strikeOuts", 0),
                "walks": stat.get("baseOnBalls", 0),
                "total_bases": stat.get("totalBases", 0),
                "avg": stat.get("avg"),
                "ops": stat.get("ops"),
            }
        )
    logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return logs[:last_n]


def get_pitcher_game_log(
    player_id: int, season: int | None = None, last_n: int = 10
) -> list[dict[str, Any]]:
    """Fetch a pitcher's recent game log."""
    season = season or date.today().year
    data = _get_sync(
        f"/v1/people/{player_id}/stats",
        {"stats": "gameLog", "group": "pitching", "season": season},
    )
    logs: list[dict[str, Any]] = []
    for split in _extract_splits(data):
        stat = split.get("stat", {})
        logs.append(
            {
                "date": split.get("date"),
                "opponent": split.get("opponent", {}).get("name", ""),
                "innings_pitched": stat.get("inningsPitched", "0"),
                "strikeouts": stat.get("strikeOuts", 0),
                "hits_allowed": stat.get("hits", 0),
                "runs": stat.get("runs", 0),
                "earned_runs": stat.get("earnedRuns", 0),
                "walks": stat.get("baseOnBalls", 0),
                "era": stat.get("era"),
                "pitches": stat.get("numberOfPitches", 0),
            }
        )
    logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return logs[:last_n]


def _extract_splits(data: dict[str, Any]) -> list[dict[str, Any]]:
    for group in data.get("stats", []):
        if group.get("splits"):
            return group["splits"]
    return []


# ---------------------------------------------------------------------------
# Season stats
# ---------------------------------------------------------------------------


def get_player_season_stats(
    player_id: int, group: str = "hitting", season: int | None = None
) -> dict[str, Any]:
    season = season or date.today().year
    data = _get_sync(
        f"/v1/people/{player_id}/stats",
        {"stats": "season", "group": group, "season": season},
    )
    for stat_group in data.get("stats", []):
        for split in stat_group.get("splits", []):
            return split.get("stat", {})
    return {}


# ---------------------------------------------------------------------------
# Team roster
# ---------------------------------------------------------------------------


def get_team_roster(team_id: int, roster_type: str = "active") -> list[dict[str, Any]]:
    data = _get_sync(f"/v1/teams/{team_id}/roster", {"rosterType": roster_type})
    roster: list[dict[str, Any]] = []
    for entry in data.get("roster", []):
        person = entry.get("person", {})
        roster.append(
            {
                "id": person.get("id"),
                "name": person.get("fullName", ""),
                "position": entry.get("position", {}).get("abbreviation", ""),
                "status": entry.get("status", {}).get("description", ""),
            }
        )
    return roster


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------


def get_standings(season: int | None = None) -> list[dict[str, Any]]:
    season = season or date.today().year
    data = _get_sync("/v1/standings", {"leagueId": "103,104", "season": season})
    teams: list[dict[str, Any]] = []
    for record in data.get("records", []):
        div = record.get("division", {}).get("name", "")
        for tr in record.get("teamRecords", []):
            split_records = tr.get("records", {}).get("splitRecords", [])
            last_ten = next(
                (item for item in split_records if item.get("type") == "lastTen"),
                {},
            )
            teams.append(
                {
                    "team": tr.get("team", {}).get("name", ""),
                    "team_id": tr.get("team", {}).get("id"),
                    "division": div,
                    "wins": tr.get("wins", 0),
                    "losses": tr.get("losses", 0),
                    "pct": tr.get("winningPercentage", ""),
                    "runs_scored": tr.get("runsScored", 0),
                    "runs_allowed": tr.get("runsAllowed", 0),
                    "streak": tr.get("streak", {}).get("streakCode", ""),
                    "last_10": f"{last_ten.get('wins', '?')}-{last_ten.get('losses', '?')}",
                }
            )
    return teams


# ---------------------------------------------------------------------------
# Live game feed
# ---------------------------------------------------------------------------


def get_live_feed(game_pk: int) -> dict[str, Any]:
    return _get_sync(f"/v1.1/game/{game_pk}/feed/live", cache_ttl=15)


def get_team_recent_form(
    team_id: int,
    slate_date: date,
    *,
    last_n: int = 10,
) -> dict[str, Any]:
    """Return official final-game form before the requested slate date."""
    start_date = slate_date - timedelta(days=30)
    end_date = slate_date - timedelta(days=1)
    data = _get_sync(
        "/v1/schedule",
        {
            "sportId": 1,
            "teamId": team_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": "linescore",
        },
        cache_ttl=600,
    )
    games: list[dict[str, Any]] = []
    for slate in data.get("dates", []):
        for game in slate.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            is_home = home.get("team", {}).get("id") == team_id
            team = home if is_home else away
            opponent = away if is_home else home
            runs_for = int(team.get("score", 0) or 0)
            runs_against = int(opponent.get("score", 0) or 0)
            games.append(
                {
                    "game_pk": game.get("gamePk"),
                    "date": game.get("gameDate", "")[:10],
                    "opponent": opponent.get("team", {}).get("name", ""),
                    "home": is_home,
                    "runs_for": runs_for,
                    "runs_against": runs_against,
                    "win": runs_for > runs_against,
                }
            )
    games.sort(key=lambda item: (item["date"], item["game_pk"] or 0), reverse=True)
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
                "avg_runs_for": 0.0,
                "avg_runs_against": 0.0,
                "run_diff_per_game": 0.0,
                "totals": [],
            }
        wins = sum(bool(item["win"]) for item in items)
        runs_for = sum(int(item["runs_for"]) for item in items)
        runs_against = sum(int(item["runs_against"]) for item in items)
        return {
            "games": count,
            "wins": wins,
            "losses": count - wins,
            "win_pct": round(wins / count, 4),
            "avg_runs_for": round(runs_for / count, 2),
            "avg_runs_against": round(runs_against / count, 2),
            "run_diff_per_game": round((runs_for - runs_against) / count, 2),
            "totals": [int(item["runs_for"]) + int(item["runs_against"]) for item in items],
        }

    return {
        "verified": len(sample) >= min(last_n, 5),
        "l5": summarize(l5),
        "l10": summarize(sample),
        "games": sample,
        "source_url": (
            f"{SOURCE_API}/api/v1/schedule?sportId=1&teamId={team_id}"
            f"&startDate={start_date.isoformat()}&endDate={end_date.isoformat()}"
        ),
    }


def get_team_availability(team_id: int) -> dict[str, Any]:
    """Use MLB's 40-man roster status to identify active and injured-list players."""
    data = _get_sync(
        f"/v1/teams/{team_id}/roster",
        {"rosterType": "40Man", "hydrate": "person"},
        cache_ttl=300,
    )
    active: list[dict[str, Any]] = []
    injured: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for entry in data.get("roster", []):
        status = entry.get("status", {})
        item = {
            "id": entry.get("person", {}).get("id"),
            "name": entry.get("person", {}).get("fullName", ""),
            "position": entry.get("position", {}).get("abbreviation", ""),
            "status_code": status.get("code", ""),
            "status": status.get("description", "Unknown"),
        }
        description = item["status"].lower()
        code = item["status_code"]
        if "injur" in description or code.startswith("D"):
            injured.append(item)
        elif code == "A" or description == "active":
            active.append(item)
        else:
            unavailable.append(item)
    return {
        "verified": bool(data.get("roster")),
        "active": active,
        "injured": injured,
        "unavailable": unavailable,
        "source_url": f"{SOURCE_API}/api/v1/teams/{team_id}/roster?rosterType=40Man",
    }


def get_game_context(game_pk: int) -> dict[str, Any]:
    """Extract posted batting orders, official weather, live state, and bullpen lists."""
    data = get_live_feed(game_pk)
    game_data = data.get("gameData", {})
    live_data = data.get("liveData", {})
    boxscore = live_data.get("boxscore", {}).get("teams", {})

    def side_context(side: str) -> dict[str, Any]:
        team_box = boxscore.get(side, {})
        order = team_box.get("battingOrder", [])
        players = team_box.get("players", {})
        lineup = []
        for player_id in order:
            record = players.get(f"ID{player_id}", {})
            person = record.get("person", {})
            lineup.append(
                {
                    "id": player_id,
                    "name": person.get("fullName", ""),
                    "position": record.get("position", {}).get("abbreviation", ""),
                }
            )
        return {
            "lineup_confirmed": len(order) >= 9,
            "lineup": lineup,
            "pitchers": team_box.get("pitchers", []),
            "bullpen": team_box.get("bullpen", []),
        }

    weather = game_data.get("weather") or {}
    status = game_data.get("status") or {}
    venue = game_data.get("venue") or {}
    officials = (
        live_data.get("boxscore", {}).get("officials")
        or game_data.get("officials")
        or []
    )
    return {
        "verified": bool(game_data),
        "status": status.get("abstractGameState", "Unknown"),
        "detailed_status": status.get("detailedState", "Unknown"),
        "home": side_context("home"),
        "away": side_context("away"),
        "weather": {
            "verified": bool(weather),
            "condition": weather.get("condition"),
            "temperature_f": weather.get("temp"),
            "wind": weather.get("wind"),
        },
        "venue": venue.get("name", ""),
        "venue_id": venue.get("id"),
        "officials": officials,
        "park_verified": bool(venue.get("name")),
        "umpire_verified": bool(officials),
        "source_url": f"{SOURCE_API}/api/v1.1/game/{game_pk}/feed/live",
        "gameday_url": f"https://www.mlb.com/gameday/{game_pk}",
    }


def get_bullpen_usage(team_id: int, slate_date: date, *, lookback_days: int = 3) -> dict[str, Any]:
    """Measure recent relief workload from official MLB box scores."""
    recent = get_team_recent_form(team_id, slate_date, last_n=lookback_days)
    appearances = 0
    pitches = 0
    relievers: dict[int, dict[str, Any]] = {}
    for game in recent["games"][:lookback_days]:
        game_pk = game.get("game_pk")
        if not game_pk:
            continue
        feed = get_live_feed(int(game_pk))
        teams = feed.get("gameData", {}).get("teams", {})
        side = "home" if teams.get("home", {}).get("id") == team_id else "away"
        team_box = feed.get("liveData", {}).get("boxscore", {}).get("teams", {}).get(side, {})
        pitcher_ids = team_box.get("pitchers", [])
        for pitcher_id in pitcher_ids[1:]:
            record = team_box.get("players", {}).get(f"ID{pitcher_id}", {})
            pitching = record.get("stats", {}).get("pitching", {})
            pitch_count = int(pitching.get("numberOfPitches", 0) or 0)
            appearances += 1
            pitches += pitch_count
            reliever = relievers.setdefault(
                pitcher_id,
                {
                    "id": pitcher_id,
                    "name": record.get("person", {}).get("fullName", ""),
                    "appearances": 0,
                    "pitches": 0,
                },
            )
            reliever["appearances"] += 1
            reliever["pitches"] += pitch_count
    return {
        "verified": bool(recent["games"]),
        "lookback_days": lookback_days,
        "appearances": appearances,
        "total_relief_pitches": pitches,
        "heavy_usage": pitches >= 120
        or any(item["appearances"] >= 3 for item in relievers.values()),
        "relievers": sorted(
            relievers.values(),
            key=lambda item: (item["appearances"], item["pitches"]),
            reverse=True,
        ),
        "source_url": recent["source_url"],
    }


# ---------------------------------------------------------------------------
# Helpers for candidate building
# ---------------------------------------------------------------------------


def compute_l5_stats(logs: list[dict[str, Any]], stat_key: str) -> dict[str, Any]:
    """Given a game log list, compute L5 avg, floor, misses vs a threshold."""
    values = [log.get(stat_key, 0) for log in logs[:5]]
    if not values:
        return {"avg": 0, "floor": 0, "median": 0, "values": []}
    values_sorted = sorted(values)
    avg = sum(values) / len(values)
    floor = values_sorted[0]
    median = values_sorted[len(values_sorted) // 2]
    return {
        "avg": round(avg, 2),
        "floor": floor,
        "median": median,
        "values": values,
    }


def pitcher_k_stats(logs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute pitcher strikeout stats from game log."""
    k_values = [log.get("strikeouts", 0) for log in logs[:5]]
    ip_values = [_baseball_innings(log.get("innings_pitched", "0")) for log in logs[:5]]
    if not k_values:
        return {"avg_k": 0, "floor_k": 0, "avg_ip": 0, "values": []}
    return {
        "avg_k": round(sum(k_values) / len(k_values), 2),
        "floor_k": min(k_values),
        "avg_ip": round(sum(ip_values) / len(ip_values), 2),
        "values": k_values,
    }


def _baseball_innings(value: object) -> float:
    """Convert MLB's 5.1/5.2 outs notation into fractional innings."""
    text = str(value or "0")
    whole_text, separator, outs_text = text.partition(".")
    try:
        whole = int(whole_text)
        outs = int(outs_text or 0) if separator else 0
    except ValueError:
        return 0.0
    return whole + outs / 3 if outs in {0, 1, 2} else 0.0
