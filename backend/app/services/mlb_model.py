from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _logistic(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _normal_cdf(value: float, mean: float, standard_deviation: float) -> float:
    z = (value - mean) / (standard_deviation * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


def _number(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _baseball_innings(value: object) -> float:
    """Convert MLB's outs notation (5.2 = 5 2/3 innings) to a real number."""
    text = str(value or "0")
    whole_text, separator, outs_text = text.partition(".")
    try:
        whole = int(whole_text)
        outs = int(outs_text or 0) if separator else 0
    except ValueError:
        return _number(value, 0.0)
    if outs not in {0, 1, 2}:
        return _number(value, 0.0)
    return whole + outs / 3


@dataclass(frozen=True, slots=True)
class MLBProjection:
    home_win_probability: float
    away_win_probability: float
    expected_total_runs: float
    expected_home_margin: float
    model_quality: float
    reasoning: tuple[str, ...]

    def moneyline_probability(self, side: Literal["home", "away"]) -> float:
        return self.home_win_probability if side == "home" else self.away_win_probability

    def total_probability(self, line: float, direction: Literal["over", "under"]) -> float:
        # Wider sigma + shrink toward 50% so independent projections cannot print
        # fake 90%+ certainty that the board ranks #1 then ticket gates strip.
        over = 1 - _normal_cdf(line, self.expected_total_runs, 3.85)
        probability = over if direction == "over" else 1 - over
        shrunk = 0.5 + (probability - 0.5) * 0.42
        return _clamp(shrunk, 0.18, 0.82)

    def spread_probability(self, side: Literal["home", "away"], line: float) -> float:
        side_margin = self.expected_home_margin if side == "home" else -self.expected_home_margin
        cover_probability = 1 - _normal_cdf(-line, side_margin, 3.85)
        shrunk = 0.5 + (cover_probability - 0.5) * 0.42
        return _clamp(shrunk, 0.18, 0.82)


def project_mlb_game(
    *,
    home_form: dict[str, Any],
    away_form: dict[str, Any],
    home_pitcher_l5: dict[str, Any] | None,
    away_pitcher_l5: dict[str, Any] | None,
    home_bullpen: dict[str, Any],
    away_bullpen: dict[str, Any],
) -> MLBProjection:
    """Transparent pregame MLB projection using only official performance inputs.

    This is deliberately independent from the sportsbook price. The market line is used later
    only to calculate value and expected value.
    """
    home_l10 = home_form.get("l10", {})
    away_l10 = away_form.get("l10", {})
    home_l5 = home_form.get("l5", {})
    away_l5 = away_form.get("l5", {})

    home_win = 0.65 * _number(home_l10.get("win_pct"), 0.5) + 0.35 * _number(
        home_l5.get("win_pct"), 0.5
    )
    away_win = 0.65 * _number(away_l10.get("win_pct"), 0.5) + 0.35 * _number(
        away_l5.get("win_pct"), 0.5
    )
    form_edge = home_win - away_win

    home_run_diff = 0.65 * _number(home_l10.get("run_diff_per_game"), 0.0) + 0.35 * _number(
        home_l5.get("run_diff_per_game"), 0.0
    )
    away_run_diff = 0.65 * _number(away_l10.get("run_diff_per_game"), 0.0) + 0.35 * _number(
        away_l5.get("run_diff_per_game"), 0.0
    )
    run_edge = home_run_diff - away_run_diff

    home_era = _number((home_pitcher_l5 or {}).get("era"), 4.20)
    away_era = _number((away_pitcher_l5 or {}).get("era"), 4.20)
    starter_edge = away_era - home_era

    bullpen_edge = 0.0
    if home_bullpen.get("heavy_usage"):
        bullpen_edge -= 0.18
    if away_bullpen.get("heavy_usage"):
        bullpen_edge += 0.18

    # Home field, blended recent form, scoring margin, starter form, and bullpen workload.
    home_logit = 0.13 + 1.35 * form_edge + 0.20 * run_edge + 0.15 * starter_edge + bullpen_edge
    home_probability = _clamp(_logistic(home_logit), 0.20, 0.80)

    home_runs_for = _number(home_l10.get("avg_runs_for"), 4.4)
    away_runs_for = _number(away_l10.get("avg_runs_for"), 4.4)
    home_runs_allowed = _number(home_l10.get("avg_runs_against"), 4.4)
    away_runs_allowed = _number(away_l10.get("avg_runs_against"), 4.4)
    expected_total = (home_runs_for + away_runs_for + home_runs_allowed + away_runs_allowed) / 2
    expected_total += ((_clamp(home_era, 1.5, 8.0) + _clamp(away_era, 1.5, 8.0)) / 2 - 4.2) * 0.45
    if home_bullpen.get("heavy_usage"):
        expected_total += 0.25
    if away_bullpen.get("heavy_usage"):
        expected_total += 0.25
    expected_total = _clamp(expected_total, 5.5, 11.5)

    expected_home_margin = _clamp(
        0.35 + 0.80 * run_edge + 0.45 * starter_edge + 0.55 * bullpen_edge,
        -5.0,
        5.0,
    )

    verified_groups = sum(
        [
            bool(home_form.get("verified")),
            bool(away_form.get("verified")),
            bool(home_pitcher_l5),
            bool(away_pitcher_l5),
            bool(home_bullpen.get("verified")),
            bool(away_bullpen.get("verified")),
        ]
    )
    quality = 0.55 + 0.065 * verified_groups

    reasoning = (
        f"Official MLB L10 form: home {home_l10.get('wins', 0)}-{home_l10.get('losses', 0)}, "
        f"away {away_l10.get('wins', 0)}-{away_l10.get('losses', 0)}.",
        f"Official MLB L10 run differential/game: home {home_run_diff:+.2f}, "
        f"away {away_run_diff:+.2f}.",
        f"Starting-pitcher L5 ERA input: home {home_era:.2f}, away {away_era:.2f}.",
        f"Independent YWP expected total: {expected_total:.2f}; sportsbook price was not used "
        "to create the projection.",
    )
    return MLBProjection(
        home_win_probability=round(home_probability, 4),
        away_win_probability=round(1 - home_probability, 4),
        expected_total_runs=round(expected_total, 2),
        expected_home_margin=round(expected_home_margin, 2),
        model_quality=round(_clamp(quality, 0.55, 0.94), 4),
        reasoning=reasoning,
    )


def pitcher_l5_summary(logs: list[dict[str, Any]]) -> dict[str, Any] | None:
    sample = logs[:5]
    if not sample:
        return None
    innings = sum(_baseball_innings(item.get("innings_pitched")) for item in sample)
    earned_runs = sum(_number(item.get("earned_runs"), 0.0) for item in sample)
    strikeouts = sum(int(item.get("strikeouts", 0) or 0) for item in sample)
    pitches = sum(int(item.get("pitches", 0) or 0) for item in sample)
    era = 9 * earned_runs / innings if innings else 9.99
    return {
        "starts": len(sample),
        "innings": round(innings, 1),
        "era": round(era, 2),
        "strikeouts": strikeouts,
        "avg_strikeouts": round(strikeouts / len(sample), 2),
        "avg_pitches": round(pitches / len(sample), 1),
    }
