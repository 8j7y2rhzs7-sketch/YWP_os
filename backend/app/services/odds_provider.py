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
        if resp.status_code == 401:
            _set_status(ok=False, events=0, error="invalid_or_unauthorized_odds_api_key")
            resp.raise_for_status()
        if resp.status_code == 429:
            _set_status(ok=False, events=0, error="odds_api_quota_exceeded")
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Game odds (moneyline, spread, totals)
# ---------------------------------------------------------------------------


def get_game_odds(
    sport: str = SPORT_KEY,
    markets: str = "h2h,spreads,totals",
    regions: str = "us",
) -> list[dict[str, Any]]:
    """Fetch current odds for all upcoming games in the sport."""
    if not odds_api_configured():
        _set_status(
            ok=False, events=0, status_code=None, remaining=None, error="odds_api_key_missing"
        )
        logger.warning("ODDS_API_KEY missing; skipping Odds API fetch")
        return []

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

    _set_status(ok=True, events=len(data), error=None)
    return data


def probe_odds_api(sport: str = SPORT_KEY) -> dict[str, Any]:
    """Lightweight connectivity check used by /health/providers."""
    if not odds_api_configured():
        _set_status(
            ok=False, events=0, status_code=None, remaining=None, error="odds_api_key_missing"
        )
        return get_last_fetch_status()

    events = get_game_odds(sport=sport, markets="h2h", regions="us")
    status = get_last_fetch_status()
    status["sample_matchups"] = [
        f"{item.get('away_team')} @ {item.get('home_team')}" for item in events[:5]
    ]
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
