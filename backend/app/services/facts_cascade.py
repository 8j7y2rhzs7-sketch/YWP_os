"""Per-sport fact cascade: official / secondary sources first, ESPN last.

Odds API remains the market-price backbone. Fact providers only enrich schedule,
form, venue, and injuries. A failed fact source must never hide priced plays.

Priority (high → low):
  NHL     → NHL Web API → Odds scores → ESPN
  NCAAF   → CFBD → NCAA data → Odds scores → ESPN
  NBA     → BallDontLie (key) → Odds scores → ESPN
  WNBA    → Odds scores → ESPN
  Soccer  → Football-Data.org (key) → Odds scores → ESPN
  NFL/NCAAB → Odds scores → ESPN
  KBO     → Odds/KBO policy (no ESPN path)
  Injuries → soft ESPN board (missing healthy club ≠ fail) after sport policies
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.services import (
    balldontlie_provider,
    cfbd_provider,
    espn_provider,
    football_data_provider,
    kbo_provider,
    ncaa_provider,
    nhl_provider,
    odds_provider,
)

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

    if sport_l == "kbo":
        try:
            game = kbo_provider.match_odds_event_to_kbo(
                slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"the_odds_api_kbo:{exc}")
            logger.warning("KBO schedule cascade miss: %s", exc)
        if errors:
            logger.info(
                "No schedule match for %s %s @ %s (%s)",
                sport_l,
                away_team,
                home_team,
                "; ".join(errors),
            )
        return None

    if sport_l == "ncaaf":
        try:
            game = cfbd_provider.match_odds_event_to_cfbd(
                slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"college_football_data:{exc}")
            logger.warning("CFBD schedule cascade miss: %s", exc)
        try:
            game = ncaa_provider.match_odds_event_to_ncaa(
                slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ncaa_data_api:{exc}")
            logger.warning("NCAA schedule cascade miss: %s", exc)

    if sport_l == "nba":
        try:
            game = balldontlie_provider.match_odds_event_to_balldontlie(
                slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"balldontlie:{exc}")
            logger.warning("BallDontLie schedule cascade miss: %s", exc)

    if sport_l in {"soccer", "mls", "epl"}:
        try:
            game = football_data_provider.match_odds_event_to_football_data(
                sport_l, slate_date, home_team=home_team, away_team=away_team
            )
            if game:
                return game
        except Exception as exc:  # noqa: BLE001
            errors.append(f"football_data_org:{exc}")
            logger.warning("Football-Data schedule cascade miss: %s", exc)

    # ESPN is last-resort schedule only — often 403 on cloud egress / incomplete.
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
        logger.info(
            "No schedule match for %s %s @ %s (%s)",
            sport_l,
            away_team,
            home_team,
            "; ".join(errors),
        )
    return None


def team_recent_form(
    sport: str,
    team_id: str | int | None,
    slate_date: date,
    *,
    team_abbrev: str | None = None,
    team_name: str | None = None,
) -> dict[str, Any]:
    sport_l = sport.lower()
    best: dict[str, Any] | None = None

    def _keep(form: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal best
        if form.get("verified"):
            return form
        if not best or len(form.get("games") or []) > len(best.get("games") or []):
            best = form
        return None

    if sport_l == "nhl" and team_abbrev:
        try:
            hit = _keep(nhl_provider.get_team_recent_form(team_abbrev, slate_date))
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("NHL form cascade miss: %s", exc)

    if sport_l == "kbo" and team_name:
        try:
            form = kbo_provider.get_team_recent_form(team_name, slate_date)
            if form.get("verified"):
                return form
            return form
        except Exception as exc:  # noqa: BLE001
            logger.warning("KBO form cascade miss: %s", exc)

    if sport_l == "ncaaf" and team_name:
        try:
            hit = _keep(cfbd_provider.get_team_recent_form(team_name, slate_date))
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("CFBD form cascade miss: %s", exc)

    if sport_l == "nba" and team_name:
        try:
            hit = _keep(balldontlie_provider.get_team_recent_form(team_name, slate_date))
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("BallDontLie form cascade miss: %s", exc)

    if sport_l in {"soccer", "mls", "epl"} and team_name:
        try:
            hit = _keep(
                football_data_provider.get_team_recent_form(
                    sport_l, team_name, slate_date
                )
            )
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("Football-Data form cascade miss: %s", exc)

    # Odds completed scores before ESPN — more reliable on cloud hosts.
    if team_name and sport_l in {
        "nfl",
        "ncaaf",
        "nba",
        "ncaab",
        "wnba",
        "nhl",
        "soccer",
        "mls",
        "epl",
        "kbo",
    }:
        try:
            hit = _keep(
                odds_provider.get_team_recent_form_from_scores(
                    sport_l, team_name, slate_date
                )
            )
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("Odds scores form cascade miss for %s: %s", sport_l, exc)

    # ESPN last: resolve by id, then by display name.
    if team_id:
        try:
            hit = _keep(espn_provider.get_team_recent_form(sport_l, team_id, slate_date))
            if hit:
                return hit
        except Exception as exc:  # noqa: BLE001
            logger.warning("ESPN form cascade miss for %s: %s", sport_l, exc)

    if team_name and sport_l in {
        "nfl",
        "ncaaf",
        "nba",
        "ncaab",
        "wnba",
        "nhl",
        "soccer",
        "mls",
        "epl",
    }:
        resolved = espn_provider.resolve_team_id(sport_l, team_name)
        if resolved and str(resolved) != str(team_id or ""):
            try:
                hit = _keep(
                    espn_provider.get_team_recent_form(sport_l, resolved, slate_date)
                )
                if hit:
                    return hit
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ESPN name-resolved form cascade miss for %s %s: %s",
                    sport_l,
                    team_name,
                    exc,
                )

    if best is not None:
        return best

    return {
        "verified": False,
        "l5": {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "win_pct": 0.5,
            "avg_for": 0.0,
            "avg_against": 0.0,
            "totals": [],
        },
        "l10": {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "win_pct": 0.5,
            "avg_for": 0.0,
            "avg_against": 0.0,
            "totals": [],
        },
        "games": [],
        "source_id": "none",
    }


def league_injuries(sport: str) -> dict[str, Any]:
    """Injury board cascade. Missing healthy clubs on a live feed count as clear."""
    sport_l = sport.lower()
    if sport_l == "kbo":
        return kbo_provider.injuries_policy()
    if sport_l == "mlb":
        # MLB injuries come through MLB Stats path in live_mlb_slate — not ESPN.
        return {
            "verified": True,
            "by_team": {},
            "source_id": "mlb_stats_api",
            "policy": "mlb_primary_path",
        }
    try:
        feed = espn_provider.get_league_injuries(sport)
        # Soften: a successful league feed that omits a club with no injuries
        # still verifies — handled in injuries_for_teams.
        return feed
    except Exception as exc:  # noqa: BLE001
        logger.warning("Injury cascade miss for %s: %s", sport, exc)
        return {
            "verified": False,
            "by_team": {},
            "source_id": espn_provider.SOURCE_ID,
            "error": str(exc),
        }
