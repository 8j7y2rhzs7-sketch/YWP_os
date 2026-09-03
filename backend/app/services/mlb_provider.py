"""
Live MLB data provider using the official MLB Stats API (statsapi.mlb.com).
Free, no API key required.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE = "https://statsapi.mlb.com/api"
TIMEOUT = 15.0


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


def _get_sync(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(f"{BASE}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def get_schedule(slate_date: date) -> list[dict[str, Any]]:
    """Return today's MLB games with probable pitchers and venue."""
    data = _get_sync(
        "/v1/schedule",
        {"sportId": 1, "date": slate_date.isoformat(), "hydrate": "probablePitcher,team,venue"},
    )
    games: list[dict[str, Any]] = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            status = g.get("status", {}).get("abstractGameState", "")
            if status in ("Final", "Postponed", "Cancelled"):
                continue
            away = g.get("teams", {}).get("away", {})
            home = g.get("teams", {}).get("home", {})
            games.append({
                "game_pk": g["gamePk"],
                "game_date": g.get("gameDate"),
                "status": status,
                "away_team": away.get("team", {}).get("name", ""),
                "away_id": away.get("team", {}).get("id"),
                "away_record": f"{away.get('leagueRecord', {}).get('wins', 0)}-{away.get('leagueRecord', {}).get('losses', 0)}",
                "away_pitcher": _pitcher_info(away.get("probablePitcher")),
                "home_team": home.get("team", {}).get("name", ""),
                "home_id": home.get("team", {}).get("id"),
                "home_record": f"{home.get('leagueRecord', {}).get('wins', 0)}-{home.get('leagueRecord', {}).get('losses', 0)}",
                "home_pitcher": _pitcher_info(home.get("probablePitcher")),
                "venue": g.get("venue", {}).get("name", ""),
                "game_status": _map_game_status(status),
            })
    return games


def _map_game_status(abstract: str) -> str:
    mapping = {
        "preview": "PRE_GAME",
        "pre-game": "PRE_GAME",
        "scheduled": "PRE_GAME",
        "live": "LIVE",
        "in progress": "LIVE",
        "final": "FINAL",
        "postponed": "POSTPONED",
        "cancelled": "CANCELLED",
        "canceled": "CANCELLED",
    }
    return mapping.get(abstract.strip().lower(), "UNKNOWN" if abstract else "PRE_GAME")


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

def get_player_game_log(player_id: int, season: int | None = None, last_n: int = 10) -> list[dict[str, Any]]:
    """Fetch a batter's recent game log."""
    season = season or date.today().year
    data = _get_sync(
        f"/v1/people/{player_id}/stats",
        {"stats": "gameLog", "group": "hitting", "season": season},
    )
    logs: list[dict[str, Any]] = []
    for split in _extract_splits(data):
        stat = split.get("stat", {})
        logs.append({
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
        })
    logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return logs[:last_n]


def get_pitcher_game_log(player_id: int, season: int | None = None, last_n: int = 10) -> list[dict[str, Any]]:
    """Fetch a pitcher's recent game log."""
    season = season or date.today().year
    data = _get_sync(
        f"/v1/people/{player_id}/stats",
        {"stats": "gameLog", "group": "pitching", "season": season},
    )
    logs: list[dict[str, Any]] = []
    for split in _extract_splits(data):
        stat = split.get("stat", {})
        logs.append({
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
        })
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

def get_player_season_stats(player_id: int, group: str = "hitting", season: int | None = None) -> dict[str, Any]:
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
        roster.append({
            "id": person.get("id"),
            "name": person.get("fullName", ""),
            "position": entry.get("position", {}).get("abbreviation", ""),
            "status": entry.get("status", {}).get("description", ""),
        })
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
            teams.append({
                "team": tr.get("team", {}).get("name", ""),
                "team_id": tr.get("team", {}).get("id"),
                "division": div,
                "wins": tr.get("wins", 0),
                "losses": tr.get("losses", 0),
                "pct": tr.get("winningPercentage", ""),
                "runs_scored": tr.get("runsScored", 0),
                "runs_allowed": tr.get("runsAllowed", 0),
                "streak": tr.get("streak", {}).get("streakCode", ""),
                "last_10": f"{tr.get('records', {}).get('splitRecords', [{}])[-1].get('wins', '?')}-{tr.get('records', {}).get('splitRecords', [{}])[-1].get('losses', '?')}",
            })
    return teams


# ---------------------------------------------------------------------------
# Live game feed
# ---------------------------------------------------------------------------

def get_live_feed(game_pk: int) -> dict[str, Any]:
    return _get_sync(f"/v1.1/game/{game_pk}/feed/live")


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
    ip_values = [float(log.get("innings_pitched", "0")) for log in logs[:5]]
    if not k_values:
        return {"avg_k": 0, "floor_k": 0, "avg_ip": 0, "values": []}
    return {
        "avg_k": round(sum(k_values) / len(k_values), 2),
        "floor_k": min(k_values),
        "avg_ip": round(sum(ip_values) / len(ip_values), 2),
        "values": k_values,
    }
