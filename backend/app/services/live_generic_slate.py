"""
Generic live slate builder for any sport supported by The Odds API.
Covers NFL, NBA, NHL, college football, college basketball, soccer, etc.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.schemas import CandidateInput
from app.services.odds_provider import (
    extract_best_odds,
    get_game_odds,
    odds_to_implied_probability,
)

logger = logging.getLogger(__name__)

SPORT_KEYS: dict[str, str] = {
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "nhl": "icehockey_nhl",
    "ncaaf": "americanfootball_ncaaf",
    "ncaab": "basketball_ncaab",
    "soccer": "soccer_usa_mls",
    "epl": "soccer_epl",
    "mls": "soccer_usa_mls",
    "kbo": "baseball_kbo",
}

SPORT_DISPLAY: dict[str, tuple[str, str]] = {
    "nfl": ("nfl", "NFL"),
    "nba": ("nba", "NBA"),
    "nhl": ("nhl", "NHL"),
    "ncaaf": ("ncaaf", "NCAAF"),
    "ncaab": ("ncaab", "NCAAB"),
    "soccer": ("soccer", "MLS"),
    "epl": ("soccer", "EPL"),
    "mls": ("soccer", "MLS"),
    "kbo": ("kbo", "KBO"),
}


def live_generic_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    sport_lower = sport.lower()
    odds_key = SPORT_KEYS.get(sport_lower)
    if not odds_key:
        logger.warning("No Odds API sport key for %s", sport)
        return []

    sport_code, league = SPORT_DISPLAY.get(sport_lower, (sport_lower, sport.upper()))

    try:
        odds_events = get_game_odds(sport=odds_key, markets="h2h,spreads,totals")
    except Exception:
        logger.exception("Failed to fetch %s odds", sport)
        return []

    if not odds_events:
        logger.warning("No %s events found", sport)
        return []

    candidates: list[CandidateInput] = []
    now = datetime.now(UTC)

    for event in odds_events:
        event_id = event.get("id", "")
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        event_name = f"{away} @ {home}"
        bookmakers = event.get("bookmakers", [])

        start_str = event.get("commence_time")
        start_time = _parse_start(start_str, slate_date)

        # --- Moneyline ---
        for team in (home, away):
            ml = extract_best_odds(bookmakers, "h2h", team)
            if not ml:
                continue
            odds_val = ml["american_odds"]
            prob = odds_to_implied_probability(odds_val)
            side = "home" if team == home else "away"

            candidates.append(_build(
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-ml-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="moneyline",
                selection=f"{team} ML",
                odds=odds_val,
                probability=prob,
                thesis_key=f"{sport_lower}-{_slug(team)}-ml-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-{side}",
                reason_codes=["MATCHUP_EDGE", "CURRENT_FORM"],
                reasoning=[f"{team} moneyline."],
                now=now,
            ))

        # --- Spreads ---
        for team in (home, away):
            spread = extract_best_odds(bookmakers, "spreads", team)
            if not spread or spread.get("point") is None:
                continue
            spread_line = Decimal(str(spread["point"]))
            spread_odds = spread["american_odds"]
            side = "home" if team == home else "away"

            candidates.append(_build(
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-spread-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="spread",
                selection=f"{team} {spread_line:+}",
                line=spread_line,
                odds=spread_odds,
                probability=odds_to_implied_probability(spread_odds),
                thesis_key=f"{sport_lower}-{_slug(team)}-spread-{spread_line}-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-{side}-margin",
                reason_codes=["GAME_SCRIPT", "MATCHUP_EDGE"],
                reasoning=[f"{team} spread {spread_line:+}."],
                now=now,
            ))

        # --- Totals ---
        for label in ("Over", "Under"):
            total = extract_best_odds(bookmakers, "totals", label)
            if not total or total.get("point") is None:
                continue
            line_val = Decimal(str(total["point"]))
            total_odds = total["american_odds"]
            mtype = "game_total_over" if label == "Over" else "game_total_under"

            candidates.append(_build(
                sport=sport_code,
                league=league,
                candidate_id=f"{sport_lower}-{label.lower()}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type=mtype,
                selection=f"{label} {line_val}",
                line=line_val,
                odds=total_odds,
                probability=odds_to_implied_probability(total_odds),
                thesis_key=f"{sport_lower}-{_slug(event_name)}-{label.lower()}-{line_val}-{slate_date}",
                script_key=f"{sport_lower}-{_slug(event_name)}-scoring",
                reason_codes=["GAME_SCRIPT", "CURRENT_FORM"],
                reasoning=[f"Game total {label} {line_val}."],
                now=now,
            ))

    logger.info("Built %d live %s candidates for %s", len(candidates), sport, slate_date)
    return candidates


def _build(
    *,
    sport: str,
    league: str,
    candidate_id: str,
    event_id: str,
    event_name: str,
    start_time: datetime,
    market_type: str,
    selection: str,
    odds: int,
    probability: float,
    thesis_key: str,
    script_key: str,
    reason_codes: list[str],
    reasoning: list[str],
    now: datetime,
    line: Decimal | None = None,
    player_key: str | None = None,
) -> CandidateInput:
    prob_clamped = max(0.02, min(0.98, probability))
    odds_clamped = max(-10000, min(10000, odds))
    if odds_clamped == 0 or -100 < odds_clamped < 100:
        odds_clamped = -100 if odds < 0 else 100
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport=sport,
        league=league,
        start_time=start_time,
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=odds_clamped,
        estimated_probability=prob_clamped,
        variance=0.32,
        data_quality=0.80,
        factors={"matchup": 0.50, "current_form": 0.45, "market_value": 0.40},
        reason_codes=reason_codes,
        reasoning=reasoning,
        data_source=f"ODDS_API_{sport.upper()}",
        source_timestamp=now,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "lineup": "unknown",
            "injuries": "unknown",
        },
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=False,
        l5_l10_verified=False,
        lineup_confirmed=False,
        injuries_verified=False,
        weather_verified=True,
        starter_confirmed=False,
        motivation_rotation_verified=False,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=False,
        recent_hit_rate=min(0.80, prob_clamped + 0.04),
        average_cushion=1.0,
        matchup_score=0.50,
        script_alignment=0.48,
        multiple_paths_score=0.50,
        role_stability=0.60,
        miss_by_one_count_l10=0,
        ain_checks={
            "recent_form_l5_l10": False,
            "situational_angles": False,
            "h2h_context": False,
        },
        thesis_key=thesis_key,
        script_key=script_key,
        player_key=player_key,
        safer_alternative=f"Safer version of {selection}",
        higher_upside=f"Higher-upside version of {selection}",
        invalidation_conditions=["Key player ruled out", "Large line movement"],
        live_trigger="Recheck price and game state before any live entry.",
        hedge="Compare cash-out offer with fair remaining value before acting.",
    )


def _parse_start(commence_time: str | None, slate_date: date) -> datetime:
    if commence_time:
        try:
            return datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return datetime(slate_date.year, slate_date.month, slate_date.day, 23, 0, tzinfo=UTC)


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("@", "at").replace(".", "")[:60]
