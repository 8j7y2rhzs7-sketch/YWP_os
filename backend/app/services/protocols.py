from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ProtocolRun
from app.schemas import CandidateInput

CURRENT_PROTOCOL = {
    "name": "YWP OS Canonical Sports Protocol",
    "version": "2026.09.03",
    "status": "canonical",
    "constitutional_laws": [
        "Capital preservation first",
        "Expected value over raw win rate",
        "Probability before prediction; no guarantees",
        "Never chase losses",
        "Adapt continuously without overfitting",
        "Separate outcome from process",
        "Every decision must be explainable",
    ],
    "decision_pipeline": [
        "raw_information",
        "validation",
        "context",
        "matchup",
        "market",
        "risk",
        "expected_value",
        "decision",
        "review",
        "learning",
    ],
    "global_required_checks": [
        "schedule_and_identity",
        "official_source_and_freshness",
        "confirmed_probable_unknown_labels",
        "l5_l10_actual_form",
        "matchup_today_not_brand_strength",
        "game_script",
        "motivation_rest_rotation",
        "lineup_injury_availability",
        "home_away_and_travel",
        "opening_current_price_and_line_movement",
        "implied_probability_edge_and_ev",
        "cushion_and_vision",
        "miss_by_one_risk",
        "variance_and_multiple_paths",
        "safer_alternative",
        "quick_cash_chain_reaction_live_path",
        "correlation_and_cross_ticket_thesis_exposure",
        "bankroll_fit",
        "weakest_leg_elimination",
        "lock_check_before_placement",
    ],
    "ain_seven_point_sweep": [
        "matchup_edge",
        "recent_form_l5_l10",
        "situational_angles",
        "injuries_and_rest",
        "pace_or_tempo",
        "h2h_context",
        "market_value",
    ],
    "strict_mode": {
        "mlb": [
            "confirmed_schedule_and_probable_starters",
            "starting_pitcher_matchup_and_splits",
            "pitcher_l5_l10_and_expected_duration",
            "bullpen_availability_last_three_days",
            "offensive_form_l5_l10_and_platoon_matchup",
            "confirmed_lineups_injuries_and_news",
            "home_away_park_weather_and_umpire",
            "f3_f5_full_game_and_team_total_alternatives",
            "opening_current_line_and_market_value",
            "variance_and_elimination_test",
        ],
        "wnba": [
            "all_players_scanned_one_by_one",
            "actual_l5_l10_logs_and_hit_rate",
            "minutes_role_usage_rotation_and_limits",
            "injuries_rest_and_confirmed_availability",
            "opponent_defense_matchup_and_scheme",
            "pace_game_script_and_blowout_risk",
            "home_away_h2h_and_recent_form",
            "prop_cushion_multiple_paths_and_alt_line",
            "market_value_and_line_movement",
            "weakest_leg_elimination",
        ],
        "nba": [
            "all_players_scanned_one_by_one",
            "actual_l5_l10_logs_minutes_role_usage_and_rotation",
            "injuries_rest_travel_and_confirmed_availability",
            "opponent_defense_matchup_pace_and_scheme",
            "game_script_blowout_risk_and_fourth_quarter_minutes",
            "prop_cushion_multiple_paths_and_alt_line",
            "opening_current_price_and_weakest_leg_elimination",
        ],
        "soccer": [
            "schedule_competition_and_leg_verified",
            "l5_l10_form_xg_xga_when_available",
            "lineups_injuries_rest_travel_and_motivation",
            "home_away_tactical_and_set_piece_matchup",
            "team_total_btts_total_and_double_chance_alternatives",
            "opening_current_price_and_market_value",
            "90_minute_vs_to_qualify_market",
            "aggregate_draw_extra_time_and_penalty_trap",
            "variance_and_weakest_leg_elimination",
        ],
        "nfl": [
            "schedule_and_starting_units_verified",
            "offense_defense_pressure_and_red_zone",
            "injuries_rest_travel_and_rotation",
            "recent_form_home_away_and_game_script",
            "weather_surface_and_market_movement",
            "variance_and_weakest_leg_elimination",
        ],
        "ncaaf": [
            "schedule_depth_chart_and_starting_units_verified",
            "offense_defense_trenches_pressure_and_explosiveness",
            "injuries_rest_travel_motivation_and_rotation",
            "recent_form_home_away_strength_of_schedule_and_script",
            "weather_surface_pace_special_teams_and_market_movement",
            "variance_blowout_backdoor_cover_and_weakest_leg_elimination",
        ],
        "kbo": [
            "confirmed_schedule_probable_starters_and_foreign_player_status",
            "starting_pitcher_form_splits_expected_duration_and_pitch_count",
            "bullpen_availability_last_three_days_and_travel",
            "offensive_l5_l10_platoon_form_lineups_and_injuries",
            "home_away_park_weather_and_market_movement",
            "f5_full_game_team_total_and_variance_elimination_test",
        ],
        "nhl": [
            "schedule_and_starting_goalies_verified",
            "injuries_rest_travel_and_line_combinations",
            "recent_form_home_away_and_special_teams",
            "pace_expected_goals_proxy_and_game_script",
            "market_value_and_weakest_leg_elimination",
        ],
    },
    "ticket_system": {
        "official_daily_card": (
            "Same canonical card for every user; bankroll controls remain personal."
        ),
        "max_bet": "One strongest qualified play; never invent a second lock.",
        "elite_two": "Two strongest diversified plays when both qualify.",
        "core_cards": "Three-, four-, and five-pick cards only from qualified plays.",
        "abc": {
            "A": "Best available picks",
            "B": "Best picks using different players/theses than A",
            "C": "Best diversified picks selected from A and B",
        },
        "fortress": "Best-of-best, low hidden-risk positions across categories.",
        "handicap": "Largest measurable cushion/handicap edges.",
        "no_stress": "Lowest variance, strongest cushion, explicit stress score.",
        "scripted": "Plays whose expected game scripts align independently.",
        "quick_cash": (
            "Early-settlement or early-game edges tracked separately from full-game risk."
        ),
        "chain_reaction": (
            "Conditional paths with an explicit trigger, downstream effect, and logged result."
        ),
        "ghostt": (
            "Higher-upside card built from real mispricing, not merely more legs or underdogs."
        ),
        "comeback": "Best current qualified plays; never a chase-loss card.",
    },
    "miss_by_one_protocol": {
        "pre_ticket": [
            "Calculate miss-by-one frequency, average cushion, role stability, variance, "
            "and number of cashing paths.",
            "Flag the likeliest ticket-killer and offer a safer line or remove it.",
            "Do not raise a line for payout without separate hit-rate and cushion approval.",
            "Quarantine critical miss-by-one legs from Cash Builder and Fortress cards.",
        ],
        "post_result": [
            "Store actual value, line, signed miss distance, whether it killed the ticket, "
            "and whether it was the final losing leg.",
            "Count slips lost separately from unique failed theses.",
            "Segment recurrence by sport, market, player, line, role, script, and card type.",
            "Treat a near miss as variance or process only after checking cushion, role, "
            "timing, and price.",
        ],
    },
    "live_cashout_protocol": {
        "before_action": [
            "Refresh score, clock or inning, market, line, price, availability, and source time.",
            "Re-evaluate the original thesis, invalidation conditions, current fair probability, "
            "remaining payout, and bankroll exposure.",
            "Treat a sportsbook cash-out offer as a new price; compare it with fair remaining "
            "value instead of reacting to fear or sunk cost.",
        ],
        "allowed_actions": [
            "HOLD when the verified thesis is intact and the offer materially underprices fair "
            "remaining value.",
            "CASH_OUT when material new information breaks the thesis and the offer is a "
            "reasonable exit relative to current fair value.",
            "PARTIAL_HEDGE only when the opposing protected market has independent value or a "
            "bankroll/exposure limit requires reduction.",
            "SKIP_LIVE_ADD when the new live price has no clean edge; never add merely to rescue "
            "a pregame position.",
        ],
        "hard_blocks": [
            "Never chase, double down, or create a second correlated loss path.",
            "Never cash out solely because the wager is temporarily losing or hold solely to "
            "recover the original stake.",
            "Never act on a stale screen, unavailable market, guessed probability, or unverified "
            "injury and lineup change.",
        ],
        "after_action": [
            "Record HOLD, CASH_OUT, PARTIAL_HEDGE, NOT_OFFERED, or NOT_APPLICABLE; the offer, "
            "time, reason, live-trigger result, and final profit or loss.",
            "Grade the live/cash-out process separately from whether the underlying ticket won.",
        ],
    },
    "adaptive_learning": {
        "log_before": [
            "inputs_and_source_timestamps",
            "model_and_protocol_versions",
            "probability_edge_ev_confidence_yis_vision",
            "reason_codes_supporting_factors_primary_risks",
            "assumptions_safer_alternative_live_trigger_and_invalidation",
        ],
        "log_after": [
            "outcome_profit_loss_closing_line_and_clv",
            "actual_value_miss_distance_and_ticket_killer_status",
            "process_grade_variance_grade_and_process_outcome_class",
            "assumptions_that_held_or_failed_and_unexpected_events",
            "root_cause_error_category_and_lesson",
            "quick_cash_chain_reaction_live_trigger_and_cashout_performance",
        ],
        "guardrails": [
            "Never update from one result",
            "Require minimum sample size and repeated pattern",
            "Isolate feature contribution",
            "Use small bounded weight changes",
            "Reduce confidence when high-rated picks are miscalibrated",
            "Require human approval for material production changes",
            "Version every weight and support rollback",
        ],
    },
    "trusted_source_research_protocol": {
        "rule": (
            "Strict Mode may auto-verify a research field only from the certified source list. "
            "Searchers query those sources before a slate is labeled PARTIAL."
        ),
        "searchers": [
            "mlb_schedule_officials_weather_venue",
            "mlb_live_feed_lineups_weather_park",
            "mlb_boxscore_umpire_crew",
            "mlb_roster_availability",
            "mlb_bullpen_workload",
            "espn_scoreboard_schedule_and_venue",
            "espn_team_schedule_l5_l10_form",
            "espn_league_injury_report",
            "open_meteo_backup_weather",
            "odds_api_current_price_and_multi_book_consensus",
            "ywp_mlb_independent_model",
            "ywp_multi_sport_independent_model",
        ],
        "never_trusted": [
            "Random blogs or tip pages",
            "Unauthenticated HTML scrapes of sportsbook sites",
            "Social media rumor without an official confirmation",
            "Manufactured or implied-only probabilities used as YWP projections",
        ],
    },
    "superseded_or_removed": [
        "Any older workflow is superseded by the newest canonical version.",
        "Incorrect ABC interpretations are removed; A/B/C use the definitions above.",
        "Heavy juice is not evidence that a leg is safe.",
        "A prior high-scoring game is not a projection by itself.",
        "Risky cards are not created by simply lengthening safe cards or stacking underdogs.",
        "Unverified schedules, players, lines, statistics, or injury statuses must not be guessed.",
        "Do not force two picks when only one qualifies.",
        "Do not treat completed non-causal legs as the reason a dead ticket lost.",
    ],
}


def _check(
    key: str,
    label: str,
    statuses: list[bool | None],
    *,
    required: bool = True,
) -> dict[str, Any]:
    if not statuses:
        status = "WARN"
        detail = "No candidates supplied this check."
    elif any(value is False for value in statuses):
        status = "FAIL" if required else "WARN"
        detail = "At least one candidate failed this check."
    elif any(value is None for value in statuses):
        status = "WARN"
        detail = "At least one candidate is unknown/unverified."
    else:
        status = "PASS"
        detail = "All candidates passed."
    return {"key": key, "label": label, "status": status, "detail": detail}


def run_protocol_health_check(
    db: Session,
    *,
    analysis_id: str,
    user_id: str | None,
    sport: str,
    candidates: list[CandidateInput],
) -> ProtocolRun:
    now = datetime.now(UTC)
    candidate_ids = [candidate.candidate_id for candidate in candidates]
    freshness_limit = (
        120 if any(candidate.market_period == "live" for candidate in candidates) else 21600
    )

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "key": "schedule_and_identity",
            "label": "Schedule, sport, event, and candidate identity",
            "status": "PASS"
            if len(candidate_ids) == len(set(candidate_ids))
            and all(candidate.sport.lower() == sport.lower() for candidate in candidates)
            else "FAIL",
            "detail": (
                "Candidate IDs must be unique and every candidate must match the slate sport."
            ),
        }
    )
    checks.append(
        _check(
            "schedule_verified",
            "Official schedule verified",
            [candidate.schedule_verified for candidate in candidates],
        )
    )
    checks.append(
        _check(
            "source_freshness",
            "Source freshness",
            [
                max(0, (now - candidate.source_timestamp).total_seconds()) <= freshness_limit
                for candidate in candidates
            ],
        )
    )
    checks.append(
        _check(
            "confirmed_probable_unknown",
            "Source confirmation labels",
            [
                None
                if not candidate.source_status
                else all(value != "unknown" for value in candidate.source_status.values())
                for candidate in candidates
            ],
            required=False,
        )
    )

    ain_definitions = [
        ("matchup_edge", "AIN 1 — Matchup edge"),
        ("recent_form_l5_l10", "AIN 2 — Actual recent form L5/L10"),
        ("situational_angles", "AIN 3 — Situational angles"),
        ("injuries_and_rest", "AIN 4 — Injuries and rest"),
        ("pace_or_tempo", "AIN 5 — Pace/tempo or game script"),
        ("h2h_context", "AIN 6 — H2H context"),
        ("market_value", "AIN 7 — Market value"),
    ]
    # AIN 1 / AIN 5 check that matchup and script inputs were computed in-range.
    # Do NOT require score >= 0.5 here: two-sided slates correctly include the weak
    # side of each market (and some underdog PLAYs) below 0.5. Strength belongs in
    # the decision engine, not the slate health sweep — otherwise every live MLB
    # board falsely FAILS the final protocol check.
    inferred: dict[str, list[bool | None]] = {
        "matchup_edge": [
            0.0 <= float(candidate.matchup_score) <= 1.0 for candidate in candidates
        ],
        "recent_form_l5_l10": [
            candidate.ain_checks.get("recent_form_l5_l10", candidate.current_form_verified)
            for candidate in candidates
        ],
        "situational_angles": [
            candidate.ain_checks.get("situational_angles") for candidate in candidates
        ],
        "injuries_and_rest": [candidate.injuries_verified for candidate in candidates],
        "pace_or_tempo": [
            candidate.script_alignment is not None
            and 0.0 <= float(candidate.script_alignment) <= 1.0
            for candidate in candidates
        ],
        "h2h_context": [candidate.ain_checks.get("h2h_context") for candidate in candidates],
        "market_value": [
            candidate.estimated_probability > 0 and candidate.american_odds != 0
            for candidate in candidates
        ],
    }
    for key, label in ain_definitions:
        checks.append(_check(key, label, inferred[key], required=key != "h2h_context"))

    checks.extend(
        [
            _check(
                "universe_scan",
                "Complete slate/player universe scan",
                [candidate.universe_scan_complete for candidate in candidates],
            ),
            _check(
                "actual_l5_l10",
                "Actual L5/L10 logs verified",
                [candidate.l5_l10_verified for candidate in candidates],
            ),
            _check(
                "lineup_injuries_starters",
                "Lineups, injuries, starters, and role",
                [
                    candidate.lineup_confirmed
                    and candidate.injuries_verified
                    and candidate.starter_confirmed
                    for candidate in candidates
                ],
            ),
            _check(
                "motivation_rotation",
                "Motivation, rest, minutes, workload, and rotation",
                [candidate.motivation_rotation_verified for candidate in candidates],
            ),
            _check(
                "home_away",
                "Home/away, venue, and travel context",
                [candidate.home_away_verified for candidate in candidates],
            ),
            _check(
                "market_movement",
                "Opening/current line and market movement",
                [candidate.market_movement_verified for candidate in candidates],
            ),
            _check(
                "sport_specific",
                "Sport-specific strict-mode sweep",
                [candidate.sport_specific_sweep_complete for candidate in candidates],
            ),
            _check(
                "cushion_vision",
                "Cushion and Vision inputs",
                [
                    candidate.recent_hit_rate is not None and candidate.average_cushion is not None
                    for candidate in candidates
                ],
                required=False,
            ),
            _check(
                "miss_by_one",
                "Miss-by-1 inputs",
                [
                    candidate.miss_by_one_count_l10 is not None
                    and candidate.miss_by_one_count_l10 >= 0
                    for candidate in candidates
                ],
            ),
            _check(
                "multiple_paths",
                "Multiple independent cashing paths",
                [
                    candidate.multiple_paths_score is not None
                    and candidate.multiple_paths_score >= 0.35
                    for candidate in candidates
                ],
            ),
            _check(
                "pre_game_only",
                "Game status is PRE_GAME",
                [candidate.game_status == "PRE_GAME" for candidate in candidates],
            ),
            _check(
                "market_open",
                "Market status is OPEN",
                [candidate.market_status == "OPEN" for candidate in candidates],
            ),
        ]
    )

    failed = [item for item in checks if item["status"] == "FAIL"]
    warned = [item for item in checks if item["status"] == "WARN"]
    status = "FAILED" if failed else "WARNING" if warned else "DOUBLE_CLEARED"
    warnings = [item["label"] + ": " + item["detail"] for item in [*failed, *warned]]
    record = ProtocolRun(
        analysis_id=analysis_id,
        user_id=user_id,
        protocol_version=settings.protocol_version,
        sport=sport.lower(),
        run_type="FULL_HEALTH_CHECK_AIN_STRICT",
        status=status,
        checks=checks,
        warnings=warnings,
        superseded_rules_ignored=CURRENT_PROTOCOL["superseded_or_removed"],
    )
    db.add(record)
    return record
