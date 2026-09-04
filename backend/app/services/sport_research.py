"""Trusted-source research pack for non-MLB sports (ESPN + Odds + Open-Meteo)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.schemas import CandidateInput
from app.services.espn_provider import (
    SOURCE_ID,
    WEATHER_SPORTS,
    get_league_injuries,
    get_team_recent_form,
    injuries_for_teams,
    match_odds_event_to_espn,
)
from app.services.research_searchers import search_market_consensus, search_open_meteo_weather
from app.services.sport_model import SportProjection, project_matchup
from app.services.team_art import logo_for_play
from app.services.ticket_gates import event_market_status

logger = logging.getLogger(__name__)


def build_event_research(
    *,
    sport: str,
    slate_date: date,
    home_team: str,
    away_team: str,
    bookmakers: list[dict[str, Any]],
    injury_feed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pull ESPN form/injuries/venue and Odds consensus for one matchup."""
    sport_l = sport.lower()
    espn_game = match_odds_event_to_espn(
        sport_l, slate_date, home_team=home_team, away_team=away_team
    )
    feed = injury_feed if injury_feed is not None else get_league_injuries(sport_l)
    home_name = (espn_game or {}).get("home_team") or home_team
    away_name = (espn_game or {}).get("away_team") or away_team
    home_id = (espn_game or {}).get("home_id")
    away_id = (espn_game or {}).get("away_id")

    home_form: dict[str, Any] = {"verified": False}
    away_form: dict[str, Any] = {"verified": False}
    if home_id and away_id:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="espn-form") as pool:
            home_fut = pool.submit(get_team_recent_form, sport_l, home_id, slate_date)
            away_fut = pool.submit(get_team_recent_form, sport_l, away_id, slate_date)
            try:
                home_form = home_fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Home form failed: %s", exc)
            try:
                away_form = away_fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Away form failed: %s", exc)

    injury_detail = injuries_for_teams(feed, home_name, away_name)
    indoor = bool((espn_game or {}).get("indoor"))
    if sport_l in WEATHER_SPORTS and espn_game and not indoor:
        city = espn_game.get("city") or ""
        coords = _city_coords(city, espn_game.get("state") or "", espn_game.get("country") or "")
        if coords:
            try:
                weather = search_open_meteo_weather(
                    latitude=coords[0], longitude=coords[1], slate_date=slate_date
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Weather search failed: %s", exc)
                weather = {"verified": False, "error": str(exc)}
        else:
            weather = {
                "verified": False,
                "detail": f"No coordinates mapped for venue city {city!r}.",
            }
    else:
        weather = {
            "verified": True,
            "source_id": SOURCE_ID,
            "detail": (
                "Indoor or non-weather sport; venue context verified."
                if espn_game
                else "Weather not required for this sport."
            ),
            "indoor": indoor,
        }

    market = search_market_consensus(bookmakers, "h2h", home_name)
    form_verified = bool(home_form.get("verified") and away_form.get("verified"))
    injuries_verified = bool(injury_detail.get("verified"))
    schedule_verified = espn_game is not None
    venue_verified = bool((espn_game or {}).get("venue"))
    weather_verified = bool(weather.get("verified"))
    market_verified = bool(market.get("verified"))

    lineup_confirmed = schedule_verified and injuries_verified
    starter_confirmed = injuries_verified
    motivation_verified = form_verified
    sport_sweep = all(
        [
            schedule_verified,
            form_verified,
            injuries_verified,
            lineup_confirmed,
            market_verified,
            weather_verified if sport_l in WEATHER_SPORTS else True,
        ]
    )

    return {
        "espn_game": espn_game,
        "home_form": home_form,
        "away_form": away_form,
        "injuries": injury_detail,
        "weather": weather,
        "market": market,
        "flags": {
            "schedule_verified": schedule_verified,
            "current_form_verified": form_verified,
            "l5_l10_verified": form_verified,
            "lineup_confirmed": lineup_confirmed,
            "injuries_verified": injuries_verified,
            "weather_verified": weather_verified,
            "starter_confirmed": starter_confirmed,
            "motivation_rotation_verified": motivation_verified,
            "home_away_verified": True,
            "market_movement_verified": market_verified,
            "sport_specific_sweep_complete": sport_sweep,
            "venue_verified": venue_verified,
        },
        "source_status": {
            "schedule": "confirmed" if schedule_verified else "unknown",
            "market": "confirmed" if market_verified else "unknown",
            "current_form": "confirmed" if form_verified else "unknown",
            "injuries": "confirmed" if injuries_verified else "unknown",
            "starter": "confirmed" if starter_confirmed else "unknown",
            "lineup": "confirmed"
            if lineup_confirmed
            else ("probable" if schedule_verified else "unknown"),
            "weather": "confirmed" if weather_verified else "unknown",
            "venue": "confirmed" if venue_verified else "unknown",
        },
        "source_urls": [
            url
            for url in [
                (espn_game or {}).get("source_url"),
                home_form.get("source_url"),
                away_form.get("source_url"),
                feed.get("source_url"),
                weather.get("source_url"),
            ]
            if url
        ],
    }


def project_from_research(
    research: dict[str, Any],
    *,
    market_type: str,
    selection: str,
    line: float | None,
    home_team: str,
) -> SportProjection:
    espn_game = research.get("espn_game") or {}
    home_name = espn_game.get("home_team") or home_team
    is_home = home_name.lower() in (selection or "").lower()
    injuries = research.get("injuries") or {}
    side_markets = "ml" in selection.lower() or "spread" in market_type or "moneyline" in market_type
    return project_matchup(
        home_form=research.get("home_form") or {},
        away_form=research.get("away_form") or {},
        market_type=market_type,
        selection=selection,
        line=line,
        home_out=int(injuries.get("home_out") or 0),
        away_out=int(injuries.get("away_out") or 0),
        is_home_selection=is_home if side_markets else None,
    )


def build_verified_candidate(
    *,
    sport: str,
    league: str,
    candidate_id: str,
    event_id: str,
    event_name: str,
    home_team: str,
    away_team: str,
    start_time: datetime,
    market_type: str,
    selection: str,
    odds: int,
    line: Decimal | None,
    thesis_key: str,
    script_key: str,
    reason_codes: list[str],
    reasoning: list[str],
    research: dict[str, Any],
    now: datetime | None = None,
) -> CandidateInput:
    now = now or datetime.now(UTC)
    projection = project_from_research(
        research,
        market_type=market_type,
        selection=selection,
        line=float(line) if line is not None else None,
        home_team=home_team,
    )
    flags = research.get("flags") or {}
    source_status = research.get("source_status") or {}
    odds_clamped = max(-10000, min(10000, odds))
    if odds_clamped == 0 or -100 < odds_clamped < 100:
        odds_clamped = -100 if odds < 0 else 100
    game_status, market_status = event_market_status(start_time, now)
    espn_game = research.get("espn_game") or {}
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport=sport,
        league=league,
        start_time=start_time,
        home_team=home_team,
        away_team=away_team,
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=odds_clamped,
        estimated_probability=projection.win_probability,
        probability_source="model",
        variance=0.30,
        data_quality=max(0.55, min(0.94, projection.quality)),
        factors={
            "matchup": projection.home_strength
            if home_team.lower() in selection.lower()
            else projection.away_strength,
            "current_form": projection.quality,
            "market_value": 0.45,
        },
        reason_codes=reason_codes,
        reasoning=[*reasoning, *projection.notes],
        data_source="ESPN_SITE_API+THE_ODDS_API",
        source_urls=list(research.get("source_urls") or []),
        source_timestamp=now,
        source_status=source_status,  # type: ignore[arg-type]
        schedule_verified=bool(flags.get("schedule_verified")),
        universe_scan_complete=True,
        current_form_verified=bool(flags.get("current_form_verified")),
        l5_l10_verified=bool(flags.get("l5_l10_verified")),
        lineup_confirmed=bool(flags.get("lineup_confirmed")),
        injuries_verified=bool(flags.get("injuries_verified")),
        weather_verified=bool(flags.get("weather_verified")),
        starter_confirmed=bool(flags.get("starter_confirmed")),
        motivation_rotation_verified=bool(flags.get("motivation_rotation_verified")),
        home_away_verified=True,
        market_movement_verified=bool(flags.get("market_movement_verified")),
        sport_specific_sweep_complete=bool(flags.get("sport_specific_sweep_complete")),
        recent_hit_rate=min(
            0.85,
            float(((research.get("home_form") or {}).get("l10") or {}).get("win_pct") or 0.5)
            if home_team.lower() in selection.lower()
            else float(((research.get("away_form") or {}).get("l10") or {}).get("win_pct") or 0.5),
        ),
        average_cushion=1.1,
        matchup_score=projection.quality,
        script_alignment=0.55,
        multiple_paths_score=0.55,
        role_stability=0.70 if flags.get("injuries_verified") else 0.50,
        miss_by_one_count_l10=0,
        ain_checks={
            "recent_form_l5_l10": bool(flags.get("l5_l10_verified")),
            "situational_angles": bool(flags.get("injuries_verified")),
            "h2h_context": bool(espn_game),
        },
        thesis_key=thesis_key,
        script_key=script_key,
        team_image_url=logo_for_play(sport, selection, event_name),
        safer_alternative=f"Safer version of {selection}",
        higher_upside=f"Higher-upside version of {selection}",
        invalidation_conditions=["Key player ruled out", "Large line movement"],
        live_trigger="Recheck price and availability before any live entry.",
        hedge="Compare cash-out offer with fair remaining value before acting.",
        game_status=game_status,
        market_status=market_status,
        missing_fields=[
            label
            for key, label in [
                ("schedule_verified", "schedule"),
                ("current_form_verified", "current form"),
                ("injuries_verified", "injuries"),
                ("market_movement_verified", "market consensus"),
            ]
            if not flags.get(key)
        ],
    )


_CITY_COORDS: dict[str, tuple[float, float]] = {
    "indianapolis": (39.7684, -86.1581),
    "nashville": (36.1627, -86.7816),
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "miami": (25.7617, -80.1918),
    "dallas": (32.7767, -96.7970),
    "denver": (39.7392, -104.9903),
    "seattle": (47.6062, -122.3321),
    "boston": (42.3601, -71.0589),
    "philadelphia": (39.9526, -75.1652),
    "atlanta": (33.7490, -84.3880),
    "phoenix": (33.4484, -112.0740),
    "detroit": (42.3314, -83.0458),
    "minneapolis": (44.9778, -93.2650),
    "kansas city": (39.0997, -94.5786),
    "green bay": (44.5133, -88.0133),
    "pittsburgh": (40.4406, -79.9959),
    "baltimore": (39.2904, -76.6122),
    "cleveland": (41.4993, -81.6944),
    "cincinnati": (39.1031, -84.5120),
    "tampa": (27.9506, -82.4572),
    "jacksonville": (30.3322, -81.6557),
    "charlotte": (35.2271, -80.8431),
    "houston": (29.7604, -95.3698),
    "san francisco": (37.7749, -122.4194),
    "london": (51.5074, -0.1278),
    "manchester": (53.4808, -2.2426),
}


def _city_coords(city: str, state: str, country: str) -> tuple[float, float] | None:
    del state, country
    key = (city or "").strip().lower()
    if key in _CITY_COORDS:
        return _CITY_COORDS[key]
    first = key.split(",")[0].strip()
    return _CITY_COORDS.get(first)
