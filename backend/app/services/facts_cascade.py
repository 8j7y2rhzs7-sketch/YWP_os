"""Per-sport fact cascade: try official / secondary sources before giving up.

Odds API remains the market-price backbone. Fact providers only enrich schedule,
form, venue, and injuries. A failed fact source must never hide priced plays.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.services import espn_provider, nhl_provider

logger = logging.getLogger(__name__)


def match_schedule_game(
    sport: str,
    slate_date: date,
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    sport_l = sport.lower()
    errors: list[str] = []

    if sport_l == "nhl":
        try:
            game = nhl_provider.match_odds_event_to_nhl(
                slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"nhl_web_api:{exc}")
            logger.warning("NHL schedule cascade miss: %s", exc)

    try:
        game = espn_provider.match_odds_event_to_espn(
            sport_l, slate_date, home_team=home_team, away_team=away_team
        )
        if game:
            return game
    except Exception as exc:  # noqa: BLE001
        errors.append(f"espn_site_api:{exc}")
        logger.warning("ESPN schedule cascade miss for %s: %s", sport_l, exc)

    if errors:
        logger.info("No schedule match for %s %s @ %s (%s)", sport_l, away_team, home_team, "; ".join(errors))
    return None


def team_recent_form(
    sport: str,
    team_id: str | int | None,
    slate_date: date,
    *,
    team_abbrev: str | None = None,
) -> dict[str, Any]:
    sport_l = sport.lower()

    if sport_l == "nhl" and team_abbrev:
        try:
            form = nhl_provider.get_team_recent_form(team_abbrev, slate_date)
            if form.get("verified"):
                return form
        except Exception as exc:  # noqa: BLE001
            logger.warning("NHL form cascade miss: %s", exc)

    if team_id:
        try:
            form = espn_provider.get_team_recent_form(sport_l, team_id, slate_date)
            if form.get("verified"):
                return form
            return form
        except Exception as exc:  # noqa: BLE001
            logger.warning("ESPN form cascade miss for %s: %s", sport_l, exc)

    return {
        "verified": False,
        "l5": {"games": 0, "wins": 0, "losses": 0, "win_pct": 0.5, "avg_for": 0.0, "avg_against": 0.0, "totals": []},
        "l10": {"games": 0, "wins": 0, "losses": 0, "win_pct": 0.5, "avg_for": 0.0, "avg_against": 0.0, "totals": []},
        "games": [],
        "source_id": "none",
    }


def league_injuries(sport: str) -> dict[str, Any]:
    try:
        return espn_provider.get_league_injuries(sport)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Injury cascade miss for %s: %s", sport, exc)
        return {
            "verified": False,
            "by_team": {},
            "source_id": espn_provider.SOURCE_ID,
            "error": str(exc),
        }
