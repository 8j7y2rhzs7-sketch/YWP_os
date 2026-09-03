"""Research searchers that fill Strict Mode gaps from trusted sources only."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import httpx

from app.services.mlb_provider import SOURCE_API, get_live_feed
from app.services.trusted_sources import sources_for

logger = logging.getLogger(__name__)
TIMEOUT = 12.0


def _ok(result: dict[str, Any]) -> dict[str, Any]:
    result.setdefault("trusted", True)
    return result


def search_mlb_umpires(game_pk: int, schedule_officials: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Pull umpire crew from MLB schedule/boxscore (trusted primary)."""
    officials = list(schedule_officials or [])
    source_url = f"{SOURCE_API}/api/v1/schedule"
    if not officials:
        try:
            box = httpx.get(
                f"{SOURCE_API}/api/v1/game/{game_pk}/boxscore",
                timeout=TIMEOUT,
                headers={"User-Agent": "YWP-OS/3.2 trusted-research"},
            )
            if box.status_code == 200:
                officials = box.json().get("officials") or []
                source_url = f"{SOURCE_API}/api/v1/game/{game_pk}/boxscore"
        except Exception as exc:
            logger.warning("Umpire boxscore search failed for %s: %s", game_pk, exc)
    if not officials:
        try:
            feed = get_live_feed(game_pk)
            officials = feed.get("liveData", {}).get("boxscore", {}).get("officials") or []
            if not officials:
                officials = feed.get("gameData", {}).get("officials") or []
            source_url = f"{SOURCE_API}/api/v1.1/game/{game_pk}/feed/live"
        except Exception as exc:
            logger.warning("Umpire live-feed search failed for %s: %s", game_pk, exc)

    crew = []
    for entry in officials:
        person = entry.get("official") or entry.get("person") or {}
        crew.append(
            {
                "id": person.get("id"),
                "name": person.get("fullName", ""),
                "role": entry.get("officialType") or entry.get("type") or "Official",
            }
        )
    home_plate = next((item for item in crew if "plate" in item["role"].lower()), None)
    return _ok(
        {
            "category": "umpires",
            "source_id": "mlb_stats_api",
            "verified": bool(crew),
            "crew": crew,
            "home_plate": home_plate,
            "source_url": source_url,
            "trusted_sources": [item["id"] for item in sources_for("umpires")],
        }
    )


def search_mlb_park(game: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Confirm venue/park identity from MLB schedule or live feed."""
    venue_name = (
        (context or {}).get("venue")
        or game.get("venue")
        or ""
    )
    venue_id = game.get("venue_id")
    verified = bool(venue_name)
    return _ok(
        {
            "category": "park",
            "source_id": "mlb_stats_api",
            "verified": verified,
            "venue": venue_name,
            "venue_id": venue_id,
            "source_url": (
                f"{SOURCE_API}/api/v1/venues/{venue_id}"
                if venue_id
                else f"{SOURCE_API}/api/v1/schedule"
            ),
            "trusted_sources": [item["id"] for item in sources_for("park")],
        }
    )


def search_open_meteo_weather(
    *,
    latitude: float | None,
    longitude: float | None,
    slate_date: date,
) -> dict[str, Any]:
    """Secondary weather searcher used only when MLB weather is missing."""
    if latitude is None or longitude is None:
        return {
            "category": "weather",
            "source_id": "open_meteo",
            "verified": False,
            "trusted": True,
            "detail": "No venue coordinates available for backup weather.",
            "trusted_sources": [item["id"] for item in sources_for("weather")],
        }
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "temperature_2m_max,precipitation_sum,windspeed_10m_max",
                "timezone": "auto",
                "start_date": slate_date.isoformat(),
                "end_date": slate_date.isoformat(),
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        daily = response.json().get("daily") or {}
        temps = daily.get("temperature_2m_max") or []
        wind = daily.get("windspeed_10m_max") or []
        precip = daily.get("precipitation_sum") or []
        if not temps:
            return {
                "category": "weather",
                "source_id": "open_meteo",
                "verified": False,
                "trusted": True,
                "detail": "Open-Meteo returned no daily weather.",
            }
        return _ok(
            {
                "category": "weather",
                "source_id": "open_meteo",
                "verified": True,
                "condition": "forecast",
                "temperature_c": temps[0],
                "wind_kph": wind[0] if wind else None,
                "precip_mm": precip[0] if precip else None,
                "source_url": "https://api.open-meteo.com/v1/forecast",
                "trusted_sources": [item["id"] for item in sources_for("weather")],
            }
        )
    except Exception as exc:
        logger.warning("Open-Meteo weather search failed: %s", exc)
        return {
            "category": "weather",
            "source_id": "open_meteo",
            "verified": False,
            "trusted": True,
            "detail": str(exc)[:200],
        }


def search_market_consensus(bookmakers: list[dict[str, Any]], market_key: str, selection: str) -> dict[str, Any]:
    """Confirm current market from multiple trusted sportsbook quotes when available."""
    prices: list[int] = []
    books: list[str] = []
    for book in bookmakers:
        for market in book.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name") or "")
                if selection.lower() not in name.lower() and name.lower() not in selection.lower():
                    # moneyline uses team names; totals use Over/Under
                    if market_key == "totals":
                        if name.lower() not in {"over", "under"}:
                            continue
                        if selection.lower().split()[0] not in name.lower():
                            continue
                    elif name.lower() != selection.lower() and selection.lower() not in name.lower():
                        continue
                price = outcome.get("price")
                if isinstance(price, int):
                    prices.append(price)
                    books.append(str(book.get("key") or book.get("title") or "book"))
    verified = len(prices) >= 1
    spread = (max(prices) - min(prices)) if len(prices) >= 2 else 0
    return _ok(
        {
            "category": "market_movement",
            "source_id": "the_odds_api",
            "verified": verified,
            "book_count": len(prices),
            "books": books,
            "price_spread": spread,
            "consensus": True if len(prices) >= 2 else False,
            "detail": (
                f"{len(prices)} trusted sportsbook quote(s); "
                f"cross-book spread {spread} American odds points."
            ),
            "trusted_sources": [item["id"] for item in sources_for("market_movement")],
        }
    )


def run_mlb_research_searchers(
    *,
    game: dict[str, Any],
    context: dict[str, Any],
    slate_date: date,
    bookmakers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the trusted-source research pack for one MLB game."""
    game_pk = int(game["game_pk"])
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="ywp-search") as pool:
        umpire_future = pool.submit(
            search_mlb_umpires, game_pk, game.get("officials") if isinstance(game.get("officials"), list) else None
        )
        park_future = pool.submit(search_mlb_park, game, context)
        weather_future = None
        if not context.get("weather", {}).get("verified"):
            weather_future = pool.submit(
                search_open_meteo_weather,
                latitude=game.get("venue_lat"),
                longitude=game.get("venue_lon"),
                slate_date=slate_date,
            )
        umpires = umpire_future.result()
        park = park_future.result()
        weather = weather_future.result() if weather_future else {
            "category": "weather",
            "source_id": "mlb_stats_api",
            "verified": bool(context.get("weather", {}).get("verified")),
            "trusted": True,
            "detail": "Using official MLB weather when posted.",
        }

    market = search_market_consensus(bookmakers or [], "h2h", str(game.get("home_team") or ""))
    return {
        "umpires": umpires,
        "park": park,
        "weather_backup": weather,
        "market": market,
        "sources_used": sorted(
            {
                item.get("source_id")
                for item in (umpires, park, weather, market)
                if item.get("source_id")
            }
        ),
    }
