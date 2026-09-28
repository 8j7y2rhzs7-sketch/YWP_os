from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine
from app.services.player_prop_research import (
    _hit_rate_probability,
    _raw_hit_rate,
    enrich_player_prop_candidates,
)
from app.services import player_prop_research
from unittest.mock import patch


def _modeled_prop(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="prop-aja-pts",
        event_id="event-wnba-1",
        event_name="Sun @ Dream",
        sport="wnba",
        league="WNBA",
        start_time=now,
        home_team="Atlanta Dream",
        away_team="Connecticut Sun",
        market_type="player_points_over",
        selection="A'ja Wilson Over 22.5 points",
        line=Decimal("22.5"),
        american_odds=-110,
        estimated_probability=0.62,
        probability_source="model",
        variance=0.34,
        data_quality=0.74,
        data_source="ESPN_PLAYER_PROP_MODEL",
        source_timestamp=now,
        source_status={
            "market": "confirmed",
            "schedule": "confirmed",
            "player_form": "confirmed",
            "injuries": "confirmed",
            "current_form": "confirmed",
        },
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        injuries_verified=True,
        starter_confirmed=True,
        lineup_confirmed=False,
        sport_specific_sweep_complete=True,
        independent_value_verified=True,
        motivation_rotation_verified=True,
        cushion_scale=4.0,
        role_stability=0.7,
        safer_alternative="Pick a different market on this sheet if this grade is SKIP.",
        thesis_key="wnba-aja-pts-over",
        script_key="wnba-aja-form",
    )
    base.update(overrides)
    return CandidateInput(**base)


def _from_values(values: list[float], *, line: float = 22.5, odds: int = -110) -> CandidateInput:
    hit = _raw_hit_rate(values, line, is_over=True)
    p = _hit_rate_probability(values, line, is_over=True)
    assert p is not None
    cushions = [v - line for v in values]
    avg_c = sum(cushions) / len(cushions)
    miss1 = sum(1 for c in cushions if -1.0 <= c < 0)
    return _modeled_prop(
        estimated_probability=p,
        american_odds=odds,
        recent_hit_rate=hit,
        average_cushion=round(avg_c, 3),
        miss_by_one_count_l10=int(miss1),
        matchup_score=p,
        script_alignment=min(0.95, max(0.05, 0.5 + avg_c / 8.0)),
        multiple_paths_score=min(1.0, 0.45 + hit * 0.5),
    )


def test_thin_close_basketball_prop_hard_skips_even_with_safer_alternative() -> None:
    # Classic near-miss profile: coin-flip hits, almost no cushion.
    candidate = _from_values([23, 22, 24, 21, 23, 22, 25, 22, 23, 21], odds=-115)
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert (
        "PROP_THIN_CLOSE_GATE" in evaluation.reason_codes
        or "PROP_CUSHION_GATE" in evaluation.reason_codes
        or "NO_CLEAN_EDGE" in evaluation.reason_codes
    )


def test_low_cushion_hard_skips_even_when_edge_exists() -> None:
    # Hits often but barely clears — the close losses the user wants blocked.
    candidate = _modeled_prop(
        estimated_probability=0.62,
        american_odds=-105,
        recent_hit_rate=0.7,
        average_cushion=0.35,
        miss_by_one_count_l10=1,
        matchup_score=0.62,
        script_alignment=0.55,
        multiple_paths_score=0.8,
    )
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "PROP_CUSHION_GATE" in evaluation.reason_codes


def test_strong_form_prop_can_play_instead_of_outlier_review() -> None:
    candidate = _from_values([28, 27, 26, 30, 25, 29, 24, 31, 27, 26], odds=-110)
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision in {"PLAY", "LEAN"}
    assert "OUTLIER_EDGE_REVIEW" not in evaluation.reason_codes
    assert "PROP_THIN_CLOSE_GATE" not in evaluation.reason_codes
    assert "PROP_CUSHION_GATE" not in evaluation.reason_codes


def test_enrich_maps_points_rebounds_combo() -> None:
    games = [
        {"points": 20, "totalRebounds": 8, "assists": 4, "game_date": f"2026-09-{d:02d}"}
        for d in range(16, 6, -1)
    ]
    candidate = _modeled_prop(
        market_type="player_pr_over",
        selection="A'ja Wilson Over 26.5 pts+reb",
        line=Decimal("26.5"),
        probability_source="market_implied",
        data_source="THE_ODDS_API_BOARD",
        data_quality=0.35,
        missing_fields=["independent_model_projection"],
        current_form_verified=False,
        l5_l10_verified=False,
        sport_specific_sweep_complete=False,
        independent_value_verified=False,
    )
    with (
        patch.object(player_prop_research.espn_provider, "resolve_team_id", return_value="1"),
        patch.object(
            player_prop_research.espn_provider,
            "resolve_athlete_id",
            return_value={"id": "99", "name": "A'ja Wilson"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_athlete_gamelog",
            return_value={"verified": True, "games": games, "source_url": "x"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_league_injuries",
            return_value={"verified": True, "by_team": {}},
        ),
    ):
        enriched = enrich_player_prop_candidates([candidate])[0]
    assert enriched.probability_source == "model"
    assert enriched.average_cushion is not None


def test_nfl_pass_yards_thin_cushion_hard_skips() -> None:
    from app.services.player_prop_research import min_prop_cushion

    candidate = _modeled_prop(
        sport="nfl",
        league="NFL",
        market_type="player_pass_yds_over",
        selection="Patrick Mahomes Over 275.5 pass yards",
        line=Decimal("275.5"),
        cushion_scale=25.0,
        average_cushion=3.0,
        recent_hit_rate=0.7,
        miss_by_one_count_l10=0,
        estimated_probability=0.62,
        matchup_score=0.62,
        script_alignment=0.6,
        multiple_paths_score=0.8,
    )
    assert min_prop_cushion(candidate) >= 5.0
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "PROP_CUSHION_GATE" in evaluation.reason_codes


def test_enrich_nfl_pass_yards() -> None:
    from datetime import date

    games = [
        {
            "passingYards": 310,
            "rushingYards": 20,
            "receivingYards": 0,
            "game_date": f"2026-09-{d:02d}",
        }
        for d in range(16, 6, -1)
    ]
    candidate = _modeled_prop(
        sport="nfl",
        league="NFL",
        market_type="player_pass_yds_over",
        selection="Patrick Mahomes Over 275.5 pass yards",
        line=Decimal("275.5"),
        probability_source="market_implied",
        data_source="THE_ODDS_API_BOARD",
        data_quality=0.35,
        missing_fields=["independent_model_projection"],
        current_form_verified=False,
        l5_l10_verified=False,
        sport_specific_sweep_complete=False,
        independent_value_verified=False,
        home_team="Kansas City Chiefs",
        away_team="Las Vegas Raiders",
    )
    with (
        patch.object(player_prop_research.espn_provider, "resolve_team_id", return_value="12"),
        patch.object(
            player_prop_research.espn_provider,
            "resolve_athlete_id",
            return_value={"id": "3139477", "name": "Patrick Mahomes"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_athlete_gamelog",
            return_value={"verified": True, "games": games, "source_url": "x"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_league_injuries",
            return_value={"verified": True, "by_team": {}},
        ),
    ):
        enriched = enrich_player_prop_candidates([candidate], slate_date=date(2026, 9, 17))[0]
    assert enriched.probability_source == "model"
    assert enriched.cushion_scale == 25.0


def test_mlb_thin_cushion_hard_skips() -> None:
    candidate = _modeled_prop(
        sport="mlb",
        league="MLB",
        market_type="player_strikeouts_over",
        selection="Ace Pitcher Over 5.5 strikeouts",
        line=Decimal("5.5"),
        estimated_probability=0.58,
        average_cushion=0.3,
        recent_hit_rate=0.6,
        miss_by_one_count_l10=2,
        cushion_scale=3.0,
        data_source="MLB_STATS_API+THE_ODDS_API",
        market_is_pitcher_strikeout_over=True,
        k_duration_verified=True,
        normal_workload_confirmed=True,
        weather_verified=True,
        lineup_confirmed=True,
        injuries_verified=True,
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        independent_value_verified=True,
        motivation_rotation_verified=True,
        starter_confirmed=True,
    )
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "PROP_CUSHION_GATE" in evaluation.reason_codes
