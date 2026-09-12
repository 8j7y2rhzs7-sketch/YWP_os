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

from pydantic import ValidationError
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.schemas import CandidateInput
from app.services.board_metrics import bookmaker_display_name
from app.services.decision_engine import implied_probability
from app.services.single_flight import single_flight
from app.services.odds_provider import (
    APP_SPORT_TO_ODDS_KEY,
    PREFERRED_BOOKS,
    active_odds_keys_for_app_sport,
    get_game_odds,
    get_last_fetch_status,
    get_player_props,
    odds_api_configured,
    soccer_league_label,
    soccer_odds_regions,
)
from app.services.ticket_gates import event_market_status

logger = logging.getLogger(__name__)

_PROP_MARKETS_BY_SPORT: dict[str, str] = {
    # Full DK/Hard-Rock-style MLB prop board (credits scale with markets×events).
    "mlb": (
        "pitcher_strikeouts,pitcher_outs,pitcher_hits_allowed,pitcher_earned_runs,"
        "batter_hits,batter_runs_scored,batter_rbis,batter_home_runs,batter_total_bases,"
        "batter_hits_runs_rbis,batter_stolen_bases,batter_walks"
    ),
    "nba": "player_points,player_rebounds,player_assists,player_threes,player_blocks,player_steals",
    "wnba": "player_points,player_rebounds,player_assists,player_threes,player_points_rebounds_assists",
    "nfl": "player_pass_yds,player_rush_yds,player_reception_yds,player_pass_tds,player_receptions,player_anytime_td",
    # NCAAF Sheet categories priced via Odds event markets (ESPN is facts-only).
    # Covers: TD scorers, pass/rush/rec, combo yards, kicking, longest, Q1 pass yards, total TDs.
    # Deferred (no Odds key / thin books): fantasy points, game highs, full each-half player menus.
    "ncaaf": (
        "player_pass_yds,player_pass_tds,player_rush_yds,player_rush_tds,"
        "player_reception_yds,player_receptions,player_reception_tds,player_anytime_td,"
        "player_pass_rush_yds,player_rush_reception_yds,player_pass_rush_reception_yds,"
        "player_pass_rush_reception_tds,player_tds_over,"
        "player_kicking_points,player_field_goals,player_pats,"
        "player_pass_longest_completion,player_reception_longest,player_rush_longest,"
        "player_pass_yds_q1"
    ),
    "nhl": "player_points,player_shots_on_goal,player_goals,player_assists",
}

# Team period markets (event-odds only). Shared event cap with props to control credits.
_PERIOD_MARKETS_BY_SPORT: dict[str, str] = {
    "ncaaf": "h2h_h1,spreads_h1,totals_h1,h2h_q1,spreads_q1,totals_q1",
    "nfl": "h2h_h1,spreads_h1,totals_h1,h2h_q1,spreads_q1,totals_q1",
}

# Cap prop/period event fan-out for huge Saturday NCAAF slates.
_BOARD_MAX_PROP_EVENTS_BY_SPORT: dict[str, int] = {
    "ncaaf": 3,
}

_LEAGUE: dict[str, str] = {
    "mlb": "MLB",
    "wnba": "WNBA",
    "nba": "NBA",
    "nfl": "NFL",
    "ncaaf": "NCAAF",
    "ncaab": "NCAAB",
    "nhl": "NHL",
    "soccer": "Soccer",
    "mls": "MLS",
    "epl": "EPL",
    "kbo": "KBO",
}


def _build_market_board_uncached(
    sport: str,
    slate_date: date,
    *,
    include_props: bool = True,
    overlay_model: bool = True,
) -> tuple[list[CandidateInput], str]:
    """Return (candidates, notice) for a DraftKings-style selectable board."""
    sport_lower = sport.lower().strip()
    odds_keys = active_odds_keys_for_app_sport(sport_lower)
    if not odds_keys:
        legacy = APP_SPORT_TO_ODDS_KEY.get(sport_lower)
        odds_keys = [legacy] if legacy else []
    if not odds_keys:
        return [], f"No Odds sport mapping for {sport_lower}."
    if not odds_api_configured() and not settings.demo_mode:
        return [], "ODDS_API_KEY is not configured — cannot load a sportsbook menu."

    odds_events: list[dict[str, Any]] = []
    leagues_hit: list[str] = []
    regions = soccer_odds_regions(sport_lower)
    try:
        for odds_key in odds_keys:
            batch = get_game_odds(
                sport=odds_key, markets="h2h,spreads,totals", regions=regions
            )
            if not batch:
                continue
            label = (
                soccer_league_label(odds_key)
                if sport_lower in {"soccer", "epl", "mls"}
                else _LEAGUE.get(sport_lower, sport_lower.upper())
            )
            if label not in leagues_hit:
                leagues_hit.append(label)
            for event in batch:
                enriched = dict(event)
                enriched["_ywp_odds_key"] = odds_key
                enriched["_ywp_league"] = label
                odds_events.append(enriched)
    except Exception:
        logger.exception("Market board odds fetch failed for %s", sport_lower)
        return [], (
            f"Could not fetch {sport_lower.upper()} sportsbook prices right now. "
            "Try again in a minute, or use Run for the model slate."
        )
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
        league = str(event.get("_ywp_league") or _LEAGUE.get(sport_lower, sport_lower.upper()))
        try:
            board.extend(
                _flatten_game_markets(
                    event=event,
                    sport=sport_lower,
                    start_time=start_time,
                    now=now,
                    league=league,
                )
            )
        except Exception:
            logger.exception("Flatten game markets failed for %s", event.get("id"))

    props_priced = 0
    props_errors = 0
    period_priced = 0
    if include_props and matched_events:
        prop_markets = _PROP_MARKETS_BY_SPORT.get(sport_lower)
        period_markets = _PERIOD_MARKETS_BY_SPORT.get(sport_lower)
        default_max = int(
            getattr(settings, "mlb_board_max_prop_events", None)
            or settings.mlb_max_prop_events
            or 0
        )
        max_events = max(
            0,
            int(_BOARD_MAX_PROP_EVENTS_BY_SPORT.get(sport_lower, default_max)),
        )
        if (prop_markets or period_markets) and max_events:
            # Chunk markets — one giant props request often 422s / times out on Render.
            prop_chunks = _chunk_csv(prop_markets, size=4) if prop_markets else []
            period_chunks = (
                _chunk_csv(period_markets, size=3) if period_markets else []
            )
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
                odds_key = str(event.get("_ywp_odds_key") or odds_keys[0])
                league = str(
                    event.get("_ywp_league") or _LEAGUE.get(sport_lower, sport_lower.upper())
                )
                prop_books: list[dict[str, Any]] = []
                period_books: list[dict[str, Any]] = []
                got_props = False
                got_period = False
                for chunk in prop_chunks:
                    try:
                        payload = get_player_props(event_id, sport=odds_key, markets=chunk)
                    except Exception:
                        props_errors += 1
                        logger.warning(
                            "Props chunk failed for %s (%s)", event_id, chunk, exc_info=True
                        )
                        continue
                    if not payload:
                        continue
                    got_props = True
                    prop_books.extend(payload.get("bookmakers") or [])
                for chunk in period_chunks:
                    try:
                        payload = get_player_props(event_id, sport=odds_key, markets=chunk)
                    except Exception:
                        props_errors += 1
                        logger.warning(
                            "Period markets chunk failed for %s (%s)",
                            event_id,
                            chunk,
                            exc_info=True,
                        )
                        continue
                    if not payload:
                        continue
                    got_period = True
                    period_books.extend(payload.get("bookmakers") or [])
                if not got_props and not got_period:
                    continue
                priced += 1
                if got_props:
                    props_priced += 1
                    merged = dict(event)
                    merged["bookmakers"] = prop_books
                    try:
                        board.extend(
                            _flatten_prop_markets(
                                event=merged,
                                sport=sport_lower,
                                start_time=start_time,
                                now=now,
                                league=league,
                            )
                        )
                    except Exception:
                        logger.exception("Flatten prop markets failed for %s", event_id)
                if got_period:
                    period_priced += 1
                    merged_period = dict(event)
                    merged_period["bookmakers"] = period_books
                    try:
                        board.extend(
                            _flatten_period_markets(
                                event=merged_period,
                                sport=sport_lower,
                                start_time=start_time,
                                now=now,
                                league=league,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Flatten period markets failed for %s", event_id
                        )

    overlay_count = 0
    if overlay_model and board:
        try:
            board, overlay_count = _overlay_model_candidates(sport_lower, slate_date, board)
        except Exception:
            logger.exception(
                "Model overlay crashed for %s board — returning book prices only",
                sport_lower,
            )

    remaining = get_last_fetch_status().get("remaining")
    credit_note = ""
    if remaining is not None and str(remaining).strip() != "":
        credit_note = f" Odds credits remaining ≈ {remaining}."
    league_note = ""
    if leagues_hit:
        league_note = f" Leagues: {', '.join(leagues_hit)}."

    notice = (
        f"Sportsbook menu for {sport_lower.upper()} {slate_date.isoformat()}: "
        f"{matched_events} game(s), {len(board)} selectable market(s)"
        + (f", props priced on {props_priced} event(s)" if props_priced else "")
        + (
            f", 1H/1Q team markets on {period_priced} event(s)"
            if period_priced
            else ""
        )
        + (f", {props_errors} prop fetch warning(s)" if props_errors else "")
        + (
            f", {overlay_count} upgraded with independent YWP model probability"
            if overlay_count
            else ""
        )
        + "."
        + league_note
        + " Select anything — Check grades each leg; only PLAY/LEAN can build a ticket."
        + credit_note
    )
    return board, notice



def build_market_board(
    sport: str,
    slate_date: date,
    *,
    include_props: bool = True,
    overlay_model: bool = True,
) -> tuple[list[CandidateInput], str]:
    """Coalesce concurrent Pick Sheet board builds for the same sport/date."""
    props_flag = "props" if include_props else "noprops"
    model_flag = "model" if overlay_model else "book"
    key = (
        f"market-board|{sport.lower().strip()}|{slate_date.isoformat()}"
        f"|{props_flag}|{model_flag}"
    )
    return single_flight(
        key,
        lambda: _build_market_board_uncached(
            sport,
            slate_date,
            include_props=include_props,
            overlay_model=overlay_model,
        ),
        ttl_seconds=45.0,
    )

def _chunk_csv(value: str, *, size: int) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if size <= 0:
        return [value]
    return [",".join(parts[i : i + size]) for i in range(0, len(parts), size)]


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
                # Preserve Sheet provenance so Hive/settle still recognize menu legs.
                "data_source": row.data_source or twin.data_source,
                "reason_codes": sorted(
                    set((twin.reason_codes or []) + (row.reason_codes or []) + ["SPORTSBOOK_MENU"])
                ),
            }
        )
        out.append(merged)
        upgraded += 1
    return out, upgraded


def overlay_selected_with_model(
    sport: str,
    slate_date: date,
    selected: list[CandidateInput],
) -> tuple[list[CandidateInput], int]:
    """Check-path overlay: upgrade only the customer's selected Sheet legs.

    Soft-fails to the original book-implied candidates if model research is slow
    or errors — never blocks grading.
    """
    if not selected:
        return selected, 0
    try:
        return _overlay_model_candidates(sport, slate_date, selected)
    except Exception:
        logger.exception("Selected-leg model overlay crashed for %s", sport)
        return selected, 0


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
    league: str | None = None,
) -> list[CandidateInput]:
    return _flatten_team_markets(
        event=event,
        sport=sport,
        start_time=start_time,
        now=now,
        league=league,
        market_keys={"h2h", "spreads", "totals"},
        default_period="full_game",
    )


def _flatten_period_markets(
    *,
    event: dict[str, Any],
    sport: str,
    start_time: datetime,
    now: datetime,
    league: str | None = None,
) -> list[CandidateInput]:
    return _flatten_team_markets(
        event=event,
        sport=sport,
        start_time=start_time,
        now=now,
        league=league,
        market_keys={
            "h2h_h1",
            "spreads_h1",
            "totals_h1",
            "h2h_q1",
            "spreads_q1",
            "totals_q1",
        },
        default_period="full_game",
    )


def _period_from_odds_market_key(market_key: str) -> tuple[str, str, str]:
    """Return (base_key, market_period, selection_tag) for Odds period markets."""
    key = market_key.casefold()
    for suffix, period, tag in (
        ("_q1", "1q", "1Q"),
        ("_q2", "2q", "2Q"),
        ("_q3", "3q", "3Q"),
        ("_q4", "4q", "4Q"),
        ("_h1", "1h", "1H"),
        ("_h2", "2h", "2H"),
    ):
        if key.endswith(suffix):
            return key[: -len(suffix)], period, tag
    return key, "full_game", ""


def _flatten_team_markets(
    *,
    event: dict[str, Any],
    sport: str,
    start_time: datetime,
    now: datetime,
    league: str | None = None,
    market_keys: set[str],
    default_period: str = "full_game",
) -> list[CandidateInput]:
    bookmakers = event.get("bookmakers") or []
    if not bookmakers:
        return []
    event_id = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    league_label = league or _LEAGUE.get(sport, sport.upper())
    event_name = f"{away} @ {home}" if away and home else event_id
    if sport == "soccer" and league_label and league_label not in {"Soccer", "MLS"}:
        event_name = f"{event_name} ({league_label})"
    rows: list[CandidateInput] = []

    for offer in _best_outcomes(bookmakers, market_keys=market_keys):
        market_key = offer["market_key"]
        base_key, period, tag = _period_from_odds_market_key(market_key)
        if period == "full_game":
            period = default_period
        name = offer["name"]
        point = offer.get("point")
        price = offer["price"]
        book = offer["book"]
        tag_suffix = f" ({tag})" if tag else ""
        if base_key == "h2h":
            if name.casefold() == "draw":
                market_type = "moneyline_draw"
                selection = f"Draw{tag_suffix}"
            else:
                market_type = "moneyline"
                selection = f"{name} ML{tag_suffix}"
            line = None
        elif base_key == "spreads":
            market_type = "run_line" if sport == "mlb" else "spread"
            if point is None:
                continue
            line = Decimal(str(point))
            selection = f"{name} {float(line):+g}{tag_suffix}"
        elif base_key == "totals":
            if point is None:
                continue
            line = Decimal(str(point))
            direction = name.casefold()
            if direction.startswith("over"):
                market_type = "game_total_over"
                selection = f"Over {line}{tag_suffix}"
            elif direction.startswith("under"):
                market_type = "game_total_under"
                selection = f"Under {line}{tag_suffix}"
            else:
                continue
        else:
            continue
        try:
            rows.append(
                _board_candidate(
                    sport=sport,
                    event_id=event_id,
                    event_name=event_name,
                    start_time=start_time,
                    home_team=home or None,
                    away_team=away or None,
                    market_type=market_type,
                    market_period=period,
                    selection=selection,
                    line=line,
                    odds=price,
                    bookmaker=book,
                    now=now,
                    player_key=None,
                    market_is_pitcher_strikeout_over=False,
                    league=league_label,
                )
            )
        except (ValidationError, ValueError) as exc:
            logger.debug("Skip invalid board market %s: %s", selection, exc)
    return rows


def _flatten_prop_markets(
    *,
    event: dict[str, Any],
    sport: str,
    start_time: datetime,
    now: datetime,
    league: str | None = None,
) -> list[CandidateInput]:
    bookmakers = event.get("bookmakers") or []
    if not bookmakers:
        return []
    event_id = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    league_label = league or _LEAGUE.get(sport, sport.upper())
    event_name = f"{away} @ {home}" if away and home else event_id
    rows: list[CandidateInput] = []

    for offer in _best_outcomes(
        bookmakers,
        market_keys=None,
        exclude_keys={
            "h2h",
            "spreads",
            "totals",
            "h2h_h1",
            "spreads_h1",
            "totals_h1",
            "h2h_q1",
            "spreads_q1",
            "totals_q1",
        },
    ):
        market_key = offer["market_key"]
        outcome = offer["name"]
        player = str(offer.get("description") or "").strip()
        point = offer.get("point")
        price = offer["price"]
        book = offer["book"]
        direction = outcome.casefold().strip()
        _, prop_period, _ = _period_from_odds_market_key(market_key)

        # Yes/No player markets (anytime TD scorers, etc.).
        if point is None and direction in {"yes", "no"}:
            if direction == "no":
                continue  # Sheet density: Yes / scorer side only.
            if not player:
                player = outcome
            key_cf = market_key.casefold()
            if "anytime_td" in key_cf:
                market_type = "player_anytime_td_yes"
                selection = f"{player} Anytime TD"
            elif "1st_td" in key_cf or "first_td" in key_cf:
                market_type = "player_first_td_yes"
                selection = f"{player} First TD"
            else:
                safe = re.sub(r"[^a-z0-9]+", "_", key_cf).strip("_") or "player_prop"
                market_type = f"{safe}_yes"[:50]
                selection = f"{player} Yes"
            player_slug = re.sub(r"[^a-z0-9]+", "-", player.casefold()).strip("-")
            try:
                rows.append(
                    _board_candidate(
                        sport=sport,
                        event_id=event_id,
                        event_name=event_name,
                        start_time=start_time,
                        home_team=home or None,
                        away_team=away or None,
                        market_type=market_type,
                        market_period=prop_period,
                        selection=selection[:180],
                        line=None,
                        odds=price,
                        bookmaker=book,
                        now=now,
                        player_key=f"{sport}-prop-{player_slug}"[:120],
                        market_is_pitcher_strikeout_over=False,
                        league=league_label,
                    )
                )
            except (ValidationError, ValueError) as exc:
                logger.debug("Skip invalid yes/no prop %s: %s", selection, exc)
            continue

        if not player or point is None:
            # Some feeds put player in name; keep a usable selection.
            if not player:
                player = outcome
            if point is None:
                continue
        line = Decimal(str(point))
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
        try:
            rows.append(
                _board_candidate(
                    sport=sport,
                    event_id=event_id,
                    event_name=event_name,
                    start_time=start_time,
                    home_team=home or None,
                    away_team=away or None,
                    market_type=market_type,
                    market_period=prop_period,
                    selection=selection[:180],
                    line=line,
                    odds=price,
                    bookmaker=book,
                    now=now,
                    player_key=f"{sport}-prop-{player_slug}"[:120],
                    market_is_pitcher_strikeout_over=is_k and is_over,
                    league=league_label,
                )
            )
        except (ValidationError, ValueError) as exc:
            logger.debug("Skip invalid prop market %s: %s", selection, exc)
    return rows


def _prop_market_meta(market_key: str, *, is_over: bool) -> tuple[str, str, bool]:
    key = market_key.casefold()
    is_k = "strikeout" in key and "batter" not in key
    if is_k:
        return (
            "player_strikeouts_over" if is_over else "player_strikeouts_under",
            "strikeouts",
            True,
        )
    labels = {
        "batter_hits": ("player_hits", "hits"),
        "batter_runs_scored": ("player_runs", "runs"),
        "batter_rbis": ("player_rbi", "RBIs"),
        "batter_home_runs": ("player_hr", "home runs"),
        "batter_total_bases": ("player_total_bases", "total bases"),
        "batter_hits_runs_rbis": ("player_hrr", "hits+runs+RBIs"),
        "batter_stolen_bases": ("player_sb", "stolen bases"),
        "batter_walks": ("player_walks", "walks"),
        "batter_strikeouts": ("batter_strikeouts", "strikeouts"),
        "pitcher_outs": ("pitcher_outs", "outs"),
        "pitcher_hits_allowed": ("pitcher_hits_allowed", "hits allowed"),
        "pitcher_earned_runs": ("pitcher_earned_runs", "earned runs"),
        "pitcher_walks": ("pitcher_walks", "walks"),
        # Football (NFL / NCAAF) player props — longer keys first via sorted match below.
        "player_pass_yds_q1": ("player_pass_yds_q1", "pass yards (1Q)"),
        "player_pass_yds": ("player_pass_yds", "pass yards"),
        "player_pass_tds": ("player_pass_tds", "pass TDs"),
        "player_pass_completions": ("player_pass_comp", "pass completions"),
        "player_pass_attempts": ("player_pass_att", "pass attempts"),
        "player_pass_interceptions": ("player_pass_int", "interceptions"),
        "player_rush_yds": ("player_rush_yds", "rush yards"),
        "player_rush_tds": ("player_rush_tds", "rush TDs"),
        "player_rush_attempts": ("player_rush_att", "rush attempts"),
        "player_reception_yds": ("player_rec_yds", "rec yards"),
        "player_receptions": ("player_receptions", "receptions"),
        "player_reception_tds": ("player_rec_tds", "rec TDs"),
        "player_pass_rush_reception_yds": ("player_prr_yds", "pass+rush+rec yards"),
        "player_pass_rush_reception_tds": ("player_prr_tds", "pass+rush+rec TDs"),
        "player_pass_rush_yds": ("player_pass_rush_yds", "pass+rush yards"),
        "player_rush_reception_yds": ("player_rush_rec_yds", "rush+rec yards"),
        "player_tds_over": ("player_tds", "touchdowns"),
        "player_kicking_points": ("player_kick_pts", "kicking points"),
        "player_field_goals": ("player_fg", "field goals"),
        "player_pats": ("player_pats", "PATs"),
        "player_pass_longest_completion": ("player_longest_pass", "longest completion"),
        "player_reception_longest": ("player_longest_rec", "longest reception"),
        "player_rush_longest": ("player_longest_rush", "longest rush"),
    }
    suffix = "over" if is_over else "under"
    if key in labels:
        prefix, label = labels[key]
        return (f"{prefix}_{suffix}"[:50], label, False)
    for market, (prefix, label) in sorted(labels.items(), key=lambda item: -len(item[0])):
        if key.startswith(market):
            return (f"{prefix}_{suffix}"[:50], label, False)
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
    league: str | None = None,
    market_period: str = "full_game",
) -> CandidateInput:
    implied = implied_probability(odds)
    implied = max(0.02, min(0.98, float(implied)))
    game_status, market_status = event_market_status(start_time, now)
    slug_sel = re.sub(r"[^a-z0-9]+", "-", selection.casefold()).strip("-")[:80]
    line_part = "nl" if line is None else str(line).replace(".", "p")
    period = (market_period or "full_game")[:32]
    candidate_id = (
        f"board-{sport}-{event_id[:18]}-{market_type}-{period}-{line_part}-{slug_sel}"
    )[:100]
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id[:100],
        event_name=event_name[:180],
        sport=sport,
        league=(league or _LEAGUE.get(sport, sport.upper()))[:40],
        start_time=start_time,
        home_team=home_team,
        away_team=away_team,
        bookmaker=bookmaker or None,
        bookmaker_label=bookmaker_display_name(bookmaker),
        price_timestamp=now,
        market_type=market_type[:50],
        market_period=period,
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
        thesis_key=f"board:{sport}:{event_id}:{market_type}:{period}:{slug_sel}:{line_part}"[
            :160
        ],
        script_key=f"board:{sport}:{event_id}:{market_type}:{period}"[:160],
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
