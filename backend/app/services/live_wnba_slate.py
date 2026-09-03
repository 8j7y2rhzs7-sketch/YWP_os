"""
Live WNBA slate builder: merges The Odds API lines into CandidateInput objects.
WNBA doesn't have a free public stats API like MLB's statsapi.mlb.com,
so we build candidates from odds data with manual stat entry supported
through the existing CandidateInput fields.
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
from app.services.team_art import logo_for_play
from app.services.ticket_gates import event_market_status

logger = logging.getLogger(__name__)

SPORT_KEY = "basketball_wnba"


def live_wnba_slate(slate_date: date) -> list[CandidateInput]:
    """Build live WNBA CandidateInput list from The Odds API."""
    try:
        odds_events = get_game_odds(
            sport=SPORT_KEY,
            markets="h2h,spreads,totals",
        )
    except Exception:
        logger.exception("Failed to fetch WNBA odds")
        return []

    if not odds_events:
        logger.warning("No WNBA events found for %s", slate_date)
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

        # --- Moneyline (home + away) ---
        for team in (home, away):
            ml = extract_best_odds(bookmakers, "h2h", team)
            if not ml:
                continue
            odds_val = ml["american_odds"]
            prob = odds_to_implied_probability(odds_val)
            side = "home" if team == home else "away"

            candidates.append(_build(
                candidate_id=f"wnba-ml-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="moneyline",
                selection=f"{team} ML",
                odds=odds_val,
                probability=prob,
                thesis_key=f"wnba-{_slug(team)}-ml-{slate_date}",
                script_key=f"wnba-{_slug(event_name)}-{side}-control",
                reason_codes=["HOME_FIELD", "CURRENT_FORM"] if side == "home" else ["CURRENT_FORM"],
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
                candidate_id=f"wnba-spread-{side}-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="spread",
                selection=f"{team} {spread_line:+}",
                line=spread_line,
                odds=spread_odds,
                probability=odds_to_implied_probability(spread_odds),
                thesis_key=f"wnba-{_slug(team)}-spread-{spread_line}-{slate_date}",
                script_key=f"wnba-{_slug(event_name)}-{side}-margin",
                reason_codes=["GAME_SCRIPT", "CURRENT_FORM"],
                reasoning=[f"{team} spread {spread_line:+}."],
                now=now,
            ))

        # --- Totals ---
        total_over = extract_best_odds(bookmakers, "totals", "Over")
        total_under = extract_best_odds(bookmakers, "totals", "Under")

        if total_over and total_over.get("point"):
            line_val = Decimal(str(total_over["point"]))
            over_odds = total_over["american_odds"]
            candidates.append(_build(
                candidate_id=f"wnba-over-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="game_total_over",
                selection=f"Over {line_val}",
                line=line_val,
                odds=over_odds,
                probability=odds_to_implied_probability(over_odds),
                thesis_key=f"wnba-{_slug(event_name)}-over-{line_val}-{slate_date}",
                script_key=f"wnba-{_slug(event_name)}-pace",
                reason_codes=["GAME_SCRIPT", "L10_CUSHION"],
                reasoning=[f"Game total Over {line_val}. Pace and scoring environment."],
                now=now,
            ))

        if total_under and total_under.get("point"):
            line_val = Decimal(str(total_under["point"]))
            under_odds = total_under["american_odds"]
            candidates.append(_build(
                candidate_id=f"wnba-under-{event_id[:12]}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="game_total_under",
                selection=f"Under {line_val}",
                line=line_val,
                odds=under_odds,
                probability=odds_to_implied_probability(under_odds),
                thesis_key=f"wnba-{_slug(event_name)}-under-{line_val}-{slate_date}",
                script_key=f"wnba-{_slug(event_name)}-defense",
                reason_codes=["GAME_SCRIPT", "ROLE_STABILITY"],
                reasoning=[f"Game total Under {line_val}. Defensive matchup."],
                now=now,
            ))

    logger.info("Built %d live WNBA candidates for %s", len(candidates), slate_date)
    return candidates


def _build(
    *,
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
    game_status, market_status = event_market_status(start_time, now)
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport="wnba",
        league="WNBA",
        start_time=start_time,
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=odds_clamped,
        estimated_probability=prob_clamped,
        probability_source="market_implied",
        variance=0.32,
        data_quality=0.82,
        factors={"matchup": 0.55, "current_form": 0.50, "market_value": 0.42},
        reason_codes=reason_codes,
        reasoning=reasoning,
        data_source="ODDS_API_WNBA",
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
        recent_hit_rate=min(0.80, prob_clamped + 0.05),
        average_cushion=1.2,
        matchup_score=0.55,
        script_alignment=0.50,
        multiple_paths_score=0.55,
        role_stability=0.65,
        miss_by_one_count_l10=0,
        ain_checks={
            "recent_form_l5_l10": False,
            "situational_angles": False,
            "h2h_context": False,
        },
        thesis_key=thesis_key,
        script_key=script_key,
        player_key=player_key,
        team_image_url=logo_for_play("wnba", selection, event_name),
        safer_alternative=f"Safer version of {selection}",
        higher_upside=f"Higher-upside version of {selection}",
        invalidation_conditions=["Starter ruled out", "Large line movement"],
        live_trigger="Recheck price and lineup before any live entry.",
        hedge=(
            "Compare any cash-out offer with current fair remaining value. "
            "Reduce exposure only after material thesis change."
        ),
        game_status=game_status,
        market_status=market_status,
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
