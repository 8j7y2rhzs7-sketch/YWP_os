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


def get_scoreboard(
    sport: str,
    slate_date: date,
    *,
    league_hint: str | None = None,
) -> list[dict[str, Any]]:
    paths: list[str] = []
    primary = resolve_espn_path(sport, league_hint=league_hint)
    if primary:
        paths.append(primary)
    sport_l = (sport or "").lower()
    # Soccer boards span many competitions — scan major paths when hint is thin.
    if sport_l in {"soccer", "mls", "epl"}:
        for path in (
            "soccer/usa.1",
            "soccer/eng.1",
            "soccer/esp.1",
            "soccer/ger.1",
            "soccer/ita.1",
            "soccer/fra.1",
            "soccer/uefa.champions",
            "soccer/uefa.europa",
            "soccer/mex.1",
        ):
            if path not in paths:
                paths.append(path)
    games: list[dict[str, Any]] = []
    stamp = slate_date.strftime("%Y%m%d")
    seen_ids: set[str] = set()
    for path in paths:
        try:
            data = _get(f"{SOURCE_API}/{path}/scoreboard", params={"dates": stamp}, cache_ttl=120)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ESPN scoreboard unavailable for %s %s: %s", path, slate_date, exc)
            continue
        for event in data.get("events") or []:
            parsed = _parse_event(event, sport=sport)
            if not parsed:
                continue
            eid = str(parsed.get("event_id") or "")
            if eid and eid in seen_ids:
                continue
            if eid:
                seen_ids.add(eid)
            parsed["espn_path"] = path
            games.append(parsed)
        # First matching path with games is enough for non-soccer.
        if games and sport_l not in {"soccer", "mls", "epl"}:
            break
    return games


def match_odds_event_to_espn(
    sport: str,
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
    league_hint: str | None = None,
) -> dict[str, Any] | None:
    """Best-effort match Odds API event names to an ESPN scoreboard game."""
    try:
        games = get_scoreboard(sport, slate_date, league_hint=league_hint)
        # Also try adjacent days for late/early slate timezone drift.
        if not games:
            for delta in (-1, 1):
                games.extend(
                    get_scoreboard(
                        sport,
                        slate_date + timedelta(days=delta),
                        league_hint=league_hint,
                    )
                )
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


def get_event_summary(
    sport: str,
    event_id: str | int,
    *,
    league_hint: str | None = None,
    espn_path: str | None = None,
) -> dict[str, Any] | None:
    """Fetch ESPN event summary (boxscore + header) for settlement."""
    path = espn_path or resolve_espn_path(sport, league_hint=league_hint)
    if not path or not event_id:
        return None
    try:
        return _get(
            f"{SOURCE_API}/{path}/summary",
            params={"event": str(event_id)},
            cache_ttl=90,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN summary unavailable for %s %s: %s", path, event_id, exc)
        return None


def parse_boxscore_player_stats(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Flatten ESPN summary boxscore players into name + numeric stats.

    Merges an athlete across passing/rushing/receiving (etc.) groups and keeps
    both raw labels (YDS) and group-prefixed keys (PASS_YDS, RUSH_YDS, REC_YDS)
    so football/hockey props settle without sport-by-sport special casing.
    """
    if not summary:
        return []
    box = summary.get("boxscore") or {}
    by_athlete: dict[str, dict[str, Any]] = {}
    for team_block in box.get("players") or []:
        team_name = str((team_block.get("team") or {}).get("displayName") or "")
        for group in team_block.get("statistics") or []:
            group_key = _boxscore_group_prefix(
                str(group.get("name") or group.get("type") or group.get("keys") or "")
            )
            names = [str(n).upper() for n in (group.get("names") or group.get("labels") or [])]
            for athlete_row in group.get("athletes") or []:
                athlete = athlete_row.get("athlete") or {}
                name = str(athlete.get("displayName") or athlete.get("fullName") or "").strip()
                athlete_id = str(athlete.get("id") or "")
                if not name:
                    continue
                key = athlete_id or f"{team_name}:{name.lower()}"
                mapped = by_athlete.get(key)
                if mapped is None:
                    mapped = {
                        "name": name,
                        "athlete_id": athlete_id,
                        "team": team_name,
                    }
                    by_athlete[key] = mapped
                raw_stats = athlete_row.get("stats") or []
                for index, label in enumerate(names):
                    if index >= len(raw_stats):
                        break
                    value = _parse_stat_cell(raw_stats[index])
                    mapped[label] = value
                    if group_key:
                        mapped[f"{group_key}_{label}"] = value
    rows = list(by_athlete.values())
    for mapped in rows:
        pts = mapped.get("PTS")
        reb = mapped.get("REB")
        ast = mapped.get("AST")
        if pts is not None and reb is not None and ast is not None:
            mapped["PRA"] = float(pts) + float(reb) + float(ast)
        goals = mapped.get("G")
        assists = mapped.get("A")
        if goals is not None and assists is not None:
            mapped["POINTS"] = float(goals) + float(assists)
            mapped["G+A"] = mapped["POINTS"]
    return rows


def _boxscore_group_prefix(raw: str) -> str:
    text = (raw or "").strip().lower()
    if not text:
        return ""
    if "pass" in text:
        return "PASS"
    if "rush" in text:
        return "RUSH"
    if "receiv" in text:
        return "REC"
    if "defen" in text:
        return "DEF"
    if "kick" in text:
        return "KICK"
    if "punt" in text:
        return "PUNT"
    if "goalie" in text or "goaltend" in text:
        return "GOALIE"
    if "forward" in text or "defense" in text or "skater" in text:
        return "SKATER"
    if "batting" in text or "batter" in text:
        return "BAT"
    if "pitch" in text:
        return "PITCH"
    return re.sub(r"[^a-z0-9]+", "", text).upper()[:12]


# Soccer league id / odds-key hints → ESPN path (beyond the default usa.1).
SOCCER_ESPN_PATHS: dict[str, str] = {
    "usa.1": "soccer/usa.1",
    "mls": "soccer/usa.1",
    "eng.1": "soccer/eng.1",
    "epl": "soccer/eng.1",
    "esp.1": "soccer/esp.1",
    "la liga": "soccer/esp.1",
    "fra.1": "soccer/fra.1",
    "ligue 1": "soccer/fra.1",
    "ita.1": "soccer/ita.1",
    "serie a": "soccer/ita.1",
    "ger.1": "soccer/ger.1",
    "bundesliga": "soccer/ger.1",
    "uefa.champions": "soccer/uefa.champions",
    "ucl": "soccer/uefa.champions",
    "uefa.europa": "soccer/uefa.europa",
    "mex.1": "soccer/mex.1",
}


def resolve_espn_path(sport: str, *, league_hint: str | None = None) -> str | None:
    """Resolve ESPN path for an app sport, including soccer league hints."""
    sport_l = (sport or "").lower().strip()
    hint = (league_hint or "").lower().strip()
    if sport_l in {"soccer", "mls", "epl"} or hint:
        for key, path in SOCCER_ESPN_PATHS.items():
            if key == hint or key in hint or (hint and hint in key):
                return path
        if sport_l == "mls":
            return "soccer/usa.1"
        if sport_l == "epl":
            return "soccer/eng.1"
    return espn_path_for(sport_l)


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
    """Build L5/L10 form from ESPN team schedules.

    Early NFL/NCAAF/NBA seasons often have <5 completed games on the current
    schedule. When that happens we backfill completed games from the prior
    season so Strict Mode is not stuck on `source:current_form` for weeks.
    """
    path = espn_path_for(sport)
    if not path:
        return _empty_form()

    current_games = _completed_games_from_schedule(
        path=path, team_id=team_id, slate_date=slate_date
    )
    games = list(current_games)
    used_prior = False
    # Prior-season backfill when the current slate is thin (Week 1–4 football,
    # early NBA/NHL, etc.).
    if len(games) < 5:
        prior_year = slate_date.year - 1
        try:
            prior = _completed_games_from_schedule(
                path=path,
                team_id=team_id,
                slate_date=slate_date,
                season=prior_year,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ESPN prior-season form backfill failed for %s team %s: %s",
                sport,
                team_id,
                exc,
            )
            prior = []
        seen = {item["date"] for item in games}
        for item in prior:
            if item["date"] in seen:
                continue
            games.append(item)
            seen.add(item["date"])
            used_prior = True

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

    # Prefer a full L5 when available; still verify with 3+ when a season is young
    # but prior-season fill could not reach five (all ESPN team sports, not just NFL).
    early_season_ok = sport.lower() in {
        "nfl",
        "ncaaf",
        "nba",
        "ncaab",
        "wnba",
        "nhl",
        "soccer",
        "mls",
        "epl",
    }
    verified = len(sample) >= 5 or (len(sample) >= 3 and early_season_ok)
    return {
        "verified": verified,
        "l5": summarize(l5),
        "l10": summarize(sample),
        "games": sample,
        "source_id": SOURCE_ID,
        "source_url": f"{SOURCE_API}/{path}/teams/{team_id}/schedule",
        "detail": (
            f"ESPN form from {len(sample)} completed games"
            + (" including prior-season backfill" if used_prior else "")
        ),
        "prior_season_backfill": used_prior,
        "current_season_games": len(current_games),
    }


def resolve_team_id(sport: str, team_name: str) -> str | None:
    """Map an Odds/ESPN display name onto an ESPN team id when schedule match missed."""
    path = espn_path_for(sport)
    if not path or not team_name.strip():
        return None
    try:
        data = _get(f"{SOURCE_API}/{path}/teams", cache_ttl=86_400)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN teams list unavailable for %s: %s", sport, exc)
        return None
    sports = data.get("sports") or []
    leagues = (sports[0].get("leagues") if sports else None) or []
    teams = (leagues[0].get("teams") if leagues else None) or data.get("teams") or []
    best_id: str | None = None
    best_score = 0
    for row in teams:
        team = row.get("team") if isinstance(row, dict) else None
        if not isinstance(team, dict):
            continue
        candidates = [
            str(team.get("displayName") or ""),
            str(team.get("name") or ""),
            str(team.get("shortDisplayName") or ""),
            str(team.get("nickname") or ""),
            str(team.get("abbreviation") or ""),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            score = _name_overlap(team_name, candidate)
            hay = _norm(candidate)
            needle = _norm(team_name)
            if hay and needle and (hay == needle or hay in needle or needle in hay):
                score += 10
            if score > best_score:
                best_score = score
                best_id = str(team.get("id") or "") or None
    return best_id if best_score >= 2 and best_id else None


def _completed_games_from_schedule(
    *,
    path: str,
    team_id: str | int,
    slate_date: date,
    season: int | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if season is not None:
        params["season"] = season
    try:
        data = _get(
            f"{SOURCE_API}/{path}/teams/{team_id}/schedule",
            params=params or None,
            cache_ttl=300,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ESPN schedule unavailable for team %s season=%s: %s",
            team_id,
            season,
            exc,
        )
        return []
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
    return games


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
    # ESPN (and similar boards) often omit healthy clubs with an empty report.
    # When the league feed itself succeeded, treat an unmatched club as matched
    # with zero injuries — do not block Strict Mode on a missing healthy side.
    feed_ok = bool(injury_feed.get("verified"))
    if feed_ok and home_team and not home_matched:
        home_matched = True
        home = []
    if feed_ok and away_team and not away_matched:
        away_matched = True
        away = []
    verified = feed_ok and (not home_team or home_matched) and (not away_team or away_matched)
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


def get_team_roster(sport: str, team_id: str | int) -> list[dict[str, Any]]:
    """Return active roster athletes for an ESPN team id."""
    path = espn_path_for(sport)
    if not path or not team_id:
        return []
    try:
        data = _get(f"{SOURCE_API}/{path}/teams/{team_id}/roster", cache_ttl=3_600)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN roster unavailable for %s team %s: %s", sport, team_id, exc)
        return []
    athletes: list[dict[str, Any]] = []
    for row in data.get("athletes") or []:
        group = row.get("items") if isinstance(row, dict) and "items" in row else [row]
        for person in group or []:
            athlete = person.get("athlete") if isinstance(person, dict) else None
            if not isinstance(athlete, dict):
                athlete = person if isinstance(person, dict) else {}
            athlete_id = athlete.get("id")
            name = athlete.get("displayName") or athlete.get("fullName") or ""
            if athlete_id and name:
                athletes.append(
                    {
                        "id": str(athlete_id),
                        "name": str(name),
                        "jersey": athlete.get("jersey"),
                        "position": ((athlete.get("position") or {}).get("abbreviation")),
                    }
                )
    return athletes


def resolve_athlete_id(
    sport: str,
    player_name: str,
    *,
    team_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    """Fuzzy-match a sportsbook player name onto an ESPN athlete via team rosters."""
    if not player_name.strip():
        return None
    ids = [str(tid) for tid in (team_ids or []) if tid]
    if not ids:
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    needle = _norm(player_name)
    for team_id in ids:
        for athlete in get_team_roster(sport, team_id):
            hay = _norm(str(athlete.get("name") or ""))
            if not hay:
                continue
            score = _name_overlap(player_name, str(athlete.get("name") or ""))
            if hay == needle:
                score += 20
            elif needle in hay or hay in needle:
                score += 12
            needle_last = (needle.split() or [""])[-1]
            hay_last = (hay.split() or [""])[-1]
            if needle_last and needle_last == hay_last and len(needle_last) > 2:
                score += 6
            if score > best_score:
                best_score = score
                best = dict(athlete)
    return best if best and best_score >= 6 else None


def get_athlete_gamelog(
    sport: str,
    athlete_id: str | int,
    *,
    season: int | None = None,
    last_n: int = 10,
) -> dict[str, Any]:
    """Parse ESPN common-v3 athlete gamelog into recent numeric stat rows."""
    path = espn_path_for(sport)
    if not path or not athlete_id:
        return {"verified": False, "names": [], "games": [], "source_id": SOURCE_ID}
    season = season or date.today().year
    url = (
        f"https://site.web.api.espn.com/apis/common/v3/sports/{path}/athletes/"
        f"{athlete_id}/gamelog"
    )
    try:
        data = _get(url, params={"season": season}, cache_ttl=900)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ESPN gamelog unavailable for %s %s: %s", sport, athlete_id, exc)
        return {
            "verified": False,
            "names": [],
            "games": [],
            "source_id": SOURCE_ID,
            "error": str(exc),
        }
    names = [str(n) for n in (data.get("names") or [])]
    labels = [str(n) for n in (data.get("labels") or [])]
    event_meta = data.get("events") if isinstance(data.get("events"), dict) else {}
    rows: list[dict[str, Any]] = []
    for season_type in data.get("seasonTypes") or []:
        for category in season_type.get("categories") or []:
            for event in category.get("events") or []:
                event_id = str(event.get("eventId") or "")
                stats = event.get("stats") or []
                if not event_id or not stats:
                    continue
                meta = event_meta.get(event_id) or {}
                mapped: dict[str, Any] = {
                    "event_id": event_id,
                    "game_date": str(meta.get("gameDate") or "")[:10],
                    "opponent": ((meta.get("opponent") or {}).get("displayName") or ""),
                    "result": meta.get("gameResult"),
                }
                for index, name in enumerate(names):
                    if index >= len(stats):
                        break
                    mapped[name] = _parse_stat_cell(stats[index])
                rows.append(mapped)
    rows.sort(key=lambda row: str(row.get("game_date") or ""), reverse=True)
    trimmed = rows[: max(1, last_n)]
    return {
        "verified": len(trimmed) >= 3,
        "names": names,
        "labels": labels,
        "games": trimmed,
        "source_id": SOURCE_ID,
        "source_url": url,
        "athlete_id": str(athlete_id),
    }


def _parse_stat_cell(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"-", "--"}:
        return None
    if "-" in text and text.replace("-", "").replace(".", "").isdigit():
        left = text.split("-", 1)[0]
        try:
            return float(left)
        except ValueError:
            return None
    try:
        return float(text.replace("%", ""))
    except ValueError:
        return None


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
