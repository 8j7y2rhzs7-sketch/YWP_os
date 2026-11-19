#!/usr/bin/env python3
"""NO-KILL ticket filter — align agent slips with app cash/fortress rules.

The app cash_builder/fortress already refuse miss_by_one_risk >= 0.55.
Agent chat tickets were stacking LOOKS-GOOD legs (5/7, exact clears, soft pads
as spine) and dying on one killer. This module is the shared hard filter.

Spine leg requirements:
  - L7 hits >= 6/7 (5/5 if n==5). 5/7 is NEVER spine.
  - Avg clear margin >= 1.5 (or min clear >= 0.5 with avg >= 2.0)
  - L7 avg MIN >= 24 when minutes present
  - Soft floors (REB/AST <= 1.5) banned from spine (pad slot only, max 1)
  - Season hit >= 75% when season_n >= 8 (dual-window)

Usage:
  from no_kill_ticket import filter_spine, build_no_kill_slip
"""
from __future__ import annotations

from dataclasses import dataclass, field


SOFT_SPINE_MAX = {
    "REB": 1.5,
    "AST": 1.5,
    "STL": 1.5,
    "BLK": 1.5,
    "3PT": 0.5,
}


@dataclass
class Leg:
    player: str
    stat: str
    line: float
    vals: list[float]
    athlete_id: str = ""
    game: str = ""
    team: str = ""
    mins: list[float] = field(default_factory=list)
    season_hits: int | None = None
    season_n: int | None = None
    label: str = ""


@dataclass
class Verdict:
    ok: bool
    role: str  # spine | pad | reject
    reasons: list[str]
    hits: int
    n: int
    avg_margin: float
    min_margin: float


def _hit_rate(vals: list[float], line: float) -> tuple[int, int]:
    usable = [v for v in vals if v is not None]
    return sum(1 for v in usable if v > line), len(usable)


def grade_leg(leg: Leg, *, as_pad: bool = False) -> Verdict:
    reasons: list[str] = []
    h, n = _hit_rate(leg.vals, leg.line)
    if n < 5:
        return Verdict(False, "reject", [f"n={n}<5"], h, n, 0.0, 0.0)

    clears = [v - leg.line for v in leg.vals if v > leg.line]
    avg_m = sum(clears) / len(clears) if clears else -999.0
    min_m = min(clears) if clears else -999.0

    # Hit gate
    keep = (n >= 7 and h >= 6) or (n == 5 and h == 5) or (n == 6 and h == 6)
    if not keep:
        reasons.append(f"L7 {h}/{n} below spine (need 6/7+)")
        return Verdict(False, "reject", reasons, h, n, avg_m, min_m)

    # Soft floor
    soft_cap = SOFT_SPINE_MAX.get(leg.stat.upper())
    if soft_cap is not None and leg.line <= soft_cap:
        if as_pad:
            return Verdict(True, "pad", ["soft pad only"], h, n, avg_m, min_m)
        reasons.append(f"soft floor {leg.stat} O{leg.line} banned from spine")
        return Verdict(False, "reject", reasons, h, n, avg_m, min_m)

    # Cushion / miss-by-1 proxy
    if avg_m < 1.5 and not (min_m >= 0.5 and avg_m >= 2.0):
        reasons.append(f"thin cushion avg_margin={avg_m:.2f} min={min_m:.2f}")
        return Verdict(False, "reject", reasons, h, n, avg_m, min_m)

    # Minutes
    if leg.mins:
        avg_min = sum(leg.mins[:7]) / len(leg.mins[:7])
        if avg_min < 24:
            reasons.append(f"mpg={avg_min:.1f}<24")
            return Verdict(False, "reject", reasons, h, n, avg_m, min_m)

    # Dual-window
    if leg.season_n and leg.season_n >= 8 and leg.season_hits is not None:
        season_pct = leg.season_hits / leg.season_n
        if season_pct < 0.75:
            reasons.append(f"season {leg.season_hits}/{leg.season_n}={season_pct:.0%}<75%")
            return Verdict(False, "reject", reasons, h, n, avg_m, min_m)

    return Verdict(True, "spine", ["PASS no-kill"], h, n, avg_m, min_m)


def filter_spine(legs: list[Leg]) -> tuple[list[tuple[Leg, Verdict]], list[tuple[Leg, Verdict]]]:
    keep: list[tuple[Leg, Verdict]] = []
    dead: list[tuple[Leg, Verdict]] = []
    for leg in legs:
        v = grade_leg(leg, as_pad=False)
        (keep if v.ok else dead).append((leg, v))
    return keep, dead


def build_no_kill_slip(
    spine_candidates: list[Leg],
    *,
    pad_candidates: list[Leg] | None = None,
    max_legs: int = 5,
    allow_one_pad: bool = True,
) -> dict:
    spine, rejected = filter_spine(spine_candidates)
    # Prefer bigger cushion then higher line
    spine.sort(key=lambda x: (-x[1].avg_margin, -x[0].line))
    picked: list[dict] = []
    used_players: set[str] = set()
    for leg, v in spine:
        if leg.player in used_players:
            continue
        picked.append(
            {
                "player": leg.player,
                "stat": leg.stat,
                "line": leg.line,
                "role": "spine",
                "hits": f"{v.hits}/{v.n}",
                "avg_margin": round(v.avg_margin, 2),
                "id": leg.athlete_id,
                "game": leg.game,
                "vals": leg.vals,
            }
        )
        used_players.add(leg.player)
        if len(picked) >= max_legs - (1 if allow_one_pad and pad_candidates else 0):
            break

    pad_out = None
    if allow_one_pad and pad_candidates and len(picked) < max_legs:
        for leg in pad_candidates:
            if leg.player in used_players:
                continue
            v = grade_leg(leg, as_pad=True)
            if v.ok and v.role == "pad":
                pad_out = {
                    "player": leg.player,
                    "stat": leg.stat,
                    "line": leg.line,
                    "role": "pad",
                    "hits": f"{v.hits}/{v.n}",
                    "avg_margin": round(v.avg_margin, 2),
                    "id": leg.athlete_id,
                    "game": leg.game,
                    "vals": leg.vals,
                }
                picked.append(pad_out)
                break

    return {
        "legs": picked,
        "rejected": [
            {
                "player": leg.player,
                "stat": leg.stat,
                "line": leg.line,
                "reasons": v.reasons,
                "hits": f"{v.hits}/{v.n}",
            }
            for leg, v in rejected[:40]
        ],
        "rule": "spine=L7>=6/7 + cushion>=1.5 + mpg>=24; soft floors pad-only; no 5/7 spine",
    }


if __name__ == "__main__":
    # smoke
    demo = [
        Leg("Bam", "REB", 7.5, [14, 8, 8, 10, 10, 9, 9], mins=[35] * 7),
        Leg("Thin", "PTS", 20.5, [21, 21, 22, 19, 21, 18, 21], mins=[30] * 7),
        Leg("Pad", "REB", 1.5, [3, 2, 4, 2, 3, 2, 5], mins=[28] * 7),
    ]
    print(build_no_kill_slip(demo[:2], pad_candidates=demo[2:]))
