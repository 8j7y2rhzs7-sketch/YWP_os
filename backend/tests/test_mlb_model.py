from __future__ import annotations

import pytest

from app.services.mlb_model import pitcher_l5_summary, project_mlb_game


def _form(
    *,
    wins: int,
    run_diff: float,
    runs_for: float = 4.5,
    runs_against: float = 4.2,
) -> dict[str, object]:
    summary = {
        "wins": wins,
        "losses": 10 - wins,
        "win_pct": wins / 10,
        "run_diff_per_game": run_diff,
        "avg_runs_for": runs_for,
        "avg_runs_against": runs_against,
    }
    return {"verified": True, "l5": dict(summary), "l10": dict(summary)}


def test_projection_is_independent_and_probabilities_sum_to_one() -> None:
    projection = project_mlb_game(
        home_form=_form(wins=8, run_diff=1.8),
        away_form=_form(wins=3, run_diff=-1.1),
        home_pitcher_l5={"era": 2.4},
        away_pitcher_l5={"era": 5.1},
        home_bullpen={"verified": True, "heavy_usage": False},
        away_bullpen={"verified": True, "heavy_usage": True},
    )

    assert projection.home_win_probability > 0.5
    assert projection.home_win_probability + projection.away_win_probability == pytest.approx(1)
    assert "sportsbook price was not used" in projection.reasoning[-1]


def test_total_probability_moves_in_the_expected_direction() -> None:
    projection = project_mlb_game(
        home_form=_form(wins=5, run_diff=0.0),
        away_form=_form(wins=5, run_diff=0.0),
        home_pitcher_l5={"era": 4.2},
        away_pitcher_l5={"era": 4.2},
        home_bullpen={"verified": True, "heavy_usage": False},
        away_bullpen={"verified": True, "heavy_usage": False},
    )

    assert projection.total_probability(7.5, "over") > projection.total_probability(10.5, "over")
    assert projection.total_probability(7.5, "under") < projection.total_probability(10.5, "under")


def test_pitcher_l5_summary_uses_actual_workload() -> None:
    summary = pitcher_l5_summary(
        [
            {"innings_pitched": "6.0", "earned_runs": 2, "strikeouts": 7, "pitches": 94},
            {"innings_pitched": "5.2", "earned_runs": 1, "strikeouts": 6, "pitches": 88},
        ]
    )

    assert summary is not None
    assert summary["starts"] == 2
    assert summary["innings"] == 11.7
    assert summary["era"] == 2.31
    assert summary["strikeouts"] == 13
    assert summary["avg_pitches"] == 91.0
