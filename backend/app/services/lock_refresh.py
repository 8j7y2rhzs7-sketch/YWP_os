"""Fetch fresh provider state for Lock Check.

Architecture: Lock Check compares the stored recommendation snapshot with a
current provider snapshot immediately before placement. The phone must not
invent sportsbook or MLB facts — the API refreshes them here.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models import Recommendation, Ticket
from app.schemas import CurrentStateUpdate
from app.services.mlb_provider import get_game_context
from app.services.odds_provider import (
    extract_best_odds,
    extract_player_prop,
    get_event_odds,
    get_player_props,
    odds_api_configured,
)

logger = logging.getLogger(__name__)

_ABSTRACT_STATUS = {
    "preview": "PRE_GAME",
    "pre-game": "PRE_GAME",
    "pregame": "PRE_GAME",
    "warmup": "PRE_GAME",
    "scheduled": "PRE_GAME",
    "live": "LIVE",
    "in progress": "LIVE",
    "final": "FINAL",
    "game over": "FINAL",
    "postponed": "POSTPONED",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
}


def ensure_lock_updates(
    ticket: Ticket,
    supplied: list[CurrentStateUpdate],
) -> list[CurrentStateUpdate]:
    """Fill missing per-leg updates from live providers for non-demo tickets."""
    by_id = {item.recommendation_id: item for item in supplied}
    merged: list[CurrentStateUpdate] = list(supplied)
    now = datetime.now(UTC)
    for leg in ticket.legs:
        if leg.action not in {"follow", "replace"}:
            continue
        recommendation = leg.recommendation
        if recommendation.id in by_id:
            continue
        if recommendation.data_source == "YWP_DEMO_PROVIDER":
            continue
        fetched = fetch_recommendation_lock_update(recommendation)
        if fetched is None:
            fetched = CurrentStateUpdate(
                recommendation_id=recommendation.id,
                source_timestamp=now,
                market_available=True,
                data_quality=0.0,
                notes=[
                    "Provider refresh failed; no fresh sportsbook/MLB snapshot available."
                ],
            )
        merged.append(fetched)
    return merged


def fetch_recommendation_lock_update(
    recommendation: Recommendation,
) -> CurrentStateUpdate | None:
    """Build a CurrentStateUpdate from live MLB + Odds API facts when possible."""
    sport = (recommendation.sport or "").lower()
    now = datetime.now(UTC)
    if sport == "mlb":
        return _mlb_lock_update(recommendation, now)
    # Generic sportsbook refresh for other live sports with Odds API event ids.
    return _odds_only_lock_update(recommendation, now, sport_key=_odds_sport_key(sport))


def _odds_sport_key(sport: str) -> str:
    mapping = {
        "mlb": "baseball_mlb",
        "nfl": "americanfootball_nfl",
        "ncaaf": "americanfootball_ncaaf",
        "nba": "basketball_nba",
        "wnba": "basketball_wnba",
        "nhl": "icehockey_nhl",
        "soccer": "soccer_epl",
        "kbo": "baseball_kbo",
    }
    return mapping.get(sport, f"baseball_{sport}" if sport else "baseball_mlb")


def _game_pk(recommendation: Recommendation) -> int | None:
    snap = recommendation.snapshot or {}
    for key in ("game_pk", "mlb_game_pk"):
        raw = snap.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    candidate_id = str(snap.get("candidate_id") or recommendation.candidate_id or "")
    match = re.search(r"-(\d{5,})$", candidate_id)
    if match:
        return int(match.group(1))
    return None


def _map_game_status(abstract: str | None, detailed: str | None = None) -> str:
    for value in (abstract, detailed):
        if not value:
            continue
        mapped = _ABSTRACT_STATUS.get(str(value).strip().casefold())
        if mapped:
            return mapped
    return "UNKNOWN"


def _mlb_lock_update(
    recommendation: Recommendation, now: datetime
) -> CurrentStateUpdate | None:
    snap = recommendation.snapshot or {}
    notes: list[str] = []
    game_pk = _game_pk(recommendation)
    game_status = str(snap.get("game_status") or "PRE_GAME")
    market_status = str(snap.get("market_status") or "OPEN")
    starter_changed = False
    lineup_changed = False
    key_injury_change = False
    severe_weather_change = False
    data_quality = float(recommendation.data_quality)

    if game_pk is not None:
        try:
            context = get_game_context(game_pk)
        except Exception:
            logger.exception("MLB lock refresh failed for game_pk=%s", game_pk)
            context = None
        if context:
            game_status = _map_game_status(
                context.get("status"), context.get("detailed_status")
            )
            notes.append(
                f"MLB live feed refreshed ({context.get('detailed_status') or context.get('status')})."
            )
            # Material lineup flip: was unconfirmed, now confirmed with full order, or vice-versa
            # after we already locked on a posted card — treat newly posted vs snapshot mismatch
            # only when snapshot claimed confirmed orders.
            home = context.get("home") or {}
            away = context.get("away") or {}
            now_lineups = bool(home.get("lineup_confirmed")) and bool(
                away.get("lineup_confirmed")
            )
            was_lineup = bool(snap.get("lineup_confirmed"))
            if was_lineup and not now_lineups and game_status == "PRE_GAME":
                lineup_changed = True
                notes.append("Posted batting orders are no longer confirmed on the live feed.")
            weather = context.get("weather") or {}
            if weather.get("verified"):
                condition = str(weather.get("condition") or "").casefold()
                if any(
                    token in condition
                    for token in ("rain", "snow", "delay", "postpon", "storm")
                ):
                    prior = " ".join(
                        str(x)
                        for x in (
                            (snap.get("factors") or {}),
                            snap.get("reasoning") or [],
                        )
                    ).casefold()
                    if "rain" not in prior and "snow" not in prior:
                        severe_weather_change = True
                        notes.append(
                            f"Weather now flagged on MLB feed: {weather.get('condition')}."
                        )
            data_quality = max(data_quality, 0.70)
        else:
            notes.append("MLB live feed could not be refreshed for this game.")

    odds_update = _odds_price_fields(recommendation, sport_key="baseball_mlb")
    if odds_update is None and not odds_api_configured():
        notes.append("Odds API is not configured; price could not be refreshed.")
        return CurrentStateUpdate(
            recommendation_id=recommendation.id,
            source_timestamp=now,
            current_odds=None,
            market_available=game_status == "PRE_GAME",
            starter_changed=starter_changed,
            lineup_changed=lineup_changed,
            key_injury_change=key_injury_change,
            severe_weather_change=severe_weather_change,
            data_quality=data_quality,
            game_status=game_status,  # type: ignore[arg-type]
            market_status="CLOSED" if game_status != "PRE_GAME" else market_status,  # type: ignore[arg-type]
            notes=notes
            + ["Lock refresh incomplete without a sportsbook price snapshot."],
        )

    if odds_update is None:
        notes.append("Current sportsbook offer for this selection was not found.")
        return CurrentStateUpdate(
            recommendation_id=recommendation.id,
            source_timestamp=now,
            current_odds=None,
            market_available=False,
            starter_changed=starter_changed,
            lineup_changed=lineup_changed,
            key_injury_change=key_injury_change,
            severe_weather_change=severe_weather_change,
            data_quality=data_quality,
            game_status=game_status,  # type: ignore[arg-type]
            market_status="CLOSED",
            notes=notes,
        )

    current_odds, market_available, odds_notes = odds_update
    notes.extend(odds_notes)
    if game_status != "PRE_GAME":
        market_available = False
        market_status = "LOCKED" if game_status == "LIVE" else "CLOSED"
    elif not market_available:
        market_status = "CLOSED"
    else:
        market_status = "OPEN"

    return CurrentStateUpdate(
        recommendation_id=recommendation.id,
        source_timestamp=now,
        current_odds=current_odds,
        market_available=market_available,
        starter_changed=starter_changed,
        lineup_changed=lineup_changed,
        key_injury_change=key_injury_change,
        severe_weather_change=severe_weather_change,
        data_quality=data_quality,
        game_status=game_status,  # type: ignore[arg-type]
        market_status=market_status,  # type: ignore[arg-type]
        first_start_back=bool(snap.get("first_start_back"))
        if snap.get("first_start_back") is not None
        else None,
        normal_workload_confirmed=bool(snap.get("normal_workload_confirmed"))
        if snap.get("normal_workload_confirmed") is not None
        else None,
        k_duration_verified=bool(snap.get("k_duration_verified", True))
        if snap.get("market_is_pitcher_strikeout_over")
        else None,
        bullpen_verified=bool(snap.get("bullpen_verified", True))
        if snap.get("bullpen_game")
        else None,
        notes=notes or ["Provider snapshot refreshed from MLB Stats API + The Odds API."],
    )


def _odds_only_lock_update(
    recommendation: Recommendation, now: datetime, *, sport_key: str
) -> CurrentStateUpdate | None:
    odds_update = _odds_price_fields(recommendation, sport_key=sport_key)
    if odds_update is None:
        return None
    current_odds, market_available, notes = odds_update
    snap = recommendation.snapshot or {}
    game_status = str(snap.get("game_status") or "PRE_GAME")
    market_status = "OPEN" if market_available and game_status == "PRE_GAME" else "CLOSED"
    return CurrentStateUpdate(
        recommendation_id=recommendation.id,
        source_timestamp=now,
        current_odds=current_odds,
        market_available=market_available and game_status == "PRE_GAME",
        data_quality=float(recommendation.data_quality),
        game_status=game_status,  # type: ignore[arg-type]
        market_status=market_status,  # type: ignore[arg-type]
        notes=notes or ["Sportsbook price refreshed from The Odds API."],
    )


def _odds_price_fields(
    recommendation: Recommendation, *, sport_key: str
) -> tuple[int | None, bool, list[str]] | None:
    if not odds_api_configured():
        return None
    event_id = recommendation.event_id
    if not event_id:
        return None

    market_type = (recommendation.market_type or "").lower()
    selection = recommendation.selection or ""
    notes: list[str] = []

    if "pitcher" in market_type or "strikeout" in market_type:
        props = get_player_props(event_id, sport=sport_key)
        if not props:
            return None, False, ["Pitcher prop market could not be refreshed."]
        bookmakers = props.get("bookmakers") or []
        player_name = re.sub(
            r"\s+(Over|Under)\b.*$", "", selection, flags=re.IGNORECASE
        ).strip()
        direction = "Over" if "under" not in selection.casefold() else "Under"
        offer = extract_player_prop(
            bookmakers, "pitcher_strikeouts", player_name, outcome_name=direction
        )
        if not offer:
            return None, False, [f"No current pitcher strikeout offer for {selection}."]
        notes.append(f"Price refreshed from {offer.get('book')}.")
        return int(offer["american_odds"]), True, notes

    event = get_event_odds(event_id, sport=sport_key)
    if not event:
        return None, False, ["Odds API event refresh failed for this market."]
    bookmakers = event.get("bookmakers") or []
    if not bookmakers:
        return None, False, ["Event has no current bookmaker offers."]

    offer: dict[str, Any] | None = None
    if "moneyline" in market_type or market_type in {"h2h", "ml"}:
        team = selection.replace(" ML", "").strip()
        offer = extract_best_odds(bookmakers, "h2h", team)
    elif "total" in market_type:
        direction = "Over" if selection.casefold().startswith("over") else "Under"
        offer = extract_best_odds(bookmakers, "totals", direction)
        if offer and recommendation.line is not None and offer.get("point") is not None:
            if abs(float(offer["point"]) - float(Decimal(str(recommendation.line)))) > 0.01:
                notes.append(
                    f"Total line moved from {recommendation.line} to {offer.get('point')}."
                )
                # Line move is a material market change — treat as unavailable at original line.
                return int(offer["american_odds"]), False, notes
    elif "spread" in market_type or "run_line" in market_type:
        team = re.sub(r"\s*[+-]\d+(\.\d+)?\s*$", "", selection).strip()
        offer = extract_best_odds(bookmakers, "spreads", team)
    else:
        # Last resort: try h2h on selection text.
        offer = extract_best_odds(bookmakers, "h2h", selection)

    if not offer:
        return None, False, [f"No current sportsbook offer matching {selection}."]
    notes.append(f"Price refreshed from {offer.get('book')}.")
    return int(offer["american_odds"]), True, notes
