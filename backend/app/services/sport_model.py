"""Independent non-MLB projections from official ESPN facts.

Never uses sportsbook implied probability as the model output. Market price is
only used later for edge comparison against this independent estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SportProjection:
    win_probability: float
    expected_total: float
    home_strength: float
    away_strength: float
    quality: float
    notes: list[str]


def project_matchup(
    *,
    home_form: dict[str, Any],
    away_form: dict[str, Any],
    market_type: str,
    selection: str,
    line: float | None = None,
    home_out: int = 0,
    away_out: int = 0,
    is_home_selection: bool | None = None,
) -> SportProjection:
    home_l10 = home_form.get("l10") or {}
    away_l10 = away_form.get("l10") or {}
    home_l5 = home_form.get("l5") or {}
    away_l5 = away_form.get("l5") or {}

    home_wp = _blend(home_l5.get("win_pct"), home_l10.get("win_pct"), 0.55)
    away_wp = _blend(away_l5.get("win_pct"), away_l10.get("win_pct"), 0.55)
    # Home court/field bump from verified home/away context.
    home_wp = min(0.92, max(0.08, home_wp + 0.03))
    away_wp = min(0.92, max(0.08, away_wp - 0.01))

    # Injury pressure — each confirmed OUT trims strength slightly.
    home_wp = min(0.92, max(0.08, home_wp - 0.015 * max(0, home_out)))
    away_wp = min(0.92, max(0.08, away_wp - 0.015 * max(0, away_out)))

    # Normalize to a two-team matchup probability.
    total = home_wp + away_wp
    home_prob = home_wp / total if total else 0.5
    away_prob = 1.0 - home_prob

    home_for = float(home_l10.get("avg_for") or 0.0)
    home_against = float(home_l10.get("avg_against") or 0.0)
    away_for = float(away_l10.get("avg_for") or 0.0)
    away_against = float(away_l10.get("avg_against") or 0.0)
    if home_for and away_for:
        expected_total = (home_for + away_for + home_against + away_against) / 2.0
    else:
        expected_total = 0.0

    notes = [
        f"Home L10 win% {home_l10.get('win_pct', 0.5):.3f}",
        f"Away L10 win% {away_l10.get('win_pct', 0.5):.3f}",
        f"Expected total {expected_total:.2f}" if expected_total else "Expected total unavailable",
    ]
    if home_out or away_out:
        notes.append(f"Injury outs home/away: {home_out}/{away_out}")

    market = (market_type or "").lower()
    selection_l = (selection or "").lower()
    if "total" in market or "over" in selection_l or "under" in selection_l:
        if line is None or not expected_total:
            prob = 0.5
        else:
            # Soft logistic around the independent total.
            gap = expected_total - float(line)
            # ~1.5 scoring units → meaningful edge.
            base = 0.5 + max(-0.22, min(0.22, gap / 12.0))
            if "under" in selection_l or "under" in market:
                prob = 1.0 - base
            else:
                prob = base
        quality = 0.72 if home_form.get("verified") and away_form.get("verified") else 0.55
        return SportProjection(
            win_probability=float(max(0.05, min(0.95, prob))),
            expected_total=expected_total,
            home_strength=home_prob,
            away_strength=away_prob,
            quality=quality,
            notes=notes,
        )

    # Moneyline / spread: prefer explicit side, else infer from selection text.
    if is_home_selection is True:
        side_prob = home_prob
    elif is_home_selection is False:
        side_prob = away_prob
    else:
        side_prob = home_prob

    if "spread" in market or "run_line" in market or "handicap" in market:
        # Spread still anchored on win probability with a mild line adjustment.
        if line is not None:
            # Favorite (negative line) needs more margin; underdog gets lift.
            side_prob = side_prob - (float(line) / 40.0)
        side_prob = max(0.05, min(0.95, side_prob))

    quality = 0.78 if home_form.get("verified") and away_form.get("verified") else 0.58
    return SportProjection(
        win_probability=float(max(0.05, min(0.95, side_prob))),
        expected_total=expected_total,
        home_strength=home_prob,
        away_strength=away_prob,
        quality=quality,
        notes=notes,
    )


def _blend(primary: Any, secondary: Any, weight: float) -> float:
    p = float(primary) if primary is not None else None
    s = float(secondary) if secondary is not None else None
    if p is None and s is None:
        return 0.5
    if p is None:
        return float(s)
    if s is None:
        return float(p)
    return weight * p + (1.0 - weight) * s
