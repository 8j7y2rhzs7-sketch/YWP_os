"""Build MLB candidates from official MLB facts and real sportsbook prices.

The projection is intentionally independent from the sportsbook price. MLB's
Stats API supplies schedule, form, starters, rosters, lineups, weather, and
bullpen workload. The Odds API supplies only the currently offered line/price.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.schemas import CandidateInput
from app.services.mlb_model import MLBProjection, pitcher_l5_summary, project_mlb_game
from app.services.mlb_provider import (
    get_bullpen_usage,
    get_game_context,
    get_pitcher_game_log,
    get_schedule,
    get_team_availability,
    get_team_recent_form,
    pitcher_k_stats,
    player_headshot_url,
    team_logo_url,
)
from app.services.odds_provider import (
    extract_best_odds,
    extract_player_prop,
    get_game_odds,
    get_last_fetch_status,
    get_player_props,
    match_game_to_event,
)
from app.services.research_searchers import run_mlb_research_searchers
from app.services.ticket_gates import event_market_status
from app.services.board_metrics import bookmaker_display_name

logger = logging.getLogger(__name__)


def live_mlb_slate(slate_date: date) -> list[CandidateInput]:
    """Return a complete real-market MLB candidate universe for one date."""
    games = get_schedule(slate_date)
    if not games:
        logger.warning("No eligible MLB games found for %s", slate_date)
        return []

    odds_events = get_game_odds(sport="baseball_mlb", markets="h2h,spreads,totals")
    if not odds_events:
        logger.warning(
            "No MLB prices returned by The Odds API (status=%s); no actionable "
            "candidates can be created without a real line and price.",
            get_last_fetch_status(),
        )
        return []

    now = datetime.now(UTC)
    candidates: list[CandidateInput] = []
    prop_events_used = 0

    for game in games:
        matched_event = match_game_to_event(game, odds_events)
        if not matched_event:
            logger.info("No sportsbook event match for MLB game %s", game.get("game_pk"))
            continue

        bookmakers = matched_event.get("bookmakers", [])
        if not bookmakers:
            continue

        research = _game_research(game, slate_date)
        # Seed context with schedule-level weather/officials/venue before searchers.
        context = research["context"]
        if game.get("weather") and not context.get("weather", {}).get("verified"):
            weather = game.get("weather") or {}
            context["weather"] = {
                "verified": bool(weather),
                "condition": weather.get("condition"),
                "temperature_f": weather.get("temp"),
                "wind": weather.get("wind"),
            }
        if game.get("venue") and not context.get("venue"):
            context["venue"] = game.get("venue")
            context["park_verified"] = True
        if game.get("officials") and not context.get("umpire_verified"):
            context["officials"] = game.get("officials")
            context["umpire_verified"] = True
        searchers = run_mlb_research_searchers(
            game=game,
            context=context,
            slate_date=slate_date,
            bookmakers=bookmakers,
        )
        research["searchers"] = searchers
        if searchers["umpires"].get("verified"):
            context["umpire_verified"] = True
            context["officials"] = searchers["umpires"].get("crew") or context.get("officials")
        if searchers["park"].get("verified"):
            context["park_verified"] = True
            context["venue"] = searchers["park"].get("venue") or context.get("venue")
        if (
            not context.get("weather", {}).get("verified")
            and searchers["weather_backup"].get("verified")
        ):
            context["weather"] = {
                "verified": True,
                "condition": searchers["weather_backup"].get("condition"),
                "temperature_f": searchers["weather_backup"].get("temperature_c"),
                "wind": searchers["weather_backup"].get("wind_kph"),
                "source": "open_meteo",
            }
        research["context"] = context
        research["market_search"] = searchers.get("market") or {}

        projection = project_mlb_game(
            home_form=research["home_form"],
            away_form=research["away_form"],
            home_pitcher_l5=research["home_pitcher_l5"],
            away_pitcher_l5=research["away_pitcher_l5"],
            home_bullpen=research["home_bullpen"],
            away_bullpen=research["away_bullpen"],
        )

        event_id = str(matched_event.get("id") or game["game_pk"])
        event_name = f"{game['away_team']} @ {game['home_team']}"
        start_time = _parse_start(game.get("game_date"), slate_date)

        candidates.extend(
            _game_market_candidates(
                game=game,
                research=research,
                projection=projection,
                bookmakers=bookmakers,
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                slate_date=slate_date,
                now=now,
            )
        )

        if settings.mlb_props_enabled and prop_events_used < settings.mlb_max_prop_events:
            # Count the attempted event request so a slate refresh can never exceed
            # the configured request budget, including events with no posted props.
            prop_events_used += 1
            prop_payload = get_player_props(
                event_id,
                sport="baseball_mlb",
                markets="pitcher_strikeouts",
            )
            if prop_payload:
                candidates.extend(
                    _pitcher_strikeout_candidates(
                        game=game,
                        research=research,
                        bookmakers=prop_payload.get("bookmakers", []),
                        event_id=event_id,
                        event_name=event_name,
                        start_time=start_time,
                        slate_date=slate_date,
                        now=now,
                    )
                )

    logger.info("Built %d independent-model MLB candidates for %s", len(candidates), slate_date)
    return candidates


def _game_market_candidates(
    *,
    game: dict[str, Any],
    research: dict[str, Any],
    projection: MLBProjection,
    bookmakers: list[dict[str, Any]],
    event_id: str,
    event_name: str,
    start_time: datetime,
    slate_date: date,
    now: datetime,
) -> list[CandidateInput]:
    candidates: list[CandidateInput] = []

    for side in ("home", "away"):
        team = str(game[f"{side}_team"])
        offer = extract_best_odds(bookmakers, "h2h", team)
        if not offer:
            continue
        probability = projection.moneyline_probability(side)
        recent_rate = float(research[f"{side}_form"].get("l10", {}).get("win_pct", 0.5))
        candidates.append(
            _build_candidate(
                game=game,
                research=research,
                candidate_id=f"mlb-ml-{side}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="moneyline",
                selection=f"{team} ML",
                odds=offer["american_odds"],
                bookmaker=str(offer.get("book") or "") or None,
                probability=probability,
                model_quality=projection.model_quality,
                thesis_key=f"mlb-{_slug(team)}-moneyline-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-{side}-control",
                reason_codes=["INDEPENDENT_MODEL", "CURRENT_FORM", "STARTING_PITCHER_EDGE"],
                reasoning=[
                    *projection.reasoning,
                    f"Actual {offer['book']} moneyline price is used only for value comparison.",
                ],
                factors=_side_factors(side, projection, research),
                recent_hit_rate=recent_rate,
                average_cushion=round(abs(probability - 0.5) * 10, 2),
                matchup_score=probability,
                script_alignment=probability,
                multiple_paths_score=_multiple_paths_score(side, research),
                now=now,
            )
        )

    for direction, label, market_type in (
        ("over", "Over", "game_total_over"),
        ("under", "Under", "game_total_under"),
    ):
        offer = extract_best_odds(bookmakers, "totals", label)
        if not offer or offer.get("point") is None:
            continue
        line = Decimal(str(offer["point"]))
        probability = projection.total_probability(float(line), direction)
        totals = [
            *research["home_form"].get("l10", {}).get("totals", []),
            *research["away_form"].get("l10", {}).get("totals", []),
        ]
        candidates.append(
            _build_candidate(
                game=game,
                research=research,
                candidate_id=f"mlb-{direction}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type=market_type,
                selection=f"{label} {line} runs",
                line=line,
                odds=offer["american_odds"],
                bookmaker=str(offer.get("book") or "") or None,
                probability=probability,
                model_quality=projection.model_quality,
                thesis_key=f"mlb-{_slug(event_name)}-{direction}-{line}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-run-environment",
                reason_codes=["INDEPENDENT_MODEL", "L5_L10_ACTUALS", "BULLPEN_WORKLOAD"],
                reasoning=[
                    *projection.reasoning,
                    f"Actual {offer['book']} total is used only for value comparison.",
                ],
                factors={
                    "projected_total": _scale(projection.expected_total_runs - float(line), 3.0),
                    "current_form": _scale(_average(totals, float(line)) - float(line), 4.0),
                    "bullpen_workload": _bullpen_total_factor(research),
                },
                recent_hit_rate=_recent_total_hit_rate(totals, float(line), direction),
                average_cushion=(
                    projection.expected_total_runs - float(line)
                    if direction == "over"
                    else float(line) - projection.expected_total_runs
                ),
                matchup_score=probability,
                script_alignment=probability,
                multiple_paths_score=0.72,
                miss_by_one_count_l10=_total_miss_by_one(totals, float(line), direction),
                now=now,
            )
        )

    for side in ("home", "away"):
        team = str(game[f"{side}_team"])
        offer = extract_best_odds(bookmakers, "spreads", team)
        if not offer or offer.get("point") is None:
            continue
        line = Decimal(str(offer["point"]))
        probability = projection.spread_probability(side, float(line))
        candidates.append(
            _build_candidate(
                game=game,
                research=research,
                candidate_id=f"mlb-rl-{side}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="run_line",
                selection=f"{team} {line:+}",
                line=line,
                odds=offer["american_odds"],
                bookmaker=str(offer.get("book") or "") or None,
                probability=probability,
                model_quality=projection.model_quality,
                thesis_key=f"mlb-{_slug(team)}-run-line-{line}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-{side}-margin",
                reason_codes=["INDEPENDENT_MODEL", "RUN_DIFFERENTIAL", "STARTER_BULLPEN"],
                reasoning=[
                    *projection.reasoning,
                    f"Independent expected home margin: {projection.expected_home_margin:+.2f}.",
                    f"Actual {offer['book']} run line is used only for value comparison.",
                ],
                factors=_side_factors(side, projection, research),
                recent_hit_rate=float(research[f"{side}_form"].get("l10", {}).get("win_pct", 0.5)),
                average_cushion=_spread_cushion(side, float(line), projection),
                matchup_score=probability,
                script_alignment=probability,
                multiple_paths_score=_multiple_paths_score(side, research),
                now=now,
            )
        )

    return candidates


def _pitcher_strikeout_candidates(
    *,
    game: dict[str, Any],
    research: dict[str, Any],
    bookmakers: list[dict[str, Any]],
    event_id: str,
    event_name: str,
    start_time: datetime,
    slate_date: date,
    now: datetime,
) -> list[CandidateInput]:
    candidates: list[CandidateInput] = []
    for side in ("home", "away"):
        pitcher = game.get(f"{side}_pitcher")
        if not pitcher or not pitcher.get("id") or not pitcher.get("name"):
            continue
        offer = extract_player_prop(
            bookmakers,
            market_key="pitcher_strikeouts",
            player_name=pitcher["name"],
            outcome_name="Over",
        )
        if not offer:
            continue

        logs = research[f"{side}_pitcher_log"]
        if len(logs) < 3:
            continue
        line = Decimal(str(offer["point"]))
        k_stats = pitcher_k_stats(logs)
        probability = _pitcher_k_probability(logs, float(line))
        summary = research[f"{side}_pitcher_l5"] or {}
        opponent_side = "away" if side == "home" else "home"
        first_start_back = _listed_unavailable(int(pitcher["id"]), research[f"{side}_availability"])
        duration_verified = (
            len(logs) >= 5
            and float(k_stats.get("avg_ip", 0)) >= 4.5
            and float(summary.get("avg_pitches", 0)) >= 70
        )

        candidates.append(
            _build_candidate(
                game=game,
                research=research,
                candidate_id=f"mlb-k-{side}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="player_strikeouts_over",
                selection=f"{pitcher['name']} Over {line} strikeouts",
                line=line,
                odds=offer["american_odds"],
                bookmaker=str(offer.get("book") or "") or None,
                probability=probability,
                model_quality=min(0.92, 0.62 + 0.035 * min(len(logs), 10)),
                thesis_key=f"mlb-{_slug(pitcher['name'])}-k-over-{line}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-{_slug(pitcher['name'])}-strikeouts",
                player_key=f"mlb-pitcher-{pitcher['id']}",
                reason_codes=["INDEPENDENT_MODEL", "ACTUAL_L5_L10", "MISS_BY_ONE_CHECK"],
                reasoning=[
                    f"Official MLB L5: {k_stats['avg_k']} average strikeouts, "
                    f"{k_stats['floor_k']} floor, {k_stats['avg_ip']} average innings.",
                    f"Actual {offer['book']} line and price are used only for value comparison.",
                ],
                factors={
                    "recent_strikeouts": _scale(k_stats["avg_k"] - float(line), 3.0),
                    "workload": _scale(k_stats["avg_ip"] - 5.0, 2.0),
                    "opponent_lineup": 0.2
                    if research["context"].get(opponent_side, {}).get("lineup_confirmed")
                    else 0.0,
                },
                recent_hit_rate=_k_hit_rate(logs, float(line)),
                average_cushion=round(k_stats["avg_k"] - float(line), 2),
                matchup_score=probability,
                script_alignment=0.64,
                multiple_paths_score=0.58,
                miss_by_one_count_l10=_k_miss_by_one(logs, float(line)),
                market_is_pitcher_strikeout_over=True,
                first_start_back=first_start_back,
                normal_workload_confirmed=duration_verified and not first_start_back,
                k_duration_verified=duration_verified,
                now=now,
            )
        )
    return candidates


def _build_candidate(
    *,
    game: dict[str, Any],
    research: dict[str, Any],
    candidate_id: str,
    event_id: str,
    event_name: str,
    start_time: datetime,
    market_type: str,
    selection: str,
    odds: int,
    probability: float,
    model_quality: float,
    thesis_key: str,
    script_key: str,
    reason_codes: list[str],
    reasoning: list[str],
    factors: dict[str, float],
    recent_hit_rate: float,
    average_cushion: float,
    matchup_score: float,
    script_alignment: float,
    multiple_paths_score: float,
    now: datetime,
    line: Decimal | None = None,
    player_key: str | None = None,
    miss_by_one_count_l10: int = 0,
    market_is_pitcher_strikeout_over: bool = False,
    first_start_back: bool = False,
    normal_workload_confirmed: bool = False,
    k_duration_verified: bool = True,
    bookmaker: str | None = None,
    price_timestamp: datetime | None = None,
) -> CandidateInput:
    context = research["context"]
    lineups_confirmed = bool(
        context.get("home", {}).get("lineup_confirmed")
        and context.get("away", {}).get("lineup_confirmed")
    )
    availability_verified = bool(
        research["home_availability"].get("verified")
        and research["away_availability"].get("verified")
    )
    form_verified = bool(
        research["home_form"].get("verified") and research["away_form"].get("verified")
    )
    bullpen_verified = bool(
        research["home_bullpen"].get("verified") and research["away_bullpen"].get("verified")
    )
    starters_confirmed = bool(
        game.get("home_pitcher", {}).get("id") if game.get("home_pitcher") else False
    ) and bool(game.get("away_pitcher", {}).get("id") if game.get("away_pitcher") else False)
    weather_verified = bool(context.get("weather", {}).get("verified"))
    park_verified = bool(context.get("park_verified") or context.get("venue") or game.get("venue"))
    umpire_verified = bool(context.get("umpire_verified") or game.get("officials"))
    market_search = research.get("market_search") or {}
    # Pregame cards often publish before batting orders. Probable starters + roster
    # availability are enough to clear the lineup gate; still prefer posted orders.
    lineup_gate = lineups_confirmed or (starters_confirmed and availability_verified)
    # Official bullpen workload + both listed starters cover rotation/workload intent.
    motivation_rotation_verified = bullpen_verified and starters_confirmed
    # Trusted sportsbook quotes verify the current market. Multi-book consensus is bonus.
    market_movement_verified = bool(market_search.get("verified", True))
    sport_specific_sweep_complete = bool(
        form_verified
        and availability_verified
        and starters_confirmed
        and (weather_verified or park_verified)
        and motivation_rotation_verified
        and market_movement_verified
        and (umpire_verified or park_verified)
    )

    missing_fields = []
    if not lineups_confirmed:
        missing_fields.append("confirmed batting orders (using probable starters)")
    if not availability_verified:
        missing_fields.append("official roster availability")
    if not weather_verified:
        missing_fields.append("official weather")
    if not starters_confirmed:
        missing_fields.append("both probable starters")
    if not bullpen_verified:
        missing_fields.append("recent bullpen workload")
    if not umpire_verified:
        missing_fields.append("umpire assignment (park/venue verified when available)")
    soft_notes = [
        "Trusted-source research protocol used MLB Stats API"
        + (" + Open-Meteo" if (context.get("weather") or {}).get("source") == "open_meteo" else "")
        + " + The Odds API.",
        "opening-to-current line history not stored; current sportsbook price verified",
    ]
    if market_search.get("book_count"):
        soft_notes.append(str(market_search.get("detail")))

    safe_odds = _valid_american_odds(odds)
    probability = max(0.02, min(0.98, float(probability)))
    source_urls = _source_urls(game, research)
    game_status, market_status = event_market_status(start_time, now)
    abstract = str(game.get("status") or "")
    if abstract == "Live":
        game_status, market_status = "LIVE", "LOCKED"
    elif abstract in {"Final"}:
        game_status, market_status = "FINAL", "CLOSED"
    elif abstract in {"Postponed"}:
        game_status, market_status = "POSTPONED", "CLOSED"
    elif abstract in {"Cancelled"}:
        game_status, market_status = "CANCELLED", "CLOSED"

    team_id = None
    pitcher_id = None
    if player_key and player_key.startswith("mlb-pitcher-"):
        try:
            pitcher_id = int(player_key.rsplit("-", 1)[-1])
        except ValueError:
            pitcher_id = None
    for side in ("home", "away"):
        team_name = str(game.get(f"{side}_team") or "")
        if team_name and team_name in selection:
            team_id = game.get(f"{side}_id")
            break
    if team_id is None:
        team_id = game.get("home_id")

    source_status: dict[str, str] = {
        "schedule": "confirmed",
        "market": "confirmed",
        "current_form": "confirmed" if form_verified else "unknown",
        "lineup": "confirmed" if lineups_confirmed else ("probable" if starters_confirmed else "unknown"),
        "injuries": "confirmed" if availability_verified else "unknown",
        "weather": "confirmed" if weather_verified else ("probable" if park_verified else "unknown"),
        "starter": "confirmed" if starters_confirmed else "probable",
        "bullpen": "confirmed" if bullpen_verified else "unknown",
        "motivation": "confirmed" if motivation_rotation_verified else "unknown",
        "umpire_park": "confirmed"
        if umpire_verified and park_verified
        else ("probable" if park_verified else "unknown"),
        "market_movement": "confirmed",
    }
    hard_missing = [
        field
        for field in missing_fields
        if not field.startswith("confirmed batting orders")
        and not field.startswith("umpire assignment")
        and not (field.startswith("official weather") and park_verified)
    ]
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport="mlb",
        league="MLB",
        start_time=start_time,
        home_team=str(game.get("home_team") or "") or None,
        away_team=str(game.get("away_team") or "") or None,
        bookmaker=bookmaker,
        bookmaker_label=bookmaker_display_name(bookmaker),
        price_timestamp=price_timestamp or now,
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=safe_odds,
        estimated_probability=probability,
        probability_source="model",
        variance=0.30 if not market_is_pitcher_strikeout_over else 0.39,
        data_quality=max(0.55, min(0.94, model_quality)),
        factors={key: max(-1.0, min(1.0, float(value))) for key, value in factors.items()},
        reason_codes=reason_codes,
        reasoning=[*reasoning, *soft_notes],
        data_source="MLB_STATS_API+THE_ODDS_API",
        source_urls=source_urls,
        source_timestamp=now,
        missing_fields=hard_missing,
        source_status=source_status,  # type: ignore[arg-type]
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=form_verified,
        l5_l10_verified=form_verified,
        lineup_confirmed=lineup_gate,
        injuries_verified=availability_verified,
        weather_verified=weather_verified or park_verified,
        starter_confirmed=starters_confirmed,
        motivation_rotation_verified=motivation_rotation_verified,
        home_away_verified=True,
        market_movement_verified=market_movement_verified,
        sport_specific_sweep_complete=sport_specific_sweep_complete,
        game_status=game_status,  # type: ignore[arg-type]
        market_status=market_status,  # type: ignore[arg-type]
        market_is_pitcher_strikeout_over=market_is_pitcher_strikeout_over,
        first_start_back=first_start_back,
        normal_workload_confirmed=normal_workload_confirmed,
        k_duration_verified=k_duration_verified,
        bullpen_verified=bullpen_verified,
        recent_hit_rate=max(0.0, min(1.0, recent_hit_rate)),
        average_cushion=average_cushion,
        matchup_score=max(0.0, min(1.0, matchup_score)),
        script_alignment=max(0.0, min(1.0, script_alignment)),
        multiple_paths_score=max(0.0, min(1.0, multiple_paths_score)),
        role_stability=0.82 if starters_confirmed else 0.55,
        miss_by_one_count_l10=min(10, max(0, miss_by_one_count_l10)),
        ain_checks={
            "recent_form_l5_l10": form_verified,
            "situational_angles": bullpen_verified and availability_verified,
            "h2h_context": None,
        },
        thesis_key=thesis_key,
        script_key=script_key,
        player_key=player_key,
        image_url=player_headshot_url(pitcher_id),
        team_image_url=team_logo_url(team_id if isinstance(team_id, int) else None),
        safer_alternative=f"Use a lower line only if its own model edge is verified: {selection}",
        higher_upside=f"Use a higher line only after a separate cushion check: {selection}",
        invalidation_conditions=[
            "Starting pitcher or batting-order change",
            "Material weather change",
            "Large adverse price move",
        ],
        live_trigger="Rebuild from current MLB game state and a fresh price before live entry.",
        hedge=(
            "Compare cash-out value with the current independent remaining-game estimate; "
            "do not hedge solely because the price moved."
        ),
    )
def _game_research(game: dict[str, Any], slate_date: date) -> dict[str, Any]:
    """Fetch independent official inputs concurrently with safe partial defaults."""
    home_id = game.get("home_id")
    away_id = game.get("away_id")
    home_pitcher = game.get("home_pitcher") or {}
    away_pitcher = game.get("away_pitcher") or {}

    tasks: dict[str, tuple[Callable[..., Any], tuple[Any, ...], Any]] = {
        "home_form": (get_team_recent_form, (home_id, slate_date), _empty_form()),
        "away_form": (get_team_recent_form, (away_id, slate_date), _empty_form()),
        "home_availability": (get_team_availability, (home_id,), _empty_availability()),
        "away_availability": (get_team_availability, (away_id,), _empty_availability()),
        "context": (get_game_context, (game["game_pk"],), _empty_context()),
        "home_bullpen": (get_bullpen_usage, (home_id, slate_date), _empty_bullpen()),
        "away_bullpen": (get_bullpen_usage, (away_id, slate_date), _empty_bullpen()),
        "home_pitcher_log": (
            get_pitcher_game_log,
            (home_pitcher.get("id"), None, 10),
            [],
        ),
        "away_pitcher_log": (
            get_pitcher_game_log,
            (away_pitcher.get("id"), None, 10),
            [],
        ),
    }

    futures: dict[str, tuple[Future[Any], Any]] = {}
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="mlb-source") as pool:
        for key, (function, args, default) in tasks.items():
            # Every task's first positional argument is its required MLB id.
            # A later None is valid (the optional season for pitcher game logs).
            if not args or args[0] is None:
                continue
            futures[key] = (pool.submit(function, *args), default)
        result = {
            key: _safe_future(key, future, default) for key, (future, default) in futures.items()
        }

    for key, (_, _, default) in tasks.items():
        result.setdefault(key, default)
    result["home_pitcher_l5"] = pitcher_l5_summary(result["home_pitcher_log"])
    result["away_pitcher_l5"] = pitcher_l5_summary(result["away_pitcher_log"])
    return result


def _safe_future(key: str, future: Future[Any], default: Any) -> Any:
    try:
        return future.result()
    except Exception as exc:
        logger.warning("Official MLB source failed for %s: %s", key, exc)
        return default


def _empty_form() -> dict[str, Any]:
    summary = {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_pct": 0.5,
        "avg_runs_for": 4.4,
        "avg_runs_against": 4.4,
        "run_diff_per_game": 0.0,
        "totals": [],
    }
    return {"verified": False, "l5": dict(summary), "l10": dict(summary), "games": []}


def _empty_availability() -> dict[str, Any]:
    return {"verified": False, "active": [], "injured": [], "unavailable": []}


def _empty_bullpen() -> dict[str, Any]:
    return {"verified": False, "heavy_usage": False, "relievers": []}


def _empty_context() -> dict[str, Any]:
    side = {"lineup_confirmed": False, "lineup": [], "pitchers": [], "bullpen": []}
    return {
        "verified": False,
        "status": "Unknown",
        "home": dict(side),
        "away": dict(side),
        "weather": {"verified": False},
        "venue": "",
        "officials": [],
        "park_verified": False,
        "umpire_verified": False,
    }


def _source_urls(game: dict[str, Any], research: dict[str, Any]) -> list[str]:
    searchers = research.get("searchers") or {}
    urls = [
        game.get("mlb_game_url"),
        research["context"].get("source_url"),
        research["context"].get("gameday_url"),
        research["home_form"].get("source_url"),
        research["away_form"].get("source_url"),
        research["home_availability"].get("source_url"),
        research["away_availability"].get("source_url"),
        research["home_bullpen"].get("source_url"),
        research["away_bullpen"].get("source_url"),
        (searchers.get("umpires") or {}).get("source_url"),
        (searchers.get("park") or {}).get("source_url"),
        (searchers.get("weather_backup") or {}).get("source_url"),
        "https://statsapi.mlb.com",
        "https://the-odds-api.com/",
    ]
    return list(dict.fromkeys(str(url) for url in urls if url))[:12]


def _side_factors(
    side: str,
    projection: MLBProjection,
    research: dict[str, Any],
) -> dict[str, float]:
    sign = 1.0 if side == "home" else -1.0
    home_l10 = research["home_form"].get("l10", {})
    away_l10 = research["away_form"].get("l10", {})
    form_edge = float(home_l10.get("win_pct", 0.5)) - float(away_l10.get("win_pct", 0.5))
    run_edge = float(home_l10.get("run_diff_per_game", 0.0)) - float(
        away_l10.get("run_diff_per_game", 0.0)
    )
    return {
        "current_form": _scale(sign * form_edge, 0.5),
        "run_differential": _scale(sign * run_edge, 3.0),
        "projected_margin": _scale(sign * projection.expected_home_margin, 4.0),
    }


def _multiple_paths_score(side: str, research: dict[str, Any]) -> float:
    opponent = "away" if side == "home" else "home"
    score = 0.55
    if research[f"{side}_form"].get("verified"):
        score += 0.08
    if research[f"{opponent}_bullpen"].get("heavy_usage"):
        score += 0.08
    if research[f"{side}_pitcher_l5"]:
        score += 0.06
    return min(0.85, score)


def _bullpen_total_factor(research: dict[str, Any]) -> float:
    heavy = int(bool(research["home_bullpen"].get("heavy_usage"))) + int(
        bool(research["away_bullpen"].get("heavy_usage"))
    )
    return 0.25 * heavy


def _spread_cushion(side: str, line: float, projection: MLBProjection) -> float:
    side_margin = (
        projection.expected_home_margin if side == "home" else -projection.expected_home_margin
    )
    return round(side_margin + line, 2)


def _recent_total_hit_rate(values: list[int], line: float, direction: str) -> float:
    if not values:
        return 0.5
    hits = sum(value > line if direction == "over" else value < line for value in values)
    return round(hits / len(values), 3)


def _total_miss_by_one(values: list[int], line: float, direction: str) -> int:
    count = 0
    for value in values[:10]:
        missed = value <= line if direction == "over" else value >= line
        if missed and abs(value - line) <= 1.0:
            count += 1
    return count


def _pitcher_k_probability(logs: list[dict[str, Any]], line: float) -> float:
    sample = logs[:10]
    if not sample:
        return 0.5
    values = [float(item.get("strikeouts", 0) or 0) for item in sample]
    empirical = (sum(value > line for value in values) + 1) / (len(values) + 2)
    average_margin = sum(values) / len(values) - line
    margin_probability = 1 / (1 + math.exp(-average_margin / 1.5))
    return round(max(0.08, min(0.92, 0.72 * empirical + 0.28 * margin_probability)), 4)


def _k_hit_rate(logs: list[dict[str, Any]], line: float) -> float:
    sample = logs[:10]
    if not sample:
        return 0.5
    return round(
        sum(float(item.get("strikeouts", 0) or 0) > line for item in sample) / len(sample), 3
    )


def _k_miss_by_one(logs: list[dict[str, Any]], line: float) -> int:
    return sum(
        float(item.get("strikeouts", 0) or 0) <= line
        and abs(float(item.get("strikeouts", 0) or 0) - line) <= 1.0
        for item in logs[:10]
    )


def _listed_unavailable(player_id: int, availability: dict[str, Any]) -> bool:
    players = [*availability.get("injured", []), *availability.get("unavailable", [])]
    return any(item.get("id") == player_id for item in players)


def _valid_american_odds(value: Any) -> int:
    try:
        odds = int(value)
    except (TypeError, ValueError):
        odds = 100
    odds = max(-10000, min(10000, odds))
    if odds == 0 or -100 < odds < 100:
        return -100 if odds < 0 else 100
    return odds


def _average(values: list[int], default: float) -> float:
    return sum(values) / len(values) if values else default


def _scale(value: float, denominator: float) -> float:
    return max(-1.0, min(1.0, value / denominator))


def _parse_start(game_date: str | None, slate_date: date) -> datetime:
    if game_date:
        try:
            return datetime.fromisoformat(game_date.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            pass
    return datetime(slate_date.year, slate_date.month, slate_date.day, 23, 0, tzinfo=UTC)


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("@", "at").replace(".", "")[:60]
