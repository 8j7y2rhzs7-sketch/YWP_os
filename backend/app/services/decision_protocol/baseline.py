"""Canonical rules for the 2026.10.04 baseline. The prior version stays named."""

from app.services.decision_protocol.states import DecisionState

PROTOCOL_VERSION = "2026.10.04"
PRIOR_PROTOCOL_VERSION = "2026.09.03"
PROTOCOL_STATUS = "implementation_baseline"

PRINCIPLES: tuple[str, ...] = (
    "High probability over high payout.",
    "No bet is a valid decision.",
    "Every parlay leg must qualify as a standalone play.",
    "Investigate the game before investigating individual player props.",
    "Use actual recent results and the exact market being considered.",
    "Verify player identity, team, schedule, injuries, lineup, and starter where applicable.",
    "Never confuse favorable odds with a likely winner.",
    "Learn from wins, losses, near misses, and incorrect assumptions.",
    "Keep the official decision process consistent across users.",
    "Never change an established protocol rule silently.",
)

STAGES: tuple[str, ...] = (
    "input_validation",
    "full_game_investigation",
    "exact_market_analysis",
    "cushion_and_reliability",
    "ain_failure_mode_sweep",
    "qualification_and_ranking",
    "ticket_construction",
)

# Sport checks that must be present before a PLAY. Absence is HOLD, not a guess.
SPORT_REQUIRED_CHECKS: dict[str, tuple[str, ...]] = {
    "mlb": (
        "starting_pitcher",
        "lineup",
        "pitcher_workload",
        "opponent_profile",
        "bullpen",
        "weather_when_material",
    ),
    "nfl": (
        "game_script",
        "matchup",
        "participation",
        "opportunity",
        "weather",
        "blowout_risk",
    ),
    "ncaaf": (
        "game_script",
        "matchup",
        "participation",
        "opportunity",
        "weather",
        "blowout_risk",
    ),
    "wnba": (
        "minutes",
        "usage",
        "matchup",
        "game_script",
        "injuries",
        "recent_results",
    ),
    "nba": (
        "minutes",
        "usage",
        "matchup",
        "game_script",
        "injuries",
        "recent_results",
    ),
    "soccer": (
        "settlement_rules",
        "draw_treatment",
        "knockout_state",
    ),
}

LEARNING_CATEGORIES: tuple[str, ...] = (
    "correct_prediction_correct_reasoning",
    "correct_result_flawed_reasoning",
    "incorrect_prediction_sound_reasoning",
    "incorrect_prediction_flawed_reasoning",
    "near_miss",
    "bad_input_or_stale_information",
    "market_or_settlement_misunderstanding",
    "ticket_correlation_or_construction_failure",
)


def baseline_manifest() -> dict[str, object]:
    """Describe the baseline without switching the live sports protocol."""
    return {
        "name": "YWP OS Decision Protocol",
        "version": PROTOCOL_VERSION,
        "prior_version": PRIOR_PROTOCOL_VERSION,
        "status": PROTOCOL_STATUS,
        "live_sports_protocol_unchanged": True,
        "rollback_to": PRIOR_PROTOCOL_VERSION,
        "principles": list(PRINCIPLES),
        "stages": list(STAGES),
        "states": [state.value for state in DecisionState],
        "official_max_legs": 2,
        "learning_categories": list(LEARNING_CATEGORIES),
        "sport_required_checks": {key: list(value) for key, value in SPORT_REQUIRED_CHECKS.items()},
    }
