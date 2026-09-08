"""Sportsbook-style market board for Pick Sheet.

Unlike the model slate (Run), this flattens every currently priced side from
The Odds API into selectable markets — including sides YWP may later SKIP.
Optional model overlay upgrades matching markets to independent projections
so Check & Grade can still clear PLAY/LEAN where research supports it.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.schemas import CandidateInput
from app.services.board_metrics import bookmaker_display_name
from app.services.decision_engine import implied_probability
from app.services.odds_provider import (
    APP_SPORT_TO_ODDS_KEY,
    PREFERRED_BOOKS,
    get_game_odds,
    get_player_props,
    odds_api_configured,
)
from app.services.ticket_gates import event_market_status

logger = logging.getLogger(__name__)

_PROP_MARKETS_BY_SPORT: dict[str, str] = {
    "mlb": "pitcher_strikeouts,batter_hits,batter_total_bases,batter_home_runs,batter_rbis",
    "nba": "player_points,player_rebounds,player_assists,player_threes",
    "wnba": "player_points,player_rebounds,player_assists",
    "nfl": "player_pass_yds,player_rush_yds,player_reception_yds,player_pass_tds",
    "nhl": "player_points,player_shots_on_goal,player_goals",
}

_LEAGUE: dict[str, str] = {
    "mlb": "MLB",
    "wnba": "WNBA",
    "nba": "NBA",
    "nfl": "NFL",
    "ncaaf": "NCAAF",
    "ncaab": "NCAAB",
    "nhl": "NHL",
    "soccer": "MLS",
    "mls": "MLS",
    "epl": "EPL",
    "kbo": "KBO",
}


def build_market_board(
    sport: str,
    slate_date: date,
    *,
    include_props: bool = True,
    overlay_model: bool = True,
) -> tuple[list[CandidateInput], str]:
    """Return (candidates, notice) for a DraftKings-style selectable board."""
    sport_lower = sport.lower().strip()
    odds_key = APP_SPORT_TO_ODDS_KEY.get(sport_lower)
    if not odds_key:
        return [], f"No Odds sport mapping for {sport_lower}."
    if not odds_api_configured() and not settings.demo_mode:
        return [], "ODDS_API_KEY is not configured — cannot load a sportsbook menu."

    odds_events = get_game_odds(sport=odds_key, markets="h2h,spreads,totals")
    if not odds_events:
        return [], (
            f"No priced {sport_lower.upper()} events on {slate_date.isoformat()}. "
            "Change the date or warm odds, then refresh."
        )

    now = datetime.now(UTC)
    board: list[CandidateInput] = []
    matched_events = 0
    for event in odds_events:
        start_time = _parse_start(event.get("commence_time"))
        if start_time is None:
            continue
        if not _on_slate_date(start_time, slate_date):
            continue
        matched_events += 1
        board.extend(
            _flatten_game_markets(
                event=event,
                sport=sport_lower,
                start_time=start_time,
                now=now,
            )
        )

    props_priced = 0
    if include_props and matched_events:
        prop_markets = _PROP_MARKETS_BY_SPORT.get(sport_lower)
        max_events = max(0, int(settings.mlb_board_max_prop_events))
        if prop_markets and max_events:
            priced = 0
            for event in odds_events:
                if priced >= max_events:
                    break
                start_time = _parse_start(event.get("commence_time"))
                if start_time is None or not _on_slate_date(start_time, slate_date):
                    continue
                event_id = str(event.get("id") or "")
                if not event_id:
                    continue
                payload = get_player_props(event_id, sport=odds_key, markets=prop_markets)
                if not payload:
                    continue
                priced += 1
                props_priced += 1
                # Merge prop bookmakers onto the event shape used by flatten.
                merged = dict(event)
                merged["bookmakers"] = payload.get("bookmakers") or []
                board.extend(
                    _flatten_prop_markets(
                        event=merged,
                        sport=sport_lower,
                        start_time=start_time,
                        now=now,
                    )
                )

    overlay_count = 0
    if overlay_model and board:
        board, overlay_count = _overlay_model_candidates(sport_lower, slate_date, board)

    notice = (
        f"Sportsbook menu for {sport_lower.upper()} {slate_date.isoformat()}: "
        f"{matched_events} game(s), {len(board)} selectable market(s)"
        + (f", props priced on {props_priced} event(s)" if props_priced else "")
        + (
            f", {overlay_count} upgraded with independent YWP model probability"
            if overlay_count
            else ""
        )
        + ". Select anything — Check grades each leg; only PLAY/LEAN can build a ticket."
    )
    return board, notice


def _overlay_model_candidates(
    sport: str,
    slate_date: date,
    board: list[CandidateInput],
) -> tuple[list[CandidateInput], int]:
    """Replace board rows with model-slate twins when event/market/selection match."""
    try:
        model_rows = _load_model_slate(sport, slate_date)
    except Exception:
        logger.exception("Model overlay failed for %s board", sport)
        return board, 0
    if not model_rows:
        return board, 0

    by_key = {_match_key(row): row for row in model_rows}
    upgraded = 0
    out: list[CandidateInput] = []
    for row in board:
        twin = by_key.get(_match_key(row))
        if twin is None:
            out.append(row)
            continue
        # Keep board candidate_id stable for the Sheet slip, but use model math.
        merged = twin.model_copy(
            update={
                "candidate_id": row.candidate_id,
                "bookmaker": row.bookmaker or twin.bookmaker,
                "bookmaker_label": row.bookmaker_label or twin.bookmaker_label,
                "american_odds": row.american_odds,
                "line": row.line if row.line is not None else twin.line,
                "price_timestamp": row.price_timestamp or twin.price_timestamp,
            }
        )
        out.append(merged)
        upgraded += 1
    return out, upgraded


def _load_model_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    sport_lower = sport.lower()
    if sport_lower == "mlb":
        from app.services.live_mlb_slate import live_mlb_slate

        return live_mlb_slate(slate_date)
    if sport_lower in {"wnba", "basketball"}:
        from app.services.live_wnba_slate import live_wnba_slate

        return live_wnba_slate(slate_date)
    from app.services.live_generic_slate import SPORT_KEYS, live_generic_slate

    if sport_lower in SPORT_KEYS:
        return live_generic_slate(sport_lower, slate_date)
    return []


def _match_key(candidate: CandidateInput) -> tuple[str, str, str, str]:
    line = "" if candidate.line is None else str(candidate.line)
    selection = re.sub(r"\s+", " ", candidate.selection.casefold().strip())
    return (
        candidate.event_id,
        candidate.market_type.casefold(),
        selection,
        line,
    )


def _flatten_game_markets(
    *,
    event: dict[str, Any],
    sport: str,
    start_time: datetime,
    now: datetime,
) -> list[CandidateInput]:
    bookmakers = event.get("bookmakers") or []
    if not bookmakers:
        return []
    event_id = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    event_name = f"{away} @ {home}" if away and home else event_id
    rows: list[CandidateInput] = []

    for offer in _best_outcomes(bookmakers, market_keys={"h2h", "spreads", "totals"}):
        market_key = offer["market_key"]
        name = offer["name"]
        point = offer.get("point")
        price = offer["price"]
        book = offer["book"]
        if market_key == "h2h":
            if name.casefold() == "draw":
                market_type = "moneyline_draw"
                selection = "Draw"
            else:
                market_type = "moneyline"
                selection = f"{name} ML"
            line = None
        elif market_key == "spreads":
            market_type = "run_line" if sport == "mlb" else "spread"
            if point is None:
                continue
            line = Decimal(str(point))
            selection = f"{name} {float(line):+g}"
        elif market_key == "totals":
            if point is None:
                continue
            line = Decimal(str(point))
            direction = name.casefold()
            if direction.startswith("over"):
                market_type = "game_total_over"
                selection = f"Over {line}"
            elif direction.startswith("under"):
                market_type = "game_total_under"
                selection = f"Under {line}"
            else:
                continue
        else:
            continue
        rows.append(
            _board_candidate(
                sport=sport,
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                home_team=home or None,
                away_team=away or None,
                market_type=market_type,
                selection=selection,
                line=line,
                odds=price,
                bookmaker=book,
                now=now,
                player_key=None,
                market_is_pitcher_strikeout_over=False,
            )
        )
    return rows


def _flatten_prop_markets(
    *,
    event: dict[str, Any],
    sport: str,
    start_time: datetime,
    now: datetime,
) -> list[CandidateInput]:
    bookmakers = event.get("bookmakers") or []
    if not bookmakers:
        return []
    event_id = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    event_name = f"{away} @ {home}" if away and home else event_id
    rows: list[CandidateInput] = []

    for offer in _best_outcomes(
        bookmakers,
        market_keys=None,
        exclude_keys={"h2h", "spreads", "totals"},
    ):
        market_key = offer["market_key"]
        outcome = offer["name"]
        player = str(offer.get("description") or "").strip()
        point = offer.get("point")
        price = offer["price"]
        book = offer["book"]
        if not player or point is None:
            # Some feeds put player in name; keep a usable selection.
            if not player:
                player = outcome
            if point is None:
                continue
        line = Decimal(str(point))
        direction = outcome.casefold()
        if direction not in {"over", "under"} and not direction.endswith(" over") and not direction.endswith(
            " under"
        ):
            # Prefer Overs on the sheet menu to keep density manageable.
            if "over" not in direction:
                continue
            direction = "over"
        is_over = "under" not in direction
        market_type, label, is_k = _prop_market_meta(market_key, is_over=is_over)
        selection = f"{player} {'Over' if is_over else 'Under'} {line} {label}"
        player_slug = re.sub(r"[^a-z0-9]+", "-", player.casefold()).strip("-")
        rows.append(
            _board_candidate(
                sport=sport,
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                home_team=home or None,
                away_team=away or None,
                market_type=market_type,
                selection=selection,
                line=line,
                odds=price,
                bookmaker=book,
                now=now,
                player_key=f"{sport}-prop-{player_slug}"[:120],
                market_is_pitcher_strikeout_over=is_k and is_over,
            )
        )
    return rows


def _prop_market_meta(market_key: str, *, is_over: bool) -> tuple[str, str, bool]:
    key = market_key.casefold()
    is_k = "strikeout" in key
    if is_k:
        return (
            "player_strikeouts_over" if is_over else "player_strikeouts_under",
            "strikeouts",
            True,
        )
    if "hits" in key:
        return ("player_hits_over" if is_over else "player_hits_under", "hits", False)
    if "total_bases" in key or "bases" in key:
        return (
            "player_total_bases_over" if is_over else "player_total_bases_under",
            "total bases",
            False,
        )
    if "home_run" in key:
        return ("player_hr_over" if is_over else "player_hr_under", "home runs", False)
    if "rbi" in key:
        return ("player_rbi_over" if is_over else "player_rbi_under", "RBIs", False)
    suffix = "over" if is_over else "under"
    safe = re.sub(r"[^a-z0-9]+", "_", key).strip("_") or "player_prop"
    return (f"{safe}_{suffix}"[:50], key.replace("_", " "), False)


def _best_outcomes(
    bookmakers: list[dict[str, Any]],
    *,
    market_keys: set[str] | None,
    exclude_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    preferred = PREFERRED_BOOKS
    best: dict[tuple[Any, ...], dict[str, Any]] = {}
    for book in bookmakers:
        book_key = str(book.get("key") or "")
        book_rank = preferred.index(book_key) if book_key in preferred else 999
        for market in book.get("markets") or []:
            market_key = str(market.get("key") or "")
            if market_keys is not None and market_key not in market_keys:
                continue
            if exclude_keys and market_key in exclude_keys:
                continue
            for outcome in market.get("outcomes") or []:
                price = outcome.get("price")
                if not isinstance(price, int) or isinstance(price, bool):
                    continue
                if price == 0 or -100 < price < 100:
                    continue
                name = str(outcome.get("name") or "")
                description = str(outcome.get("description") or "")
                point = outcome.get("point")
                fingerprint = (market_key, name.casefold(), description.casefold(), point)
                row = {
                    "market_key": market_key,
                    "name": name,
                    "description": description,
                    "point": point,
                    "price": price,
                    "book": book_key,
                    "book_rank": book_rank,
                }
                current = best.get(fingerprint)
                if current is None:
                    best[fingerprint] = row
                    continue
                if (book_rank, -price) < (current["book_rank"], -current["price"]):
                    best[fingerprint] = row
    return list(best.values())


def _board_candidate(
    *,
    sport: str,
    event_id: str,
    event_name: str,
    start_time: datetime,
    home_team: str | None,
    away_team: str | None,
    market_type: str,
    selection: str,
    line: Decimal | None,
    odds: int,
    bookmaker: str,
    now: datetime,
    player_key: str | None,
    market_is_pitcher_strikeout_over: bool,
) -> CandidateInput:
    implied = implied_probability(odds)
    implied = max(0.02, min(0.98, float(implied)))
    game_status, market_status = event_market_status(start_time, now)
    slug_sel = re.sub(r"[^a-z0-9]+", "-", selection.casefold()).strip("-")[:80]
    line_part = "nl" if line is None else str(line).replace(".", "p")
    candidate_id = f"board-{sport}-{event_id[:18]}-{market_type}-{line_part}-{slug_sel}"[:100]
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id[:100],
        event_name=event_name[:180],
        sport=sport,
        league=_LEAGUE.get(sport, sport.upper()),
        start_time=start_time,
        home_team=home_team,
        away_team=away_team,
        bookmaker=bookmaker or None,
        bookmaker_label=bookmaker_display_name(bookmaker),
        price_timestamp=now,
        market_type=market_type[:50],
        selection=selection[:180],
        line=line,
        american_odds=odds,
        estimated_probability=implied,
        probability_source="market_implied",
        variance=0.45,
        data_quality=0.35,
        reason_codes=["SPORTSBOOK_MENU", "MARKET_IMPLIED"],
        reasoning=[
            "Priced from the live sportsbook menu for customer selection.",
            "Independent YWP model probability is applied only when research overlay matches.",
        ],
        data_source="THE_ODDS_API_BOARD",
        source_urls=["https://the-odds-api.com/"],
        source_timestamp=now,
        missing_fields=["independent_model_projection"],
        source_status={"market": "confirmed", "schedule": "confirmed"},
        schedule_verified=True,
        market_movement_verified=True,
        game_status=game_status,  # type: ignore[arg-type]
        market_status=market_status,  # type: ignore[arg-type]
        market_is_pitcher_strikeout_over=market_is_pitcher_strikeout_over,
        independent_value_verified=False,
        thesis_key=f"board:{sport}:{event_id}:{market_type}:{slug_sel}:{line_part}"[:160],
        script_key=f"board:{sport}:{event_id}:{market_type}"[:160],
        player_key=player_key,
        safer_alternative="Pick a different market on this sheet if this grade is SKIP.",
        higher_upside="Use Run/Full Protocol when you want model-only candidates.",
        invalidation_conditions=["Price move", "Lineup change", "Market suspension"],
    )


def _parse_start(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _on_slate_date(start_time: datetime, slate_date: date) -> bool:
    if start_time.astimezone(UTC).date() == slate_date:
        return True
    try:
        local = start_time.astimezone(ZoneInfo("America/New_York")).date()
    except Exception:
        return False
    return local == slate_date
