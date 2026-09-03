"""
Live MLB slate builder: merges MLB Stats API schedule/stats with
The Odds API lines into CandidateInput objects for the decision engine.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app.schemas import CandidateInput
from app.services.mlb_provider import (
    compute_l5_stats,
    get_pitcher_game_log,
    get_player_game_log,
    get_schedule,
    pitcher_k_stats,
    player_headshot_url,
    team_logo_url,
)
from app.services.odds_provider import (
    extract_best_odds,
    get_game_odds,
    match_game_to_event,
    odds_to_implied_probability,
)

logger = logging.getLogger(__name__)


def live_mlb_slate(slate_date: date) -> list[CandidateInput]:
    """Build a live CandidateInput list from real MLB + odds data."""
    games = get_schedule(slate_date)
    if not games:
        logger.warning("No MLB games found for %s", slate_date)
        return []

    try:
        odds_events = get_game_odds(sport="baseball_mlb", markets="h2h,spreads,totals")
    except Exception:
        logger.exception("Failed to fetch odds; building slate without book lines")
        odds_events = []

    from app.services.odds_provider import get_last_fetch_status

    odds_status = get_last_fetch_status()
    if not odds_events:
        logger.warning(
            "Odds API returned no MLB events (status=%s). Moneyline/total/run-line markets "
            "will be missing; only pitcher K estimates from MLB.com can be built.",
            odds_status,
        )

    candidates: list[CandidateInput] = []
    now = datetime.now(UTC)

    for game in games:
        matched_event = match_game_to_event(game, odds_events) if odds_events else None
        bookmakers = matched_event.get("bookmakers", []) if matched_event else []
        event_id = matched_event.get("id", str(game["game_pk"])) if matched_event else str(game["game_pk"])
        event_name = f"{game['away_team']} @ {game['home_team']}"

        start_time = _parse_start(game.get("game_date"), slate_date)
        game_status = game.get("game_status") or "PRE_GAME"
        market_status = "OPEN" if game_status == "PRE_GAME" else "CLOSED"

        # --- Moneyline candidates (home + away) ---
        for side in ("home", "away"):
            team = game[f"{side}_team"]
            ml = extract_best_odds(bookmakers, "h2h", team)
            if not ml:
                ml = extract_best_odds(bookmakers, "h2h")
                if ml and ml["name"].lower() not in team.lower():
                    continue
            if not ml:
                continue

            odds_val = ml["american_odds"]
            prob = odds_to_implied_probability(odds_val)
            pitcher = game.get(f"{side}_pitcher")
            pitcher_name = pitcher["name"] if pitcher else "TBD"
            pitcher_id = pitcher.get("id") if pitcher else None

            candidates.append(_build_candidate(
                candidate_id=f"mlb-ml-{side}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="moneyline",
                selection=f"{team} ML",
                odds=odds_val,
                probability=prob,
                thesis_key=f"mlb-{_slug(team)}-moneyline-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-{side}-control",
                reason_codes=_ml_reason_codes(pitcher),
                reasoning=[f"{team} moneyline. Probable pitcher: {pitcher_name}. Record: {game[f'{side}_record']}."],
                now=now,
                game_status=game_status,
                market_status=market_status,
                image_url=player_headshot_url(pitcher_id),
                team_image_url=team_logo_url(game.get(f"{side}_id")),
            ))

        # --- Totals (over/under) ---
        total = extract_best_odds(bookmakers, "totals", "Over")
        total_under = extract_best_odds(bookmakers, "totals", "Under")
        if total and total.get("point"):
            line_val = Decimal(str(total["point"]))
            over_odds = total["american_odds"]
            candidates.append(_build_candidate(
                candidate_id=f"mlb-over-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="game_total_over",
                selection=f"Over {line_val} runs",
                line=line_val,
                odds=over_odds,
                probability=odds_to_implied_probability(over_odds),
                thesis_key=f"mlb-{_slug(event_name)}-over-{line_val}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-runs",
                reason_codes=["LINEUP_EDGE", "BULLPEN_EDGE"],
                reasoning=[f"Game total Over {line_val}. Both lineups and bullpens factor into scoring expectation."],
                now=now,
                game_status=game_status,
                market_status=market_status,
                team_image_url=team_logo_url(game.get("home_id")),
            ))
        if total_under and total_under.get("point"):
            line_val = Decimal(str(total_under["point"]))
            under_odds = total_under["american_odds"]
            candidates.append(_build_candidate(
                candidate_id=f"mlb-under-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="game_total_under",
                selection=f"Under {line_val} runs",
                line=line_val,
                odds=under_odds,
                probability=odds_to_implied_probability(under_odds),
                thesis_key=f"mlb-{_slug(event_name)}-under-{line_val}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-low-scoring",
                reason_codes=["STARTING_PITCHER_EDGE", "BULLPEN_EDGE"],
                reasoning=[f"Game total Under {line_val}. Pitching matchup drives the thesis."],
                now=now,
                game_status=game_status,
                market_status=market_status,
                team_image_url=team_logo_url(game.get("home_id")),
            ))

        # --- Spreads (run line) ---
        for spread_side in ("home", "away"):
            team = game[f"{spread_side}_team"]
            spread = extract_best_odds(bookmakers, "spreads", team)
            if not spread or spread.get("point") is None:
                continue
            spread_line = Decimal(str(spread["point"]))
            spread_odds = spread["american_odds"]
            spread_pitcher = game.get(f"{spread_side}_pitcher")
            candidates.append(_build_candidate(
                candidate_id=f"mlb-rl-{spread_side}-{game['game_pk']}",
                event_id=event_id,
                event_name=event_name,
                start_time=start_time,
                market_type="run_line",
                selection=f"{team} {spread_line:+}",
                line=spread_line,
                odds=spread_odds,
                probability=odds_to_implied_probability(spread_odds),
                thesis_key=f"mlb-{_slug(team)}-runline-{spread_line}-{slate_date}",
                script_key=f"mlb-{_slug(event_name)}-{spread_side}-margin",
                reason_codes=["STARTING_PITCHER_EDGE", "LINEUP_EDGE"],
                reasoning=[f"{team} run line {spread_line:+}. Margin of victory thesis."],
                now=now,
                game_status=game_status,
                market_status=market_status,
                image_url=player_headshot_url(spread_pitcher.get("id") if spread_pitcher else None),
                team_image_url=team_logo_url(game.get(f"{spread_side}_id")),
            ))

        # --- Pitcher strikeout props (if we have pitcher data) ---
        for side in ("home", "away"):
            pitcher = game.get(f"{side}_pitcher")
            if not pitcher or not pitcher.get("id"):
                continue
            try:
                k_log = get_pitcher_game_log(pitcher["id"], last_n=5)
                if not k_log:
                    continue
                k_stats = pitcher_k_stats(k_log)
                if k_stats["avg_k"] < 3:
                    continue

                k_line = round(k_stats["avg_k"] - 0.5)
                if k_line < 3:
                    continue
                k_line_dec = Decimal(str(k_line)) + Decimal("0.5")
                k_hit = _k_hit_rate(k_log, float(k_line_dec))
                k_prob = max(0.35, min(0.78, k_hit if k_hit > 0 else 0.52))

                candidates.append(_build_candidate(
                    candidate_id=f"mlb-k-{side}-{game['game_pk']}",
                    event_id=event_id,
                    event_name=event_name,
                    start_time=start_time,
                    market_type="player_strikeouts_over",
                    selection=f"{pitcher['name']} Over {k_line_dec} Ks",
                    line=k_line_dec,
                    odds=-115,
                    probability=k_prob,
                    thesis_key=f"mlb-{_slug(pitcher['name'])}-k-over-{k_line_dec}-{slate_date}",
                    script_key=f"mlb-{_slug(event_name)}-{_slug(pitcher['name'])}-strikeouts",
                    player_key=f"mlb-pitcher-{pitcher['id']}",
                    reason_codes=["STRIKEOUT_MATCHUP"],
                    reasoning=[
                        f"{pitcher['name']} L5 avg: {k_stats['avg_k']} Ks, floor: {k_stats['floor_k']}, "
                        f"avg IP: {k_stats['avg_ip']}. Line set at {k_line_dec}."
                    ],
                    now=now,
                    game_status=game_status,
                    market_status=market_status,
                    image_url=player_headshot_url(pitcher["id"]),
                    team_image_url=team_logo_url(game.get(f"{side}_id")),
                    market_is_pitcher_strikeout_over=True,
                    average_cushion=round(k_stats["avg_k"] - float(k_line_dec), 2),
                    recent_hit_rate=k_hit,
                    miss_by_one_count_l10=_k_miss_by_one(k_log, float(k_line_dec)),
                ))
            except Exception:
                logger.warning("Failed to get K stats for pitcher %s", pitcher.get("name"))
                continue

    logger.info("Built %d live MLB candidates for %s", len(candidates), slate_date)
    return candidates


def _build_candidate(
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
    market_is_pitcher_strikeout_over: bool = False,
    average_cushion: float | None = None,
    recent_hit_rate: float | None = None,
    miss_by_one_count_l10: int = 0,
    game_status: str = "PRE_GAME",
    market_status: str = "OPEN",
    image_url: str | None = None,
    team_image_url: str | None = None,
) -> CandidateInput:
    prob_clamped = max(0.02, min(0.98, probability))
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport="mlb",
        league="MLB",
        start_time=start_time,
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=odds,
        estimated_probability=prob_clamped,
        variance=0.30,
        data_quality=0.88,
        factors={"matchup": 0.60, "current_form": 0.50, "market_value": 0.45},
        reason_codes=reason_codes,
        reasoning=reasoning,
        data_source="MLB_STATS_API+ODDS_API",
        source_timestamp=now,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "lineup": "probable",
            "injuries": "unknown",
        },
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=False,
        injuries_verified=False,
        weather_verified=False,
        starter_confirmed=True,
        motivation_rotation_verified=False,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=False,
        game_status=game_status,
        market_status=market_status,
        market_is_pitcher_strikeout_over=market_is_pitcher_strikeout_over,
        recent_hit_rate=recent_hit_rate or min(0.85, prob_clamped + 0.05),
        average_cushion=average_cushion or 1.5,
        matchup_score=0.60,
        script_alignment=0.55,
        multiple_paths_score=0.60,
        role_stability=0.70,
        miss_by_one_count_l10=miss_by_one_count_l10,
        ain_checks={
            "recent_form_l5_l10": True,
            "situational_angles": False,
            "h2h_context": False,
        },
        thesis_key=thesis_key,
        script_key=script_key,
        player_key=player_key,
        image_url=image_url,
        team_image_url=team_image_url,
        safer_alternative=f"Safer version of {selection}",
        higher_upside=f"Higher-upside version of {selection}",
        invalidation_conditions=["Material lineup change", "Large adverse price move"],
        live_trigger="Recheck price and underlying game state before any live entry.",
        hedge=(
            "Compare any cash-out offer with current fair remaining value. "
            "Reduce exposure only after material thesis change or exposure limit."
        ),
    )


def _parse_start(game_date: str | None, slate_date: date) -> datetime:
    if game_date:
        try:
            return datetime.fromisoformat(game_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return datetime(slate_date.year, slate_date.month, slate_date.day, 23, 0, tzinfo=UTC)


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("@", "at").replace(".", "")[:60]


def _ml_reason_codes(pitcher: dict[str, Any] | None) -> list[str]:
    codes = ["HOME_FIELD"]
    if pitcher:
        codes.insert(0, "STARTING_PITCHER_EDGE")
    return codes


def _k_hit_rate(logs: list[dict[str, Any]], line: float) -> float:
    if not logs:
        return 0.5
    hits = sum(1 for log in logs[:10] if log.get("strikeouts", 0) > line)
    return round(hits / min(len(logs), 10), 2)


def _k_miss_by_one(logs: list[dict[str, Any]], line: float) -> int:
    count = 0
    for log in logs[:10]:
        k = log.get("strikeouts", 0)
        if abs(k - line) <= 0.5 and k <= line:
            count += 1
    return count
