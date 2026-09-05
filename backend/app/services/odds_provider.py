"""
Live odds provider using The Odds API (the-odds-api.com).
Requires a free API key (500 req/month on free tier).
Aggregates odds from Hard Rock, DraftKings, FanDuel, BetMGM, etc.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com"
TIMEOUT = 15.0
SPORT_KEY = "baseball_mlb"

PREFERRED_BOOKS = [
    "hardrockbet",
    "draftkings",
    "fanduel",
    "betmgm",
    "betrivers",
    "pointsbetus",
]

_last_fetch_status: dict[str, Any] = {
    "ok": False,
    "configured": False,
    "status_code": None,
    "events": 0,
    "remaining": None,
    "error": None,
}

# App sport key → Odds API sport key
APP_SPORT_TO_ODDS_KEY: dict[str, str] = {
    "mlb": "baseball_mlb",
    "wnba": "basketball_wnba",
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "ncaab": "basketball_ncaab",
    "nhl": "icehockey_nhl",
    "soccer": "soccer_usa_mls",
    "mls": "soccer_usa_mls",
    "epl": "soccer_epl",
    "kbo": "baseball_kbo",
}

# Free /v4/sports cache — endpoint does not consume usage credits.
_SPORTS_CACHE_TTL_SECONDS = 6 * 60 * 60
_sports_cache: dict[str, Any] = {
    "fetched_at": 0.0,
    "in_season": [],
    "all": [],
    "error": None,
}

# Short TTL for paid /odds responses so empty-date follow-ups, category
# switching, and double refreshes reuse the same payload without a second bill.
_ODDS_CACHE_TTL_SECONDS = 5 * 60
_odds_response_cache: dict[str, dict[str, Any]] = {}


def get_last_fetch_status() -> dict[str, Any]:
    """Return the most recent Odds API fetch outcome (no secrets)."""
    return dict(_last_fetch_status)


def odds_api_configured() -> bool:
    return bool(_normalized_key())


def key_diagnostics(raw: str | None = None) -> dict[str, Any]:
    """Public, secret-safe description of the configured Odds API key."""
    key = raw if raw is not None else _normalized_key()
    if not key:
        return {
            "configured": False,
            "length": 0,
            "fingerprint": None,
            "looks_like_hex": False,
            "has_non_hex": False,
        }
    looks_like_hex = bool(re.fullmatch(r"[0-9a-fA-F]+", key))
    fingerprint = f"{key[:4]}…{key[-4:]}" if len(key) >= 8 else "too_short"
    return {
        "configured": True,
        "length": len(key),
        "fingerprint": fingerprint,
        "looks_like_hex": looks_like_hex,
        "has_non_hex": not looks_like_hex,
    }


def _normalized_key() -> str | None:
    key = settings.odds_api_key
    if key is None:
        return None
    cleaned = key.strip().strip('"').strip("'")
    cleaned = re.sub(r"[\s\u200b\u200c\u200d\ufeff]", "", cleaned)
    if cleaned in {"", "-", "null", "None"}:
        return None
    if re.fullmatch(r"[0-9a-fA-F]+", cleaned):
        return cleaned
    # Odds API keys are hex. Common copy/paste mixups: l/I → 1, O → 0.
    repaired = cleaned.translate(str.maketrans({"l": "1", "L": "1", "I": "1", "O": "0"}))
    if re.fullmatch(r"[0-9a-fA-F]+", repaired) and len(repaired) >= 16:
        logger.warning(
            "ODDS_API_KEY contained non-hex lookalike characters; using hex-normalized value"
        )
        return repaired
    return cleaned


def _api_key() -> str:
    key = _normalized_key()
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Sign up free at https://the-odds-api.com "
            "and set the ODDS_API_KEY env var on the server."
        )
    return key


def _safe_error_message(exc: BaseException) -> str:
    text = str(exc)
    # Never echo apiKey query values back to clients/logs consumers.
    text = re.sub(r"(apiKey=)[^&\s]+", r"\1***", text, flags=re.IGNORECASE)
    return text[:180]


def _set_status(**kwargs: Any) -> None:
    _last_fetch_status.update(kwargs)
    _last_fetch_status["configured"] = odds_api_configured()
    _last_fetch_status.update(key_diagnostics())


def _get_sync(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    with httpx.Client(timeout=TIMEOUT) as client:
        all_params = {"apiKey": _api_key(), **(params or {})}
        resp = client.get(f"{BASE}{path}", params=all_params)
        remaining = resp.headers.get("x-requests-remaining")
        _set_status(
            status_code=resp.status_code,
            remaining=remaining,
        )
        if remaining is not None:
            logger.info("Odds API requests remaining: %s", remaining)
        if resp.status_code in {401, 429}:
            body_text = ""
            try:
                body_text = resp.text.lower()
            except Exception:  # noqa: BLE001
                body_text = ""
            if (
                "out_of_usage" in body_text
                or "usage quota" in body_text
                or "out_of_usage_credits" in body_text
                or resp.status_code == 429
            ):
                _set_status(ok=False, events=0, error="odds_api_quota_exceeded")
            else:
                _set_status(ok=False, events=0, error="invalid_or_unauthorized_odds_api_key")
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()


def list_odds_sports(
    *,
    include_out_of_season: bool = False,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return Odds API sport objects via GET /v4/sports.

    This endpoint does **not** count against the usage quota. One `all=true`
    call yields both catalogs (filter on `active`). Results are cached for
    several hours so we can gate paid odds calls without burning credits.
    """
    import time

    now = time.time()
    cache_age = now - float(_sports_cache.get("fetched_at") or 0.0)
    if (
        not force_refresh
        and float(_sports_cache.get("fetched_at") or 0.0) > 0
        and cache_age < _SPORTS_CACHE_TTL_SECONDS
        and _sports_cache.get("error") is None
    ):
        cached = _sports_cache["all"] if include_out_of_season else _sports_cache["in_season"]
        return list(cached or [])

    if not odds_api_configured():
        _sports_cache.update(
            {"fetched_at": now, "in_season": [], "all": [], "error": "odds_api_key_missing"}
        )
        return []

    try:
        # Single free call: all=true + active flag covers in/out of season.
        all_raw = _get_sync("/v4/sports/", params={"all": "true"})
    except Exception as exc:
        logger.exception("Free Odds /sports catalog fetch failed")
        _sports_cache.update(
            {
                "fetched_at": now,
                "in_season": list(_sports_cache.get("in_season") or []),
                "all": list(_sports_cache.get("all") or []),
                "error": _safe_error_message(exc),
            }
        )
        cached = _sports_cache["all"] if include_out_of_season else _sports_cache["in_season"]
        return list(cached or [])

    all_sports = [item for item in all_raw if isinstance(item, dict)] if isinstance(all_raw, list) else []
    in_season = [item for item in all_sports if item.get("active") is True]
    # If the API omits `active` on a row, treat default (no all=true semantics) as in-season.
    if not in_season and all_sports and all(item.get("active") is None for item in all_sports):
        in_season = list(all_sports)
    _sports_cache.update(
        {
            "fetched_at": now,
            "in_season": in_season,
            "all": all_sports,
            "error": None,
        }
    )
    _set_status(
        ok=True,
        events=len(in_season),
        error=None,
        catalog_in_season=len(in_season),
        catalog_total=len(all_sports),
        credit_cost=0,
    )
    return list(all_sports if include_out_of_season else in_season)


def in_season_odds_keys(*, force_refresh: bool = False) -> set[str]:
    """Odds API keys currently marked in-season (free catalog)."""
    rows = list_odds_sports(include_out_of_season=False, force_refresh=force_refresh)
    return {
        str(item.get("key") or "").strip()
        for item in rows
        if str(item.get("key") or "").strip()
    }


def odds_key_for_app_sport(app_sport: str) -> str | None:
    return APP_SPORT_TO_ODDS_KEY.get((app_sport or "").strip().lower())


def app_sport_in_season(app_sport: str, *, force_refresh: bool = False) -> bool | None:
    """True/False when mapped; None when the app sport has no Odds key mapping."""
    odds_key = odds_key_for_app_sport(app_sport)
    if not odds_key:
        return None
    if not odds_api_configured():
        return None
    return odds_key in in_season_odds_keys(force_refresh=force_refresh)


def build_app_sports_catalog(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """App-facing sport catalog enriched with free Odds in-season flags."""
    in_season = in_season_odds_keys(force_refresh=force_refresh)
    catalog_error = _sports_cache.get("error")
    rows: list[dict[str, Any]] = []
    labels = {
        "mlb": "MLB",
        "wnba": "WNBA",
        "nba": "NBA",
        "nfl": "NFL",
        "ncaaf": "NCAAF",
        "ncaab": "NCAAB",
        "nhl": "NHL",
        "soccer": "SOCCER",
        "kbo": "KBO",
    }
    for app_key, label in labels.items():
        odds_key = odds_key_for_app_sport(app_key)
        active = bool(odds_key and odds_key in in_season) if odds_api_configured() else None
        rows.append(
            {
                "key": app_key,
                "label": label,
                "odds_key": odds_key,
                "in_season": active,
                "priced_slate_available": active is True,
                "note": (
                    "In season — priced slate uses credits"
                    if active is True
                    else (
                        "Out of season — refresh skipped to save Odds credits"
                        if active is False
                        else (
                            "Odds catalog unavailable"
                            if catalog_error
                            else "Odds key not configured"
                        )
                    )
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Game odds (moneyline, spread, totals) — PAID: markets × regions credits
# ---------------------------------------------------------------------------


def get_game_odds(
    sport: str = SPORT_KEY,
    markets: str = "h2h,spreads,totals",
    regions: str = "us",
    *,
    allow_out_of_season: bool = False,
) -> list[dict[str, Any]]:
    """Fetch current odds for all upcoming games in the sport.

    Paid call. Skips automatically when the free /sports catalog says this
    Odds sport key is out of season, unless allow_out_of_season=True.
    Successful responses are cached briefly so nearby-date helpers and sport
    switching reuse the same credit spend.
    """
    import time

    if not odds_api_configured():
        _set_status(
            ok=False, events=0, status_code=None, remaining=None, error="odds_api_key_missing"
        )
        logger.warning("ODDS_API_KEY missing; skipping Odds API fetch")
        return []

    if not allow_out_of_season:
        try:
            active_keys = in_season_odds_keys()
            # If catalog failed empty due to auth/quota, don't mask that as OOS.
            if active_keys and sport not in active_keys:
                _set_status(
                    ok=True,
                    events=0,
                    error="sport_out_of_season",
                    skipped_paid_call=True,
                    sport=sport,
                    credit_cost=0,
                )
                logger.info(
                    "Skipping paid Odds fetch for out-of-season sport %s (free catalog gate)",
                    sport,
                )
                return []
        except Exception:  # noqa: BLE001 — never block paid path on catalog issues
            logger.exception("In-season catalog gate failed for %s; continuing paid fetch", sport)

    cache_key = f"{sport}|{markets}|{regions}"
    now = time.time()
    cached = _odds_response_cache.get(cache_key)
    if cached and now - float(cached.get("fetched_at") or 0.0) < _ODDS_CACHE_TTL_SECONDS:
        data = cached.get("data") or []
        _set_status(
            ok=True,
            events=len(data),
            error=None,
            skipped_paid_call=False,
            cache_hit=True,
            credit_cost=0,
            sport=sport,
        )
        return list(data)

    try:
        data = _get_sync(
            f"/v4/sports/{sport}/odds",
            {
                "regions": regions,
                "markets": markets,
                "oddsFormat": "american",
            },
        )
    except Exception as exc:
        # Prefer the structured status already set by _get_sync for 401/429.
        if not _last_fetch_status.get("error"):
            _set_status(ok=False, events=0, error=_safe_error_message(exc))
        else:
            _set_status(ok=False, events=0)
        logger.exception("Odds API fetch failed")
        return []

    if not isinstance(data, list):
        _set_status(ok=False, events=0, error="unexpected_odds_payload")
        return []

    market_count = len([part for part in markets.split(",") if part.strip()])
    region_count = len([part for part in regions.split(",") if part.strip()])
    credit_cost = market_count * max(1, region_count)
    _odds_response_cache[cache_key] = {"fetched_at": now, "data": data}
    _set_status(
        ok=True,
        events=len(data),
        error=None,
        skipped_paid_call=False,
        cache_hit=False,
        credit_cost=credit_cost,
        sport=sport,
    )
    return data


def prefetch_in_season_app_odds(
    *,
    markets: str = "h2h,spreads,totals",
    regions: str = "us",
) -> dict[str, Any]:
    """Optionally warm paid odds for every in-season app sport (uses credits).

    Cost ≈ 3 credits × number of in-season mapped sports that are not already
    cached. Prefer this only when the user will browse multiple sports; a single
    sport refresh remains cheaper.
    """
    catalog = build_app_sports_catalog()
    warmed: list[str] = []
    skipped: list[str] = []
    credits_spent = 0
    for row in catalog:
        if row.get("in_season") is not True:
            skipped.append(str(row.get("key")))
            continue
        odds_key = row.get("odds_key")
        if not odds_key:
            skipped.append(str(row.get("key")))
            continue
        before = get_last_fetch_status()
        get_game_odds(sport=str(odds_key), markets=markets, regions=regions)
        after = get_last_fetch_status()
        spent = int(after.get("credit_cost") or 0)
        credits_spent += spent
        if after.get("cache_hit"):
            warmed.append(f"{row['key']}:cache")
        else:
            warmed.append(f"{row['key']}:{spent}c")
        # Preserve last status for health; keep loop quiet.
        _ = before
    return {
        "warmed": warmed,
        "skipped_out_of_season_or_unmapped": [s for s in skipped if s],
        "credits_spent": credits_spent,
        "cache_ttl_seconds": _ODDS_CACHE_TTL_SECONDS,
        "note": (
            "Prefetch spends credits once per sport then category switches are free "
            f"for ~{_ODDS_CACHE_TTL_SECONDS // 60} minutes. Skip prefetch if you only use one sport."
        ),
    }


def probe_odds_api(sport: str = SPORT_KEY) -> dict[str, Any]:
    """Connectivity check using the FREE /v4/sports catalog (0 credits)."""
    if not odds_api_configured():
        _set_status(
            ok=False, events=0, status_code=None, remaining=None, error="odds_api_key_missing"
        )
        return get_last_fetch_status()

    sports = list_odds_sports(include_out_of_season=False, force_refresh=True)
    status = get_last_fetch_status()
    status["probe_mode"] = "free_sports_catalog"
    status["credit_cost"] = 0
    status["in_season_count"] = len(sports)
    status["sample_sports"] = [
        f"{item.get('title') or item.get('key')} ({item.get('key')})" for item in sports[:8]
    ]
    status["target_sport_in_season"] = any(item.get("key") == sport for item in sports)
    # Keep backward-compatible sample_matchups empty; this probe does not fetch odds.
    status["sample_matchups"] = []
    if _sports_cache.get("error"):
        status["ok"] = False
        status["error"] = _sports_cache.get("error")
    else:
        status["ok"] = True
        status["error"] = None
    return status


def get_event_odds(
    event_id: str,
    sport: str = SPORT_KEY,
    markets: str = "h2h,spreads,totals",
    regions: str = "us",
) -> dict[str, Any] | None:
    """Fetch odds for a single event by event_id."""
    if not odds_api_configured():
        return None
    try:
        data = _get_sync(
            f"/v4/sports/{sport}/events/{event_id}/odds",
            {
                "regions": regions,
                "markets": markets,
                "oddsFormat": "american",
            },
        )
    except Exception:
        logger.exception("Odds API event fetch failed for %s", event_id)
        return None
    if isinstance(data, dict):
        return data
    return None


# ---------------------------------------------------------------------------
# Player props
# ---------------------------------------------------------------------------


def get_player_props(
    event_id: str,
    sport: str = SPORT_KEY,
    markets: str = "batter_hits,batter_total_bases,batter_rbis,batter_home_runs,pitcher_strikeouts",
    regions: str = "us",
) -> dict[str, Any] | None:
    """Fetch player prop odds for a single event."""
    if not odds_api_configured():
        return None
    try:
        data = _get_sync(
            f"/v4/sports/{sport}/events/{event_id}/odds",
            {
                "regions": regions,
                "markets": markets,
                "oddsFormat": "american",
            },
        )
        if isinstance(data, dict):
            return data
        return None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 422:
            logger.warning("Props not available for event %s", event_id)
            return None
        raise


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def extract_best_odds(
    bookmakers: list[dict[str, Any]],
    market_key: str,
    selection_name: str | None = None,
    preferred_books: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    From a list of bookmakers, find the best odds for a given market/selection.
    Prioritizes preferred books (Hard Rock first), falls back to best available.
    """
    preferred = preferred_books or PREFERRED_BOOKS
    candidates: list[dict[str, Any]] = []

    for book in bookmakers:
        book_key = book.get("key", "")
        for market in book.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                outcome_name = str(outcome.get("name", ""))
                match_rank = 0
                if selection_name and outcome_name.casefold() != selection_name.casefold():
                    # Exact team names always win. Containment is the next safest
                    # fallback, followed by a nickname-only match for feeds that
                    # omit the city. This prevents White Sox/Red Sox cross-matches.
                    sel = selection_name.casefold()
                    out = outcome_name.casefold()
                    if sel in out or out in sel:
                        match_rank = 1
                    elif sel.split() and out.split() and sel.split()[-1] == out.split()[-1]:
                        match_rank = 2
                    else:
                        continue
                price = outcome.get("price")
                if not isinstance(price, int) or isinstance(price, bool):
                    continue
                candidates.append(
                    {
                        "book": book_key,
                        "name": outcome_name,
                        "price": price,
                        "point": outcome.get("point"),
                        "match_rank": match_rank,
                        "preferred_rank": preferred.index(book_key)
                        if book_key in preferred
                        else 999,
                    }
                )

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c["match_rank"], c["preferred_rank"], -c["price"]))
    best = candidates[0]
    return {
        "book": best["book"],
        "name": best["name"],
        "american_odds": best["price"],
        "point": best["point"],
    }


def extract_player_prop(
    bookmakers: list[dict[str, Any]],
    market_key: str,
    player_name: str,
    outcome_name: str = "Over",
    preferred_books: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return a real player-prop line; never manufacture a line or price.

    The Odds API identifies the player in the outcome description for standard player markets.
    Some books place it in the outcome name, so both representations are supported.
    """
    preferred = preferred_books or PREFERRED_BOOKS
    wanted_player = player_name.casefold().strip()
    wanted_outcome = outcome_name.casefold().strip()
    candidates: list[dict[str, Any]] = []
    for book in bookmakers:
        book_key = str(book.get("key", ""))
        for market in book.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name", "")).casefold().strip()
                description = str(outcome.get("description", "")).casefold().strip()
                player_matches = wanted_player in description or wanted_player in name
                outcome_matches = name == wanted_outcome or name.endswith(f" {wanted_outcome}")
                if not player_matches or not outcome_matches:
                    continue
                point = outcome.get("point")
                price = outcome.get("price")
                if point is None or not isinstance(price, int):
                    continue
                candidates.append(
                    {
                        "book": book_key,
                        "american_odds": price,
                        "point": point,
                        "preferred_rank": preferred.index(book_key)
                        if book_key in preferred
                        else 999,
                    }
                )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item["preferred_rank"], -item["american_odds"]))
    result = candidates[0]
    return {
        "book": result["book"],
        "american_odds": result["american_odds"],
        "point": result["point"],
    }


def match_game_to_event(
    game: dict[str, Any],
    odds_events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match an MLB Stats API game to an Odds API event by team names."""
    home = game.get("home_team", "").lower()
    away = game.get("away_team", "").lower()
    if not home or not away:
        return None

    # Use exact full team names first. This is essential when both opponents
    # share the same last token, such as White Sox and Red Sox.
    for event in odds_events:
        event_home = str(event.get("home_team", "")).lower().strip()
        event_away = str(event.get("away_team", "")).lower().strip()
        if home.strip() == event_home and away.strip() == event_away:
            return event

    for event in odds_events:
        event_home = str(event.get("home_team", "")).lower()
        event_away = str(event.get("away_team", "")).lower()
        if _fuzzy_team_match(home, event_home) and _fuzzy_team_match(away, event_away):
            return event
    return None


def _fuzzy_team_match(mlb_name: str, odds_name: str) -> bool:
    """Simple fuzzy match: check if the last word of each name matches."""
    mlb_parts = mlb_name.strip().split()
    odds_parts = odds_name.strip().split()
    if not mlb_parts or not odds_parts:
        return False
    if mlb_parts[-1] == odds_parts[-1]:
        return True
    # Handle nicknames that differ only by city prefix.
    return mlb_name in odds_name or odds_name in mlb_name


def odds_to_implied_probability(american_odds: int) -> float:
    """Convert American odds to implied probability (no-vig)."""
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    return 100 / (american_odds + 100)
