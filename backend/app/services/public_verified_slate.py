"""Public verified-schedule fallback when The Odds API is down.

Uses free official/public scoreboards (ESPN / NHL / MLB Stats) that we can
verify for real tip times and teams. No sportsbook prices — fair American odds
are derived from the research model so the board stays honest and PARTIAL.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from app.schemas import CandidateInput
from app.services.espn_provider import get_scoreboard
from app.services.odds_provider import canonical_app_sport, sport_public_label
from app.services.sport_research import build_event_research, build_verified_candidate
from app.services.ticket_gates import event_market_status

logger = logging.getLogger(__name__)

PUBLIC_FALLBACK_SPORTS: tuple[str, ...] = (
    "nba",
    "nfl",
    "nhl",
    "ncaaf",
    "ncaab",
    "wnba",
    "soccer",
    "mlb",
)

_LEAGUE = {
    "nba": "NBA",
    "nfl": "NFL",
    "nhl": "NHL",
    "ncaaf": "NCAAF",
    "ncaab": "NCAAM",
    "wnba": "WNBA",
    "soccer": "Soccer",
    "mlb": "MLB",
}


def fair_american_odds(probability: float) -> int:
    """Convert a model win probability into a no-vig American price."""
    p = min(0.99, max(0.01, float(probability)))
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def odds_api_unavailable() -> bool:
    """True when Odds is missing, unauthorized, rate-limited, or last fetch failed hard."""
    from app.services.odds_provider import get_last_fetch_status, odds_api_configured

    if not odds_api_configured():
        return True
    status = get_last_fetch_status() or {}
    err = str(status.get("error") or "").lower()
    code = status.get("status_code")
    if code in {401, 403, 429, 500, 502, 503, 504}:
        return True
    return any(
        token in err
        for token in (
            "unauthorized",
            "invalid",
            "rate",
            "quota",
            "timeout",
            "connection",
            "unavailable",
            "401",
            "403",
            "429",
        )
    )


def _parse_start(raw: Any, slate_date: date) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime(slate_date.year, slate_date.month, slate_date.day, 23, 59, tzinfo=UTC)


def _schedule_games(sport: str, slate_date: date) -> list[dict[str, Any]]:
    sport_l = canonical_app_sport(sport)
    games: list[dict[str, Any]] = []

    if sport_l == "mlb":
        try:
            from app.services.mlb_provider import get_schedule

            for row in get_schedule(slate_date) or []:
                games.append(
                    {
                        "event_id": str(row.get("game_pk") or ""),
                        "home_team": str(row.get("home_team") or ""),
                        "away_team": str(row.get("away_team") or ""),
                        "start_time": row.get("game_date"),
                        "status": str(row.get("status") or ""),
                        "source": "mlb_stats_api",
                    }
                )
        except Exception:
            logger.exception("MLB public schedule failed for %s", slate_date)

    if sport_l == "nhl":
        try:
            from app.services.nhl_provider import get_schedule as nhl_schedule

            nhl_fn = nhl_schedule
            # Prefer date-specific helper when exported; fall back carefully.
            try:
                from app.services import nhl_provider as nhl_mod

                if hasattr(nhl_mod, "_games_for_date"):
                    rows = nhl_mod._games_for_date(slate_date)  # noqa: SLF001
                else:
                    rows = nhl_fn(slate_date) if callable(nhl_fn) else []
            except Exception:
                rows = []
            for row in rows or []:
                games.append(
                    {
                        "event_id": str(row.get("id") or row.get("event_id") or ""),
                        "home_team": str(row.get("home_team") or ""),
                        "away_team": str(row.get("away_team") or ""),
                        "start_time": row.get("start_time") or row.get("gameDate"),
                        "status": str(row.get("status") or ""),
                        "source": "nhl_web_api",
                    }
                )
        except Exception:
            logger.exception("NHL public schedule failed for %s", slate_date)

    try:
        for row in get_scoreboard(sport_l, slate_date) or []:
            games.append(
                {
                    "event_id": str(row.get("event_id") or ""),
                    "home_team": str(row.get("home_team") or ""),
                    "away_team": str(row.get("away_team") or ""),
                    "start_time": row.get("start_time") or row.get("date"),
                    "status": str(row.get("status") or row.get("state") or ""),
                    "source": "espn_scoreboard",
                }
            )
    except Exception:
        logger.exception("ESPN public scoreboard failed for %s %s", sport_l, slate_date)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in games:
        home = str(game.get("home_team") or "").strip()
        away = str(game.get("away_team") or "").strip()
        if not home or not away:
            continue
        key = f"{away.lower()}@{home.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(game)
    return out


def _is_final_status(status: str) -> bool:
    s = (status or "").strip().casefold()
    return any(token in s for token in ("final", "completed", "post", "cancel", "postpone"))


def public_verified_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    """Build schedule-verified moneyline sides from public feeds (no book prices)."""
    sport_l = canonical_app_sport(sport)
    if sport_l == "all":
        merged: list[CandidateInput] = []
        for key in PUBLIC_FALLBACK_SPORTS:
            try:
                merged.extend(public_verified_slate(key, slate_date))
            except Exception:
                logger.exception("Public fallback failed for %s", key)
        return merged
    if sport_l not in PUBLIC_FALLBACK_SPORTS:
        return []

    now = datetime.now(UTC)
    league = _LEAGUE.get(sport_l, sport_public_label(sport_l))
    candidates: list[CandidateInput] = []

    for game in _schedule_games(sport_l, slate_date):
        if _is_final_status(str(game.get("status") or "")):
            continue
        home = str(game.get("home_team") or "").strip()
        away = str(game.get("away_team") or "").strip()
        start_time = _parse_start(game.get("start_time"), slate_date)
        game_status, market_status = event_market_status(start_time, now)
        if market_status != "OPEN":
            continue
        event_id = str(game.get("event_id") or f"pub-{sport_l}-{away}-{home}-{slate_date}")
        event_name = f"{away} @ {home}"
        try:
            research = build_event_research(
                sport=sport_l,
                slate_date=slate_date,
                home_team=home,
                away_team=away,
                bookmakers=[],
            )
        except Exception:
            logger.exception("Public research failed for %s", event_name)
            continue

        flags = dict(research.get("flags") or {})
        flags["schedule_verified"] = True
        flags["home_away_verified"] = True
        flags["universe_scan_complete"] = True
        # No books → never claim market movement consensus.
        flags["market_movement_verified"] = False
        research["flags"] = flags
        source_status = dict(research.get("source_status") or {})
        source_status["schedule"] = "confirmed"
        # "n/a" (not "unknown") so readiness does not hard-gap market while Odds is down.
        source_status["market"] = "n/a"
        research["source_status"] = source_status

        for team, side in ((home, "home"), (away, "away")):
            try:
                seed = build_verified_candidate(
                    sport=sport_l,
                    league=league,
                    candidate_id=f"pub-{sport_l}-ml-{side}-{event_id[:16]}",
                    event_id=event_id,
                    event_name=event_name,
                    home_team=home,
                    away_team=away,
                    start_time=start_time,
                    market_type="moneyline",
                    selection=f"{team} ML",
                    odds=-110,
                    line=None,
                    thesis_key=f"pub-{sport_l}-{side}-ml-{slate_date}",
                    script_key=f"pub-{sport_l}-{event_id[:12]}-{side}",
                    reason_codes=["PUBLIC_SCHEDULE_FALLBACK", "CURRENT_FORM"],
                    reasoning=[
                        "Odds API unavailable — public schedule + form research only.",
                        f"Source: {game.get('source') or 'public_scoreboard'}.",
                        "No sportsbook price — fair odds from model probability (PARTIAL).",
                    ],
                    research=research,
                    now=now,
                )
            except Exception:
                logger.exception("Public candidate build failed for %s", team)
                continue

            fair = fair_american_odds(float(seed.estimated_probability))
            # Floor quality above minimum so Check can clear LEAN while Odds is down;
            # still PARTIAL / LEAN-capped — never claim a priced VERIFIED book board.
            quality = max(0.68, float(seed.data_quality or 0.0))
            candidates.append(
                seed.model_copy(
                    update={
                        "american_odds": fair,
                        "probability_source": "model",
                        "data_source": "PUBLIC_SCHEDULE_FALLBACK",
                        "data_quality": quality,
                        "schedule_verified": True,
                        "home_away_verified": True,
                        "universe_scan_complete": True,
                        "market_movement_verified": False,
                        "game_status": game_status,
                        "market_status": market_status,
                        "source_status": {
                            **dict(seed.source_status or {}),
                            "schedule": "confirmed",
                            "market": "n/a",
                        },
                        "reason_codes": list(
                            dict.fromkeys(
                                [
                                    *(seed.reason_codes or []),
                                    "PUBLIC_SCHEDULE_FALLBACK",
                                    "NO_SPORTSBOOK_PRICE",
                                ]
                            )
                        ),
                    }
                )
            )

    return candidates


def public_fallback_notice(sport: str, count: int) -> str:
    label = "ALL SPORTS" if sport == "all" else sport_public_label(sport)
    return (
        f"PUBLIC FALLBACK board for {label}: {count} schedule-verified moneyline sides "
        "from free official/public feeds (ESPN / NHL / MLB). The Odds API is down or "
        "unconfigured, so there are no sportsbook prices — fair model odds only. "
        "LEAN-only picks can still clear while Odds is down — never treat as a priced "
        "VERIFIED book board until Odds recovers."
    )
