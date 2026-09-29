"""Weekly-report lessons encoded as calculation gates — not pick-generator heuristics.

YWP operates as a calculation engine. A play with good facts can still fail if the
market, threshold, card, or leg combination is wrong. These helpers return explicit
blocker codes; callers hard-REJECT / WAIT / quarantine. They never invent evidence.
"""

from __future__ import annotations

from statistics import median
from typing import Any

# Lesson 11 — heavy juice is not evidence of safety.
HEAVY_JUICE_THRESHOLD = -200
# Minimum independent model edge required to keep a heavily juiced price.
HEAVY_JUICE_MIN_EDGE = 0.04

# Lesson 2 — market-specific series must clear the offered line.
PROP_MEDIAN_MIN_CLEAR = 0.25  # median must beat line by this (in market units)

# Lesson 8 — card evidence floors (numerical thresholds still tuning; start conservative).
CARD_STANDARDS: dict[str, dict[str, float | int]] = {
    # Max Bet = strongest single already selected by rank; do not re-floor confidence.
    "max_bet": {"max_miss_by_one": 0.80},
    "fortress": {
        "max_miss_by_one": 0.45,
        "min_confidence": 80,
        "min_market_families": 2,
        "min_legs": 2,
    },
    "no_stress": {
        "max_miss_by_one": 0.40,
        "max_variance": 0.35,
        "min_confidence": 80,
        "min_legs": 2,
    },
    "scripted": {
        "max_miss_by_one": 0.50,
        "min_script_alignment": 0.55,
        "min_legs": 2,
    },
    "cash_builder": {"max_miss_by_one": 0.45, "min_confidence": 80},
    "quick_cash": {"max_miss_by_one": 0.45, "min_confidence": 75},
}

# Lesson 9 — drop weakest ticket-killers, then re-check the new weakest.
# Confidence alone does not kill a card (board rank #1 can be 72–80); miss-by-1 does.
WEAKEST_FLOOR_MISS = 0.55

# Lesson 6 — same-player category families that must not stack as one thesis.
_CATEGORY_FAMILY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("pitcher_k", ("strikeout", "pitcher_strikeouts", "player_strikeouts")),
    ("pitcher_er", ("earned_run", "pitcher_er", "allowed_er", "player_earned")),
    ("pitcher_hits", ("hits_allowed", "pitcher_hits", "allowed_hits")),
    ("pitcher_outs", ("outs_recorded", "pitcher_outs", "pitcher_out")),
    ("player_points", ("player_points", "points_over", "points_under")),
    ("player_rebounds", ("player_rebounds", "rebounds_over", "rebounds_under")),
    ("player_assists", ("player_assists", "assists_over", "assists_under")),
    ("player_threes", ("player_threes", "three_pointers", "3pt")),
    ("player_pra", ("points_rebounds_assists", "pra_", "player_pra")),
]


def market_family(market_type: str | None) -> str:
    text = str(market_type or "").lower()
    for family, tokens in _CATEGORY_FAMILY_RULES:
        if any(token in text for token in tokens):
            return family
    if text.startswith("player_") or text.startswith("pitcher_") or text.startswith("batter_"):
        return text.rsplit("_", 1)[0] if "_" in text else text
    if "spread" in text or "handicap" in text or "run_line" in text:
        return "spread"
    if "total" in text:
        return "total"
    if "moneyline" in text or text in {"h2h", "ml"}:
        return "moneyline"
    return text or "unknown"


def is_modeled_prop_market(sport: str | None, market_type: str | None) -> bool:
    sport_l = str(sport or "").lower()
    market_l = str(market_type or "").lower()
    if sport_l not in {"wnba", "nba", "basketball", "nfl", "ncaaf", "mlb"}:
        return False
    return (
        market_l.startswith("player_")
        or market_l.startswith("pitcher_")
        or market_l.startswith("batter_")
        or "strikeout" in market_l
    )


def identity_blockers(candidate: Any) -> list[str]:
    """Lesson 1 — bad identity contaminates every downstream statistic."""
    blockers: list[str] = []
    sport = str(getattr(candidate, "sport", "") or "").lower()
    market = str(getattr(candidate, "market_type", "") or "").lower()
    if is_modeled_prop_market(sport, market):
        player_key = getattr(candidate, "player_key", None)
        if not player_key or str(player_key).strip().lower() in {"", "none", "unknown", "null"}:
            blockers.append("IDENTITY_PLAYER_KEY_MISSING")
        # Selection must not be a bare team market masquerading as a prop.
        selection = str(getattr(candidate, "selection", "") or "").strip()
        if len(selection) < 3:
            blockers.append("IDENTITY_SELECTION_TOO_THIN")
    event_name = str(getattr(candidate, "event_name", "") or "")
    if not event_name or len(event_name.strip()) < 3:
        blockers.append("IDENTITY_EVENT_MISSING")
    return blockers


def market_series_blockers(candidate: Any) -> list[str]:
    """Lesson 2 — exact market L5/L10 / median / distance from line, not general form."""
    if not is_modeled_prop_market(
        getattr(candidate, "sport", None), getattr(candidate, "market_type", None)
    ):
        return []
    blockers: list[str] = []
    values = getattr(candidate, "observation_values", None)
    if not values:
        snap = getattr(candidate, "snapshot", None) or {}
        if isinstance(snap, dict):
            values = snap.get("observation_values") or snap.get("l10_values")
    line = getattr(candidate, "line", None)
    direction = str(getattr(candidate, "selection", "") or "").lower()
    is_under = (
        " under" in f" {direction} "
        or direction.endswith(" under")
        or "_under" in str(getattr(candidate, "market_type", "") or "").lower()
    )

    has_hit_rate = getattr(candidate, "recent_hit_rate", None) is not None
    has_cushion = getattr(candidate, "average_cushion", None) is not None
    if not values and not (has_hit_rate and has_cushion):
        blockers.append("MARKET_SERIES_MISSING")
        return blockers

    if values and line is not None:
        try:
            nums = [float(v) for v in values]
            line_f = float(line)
        except (TypeError, ValueError):
            blockers.append("MARKET_SERIES_UNPARSEABLE")
            return blockers
        if len(nums) < 5:
            blockers.append("MARKET_SERIES_TOO_SHORT")
        med = float(median(nums))
        clear = (line_f - med) if is_under else (med - line_f)
        if clear < PROP_MEDIAN_MIN_CLEAR:
            blockers.append("MARKET_MEDIAN_DOES_NOT_CLEAR_LINE")
    return blockers


def heavy_juice_blockers(
    *,
    american_odds: int,
    edge: float,
    independent_value_verified: bool,
    heavily_juiced_filler: bool = False,
) -> list[str]:
    """Lesson 11 — short price / heavy juice is not safety."""
    juice_price = int(american_odds) <= HEAVY_JUICE_THRESHOLD
    if not juice_price and not heavily_juiced_filler:
        return []
    if independent_value_verified and float(edge) >= HEAVY_JUICE_MIN_EDGE:
        return []
    return ["HEAVY_JUICE_NOT_SAFETY"]


def line_shave_blockers(candidate: Any) -> list[str]:
    """Lesson 3 — shorter line is not automatically safer without distribution evidence."""
    base = getattr(candidate, "base_line", None)
    line = getattr(candidate, "line", None)
    if base is None or line is None:
        return []
    try:
        base_f = float(base)
        line_f = float(line)
    except (TypeError, ValueError):
        return []
    market = str(getattr(candidate, "market_type", "") or "").lower()
    is_under = "_under" in market or " under" in str(getattr(candidate, "selection", "")).lower()
    # "Shorter" for an over = lower line; for an under = higher line (easier).
    shaved = (line_f < base_f) if not is_under else (line_f > base_f)
    if not shaved:
        return []
    if bool(getattr(candidate, "alt_line_approved", False)):
        # Still require market series / cushion — approval alone is not distribution.
        if getattr(candidate, "average_cushion", None) is None and not getattr(
            candidate, "observation_values", None
        ):
            return ["LINE_SHAVE_WITHOUT_DISTRIBUTION"]
        return []
    return ["LINE_SHAVE_WITHOUT_DISTRIBUTION"]


def protective_dog_spread_blockers(candidate: Any) -> list[str]:
    """Lesson 12 — protective underdog spreads need an affirmative case."""
    market = str(getattr(candidate, "market_type", "") or "").lower()
    if not any(token in market for token in ("spread", "handicap", "run_line")):
        return []
    odds = int(getattr(candidate, "american_odds", 0) or 0)
    if odds <= 0:
        return []  # favorite / even — not the protective-dog pattern
    matchup = getattr(candidate, "matchup_score", None)
    script = getattr(candidate, "script_alignment", None)
    cushion = getattr(candidate, "average_cushion", None)
    affirmative = (
        (matchup is not None and float(matchup) >= 0.58)
        or (script is not None and float(script) >= 0.60)
        or (cushion is not None and float(cushion) > 0)
    )
    if affirmative:
        return []
    return ["PROTECTIVE_DOG_WITHOUT_AFFIRMATIVE_CASE"]


def minutes_not_production_blockers(candidate: Any) -> list[str]:
    """Lesson 4 — minutes are opportunity, not production. Cap volume props without role."""
    if not is_modeled_prop_market(
        getattr(candidate, "sport", None), getattr(candidate, "market_type", None)
    ):
        return []
    market = str(getattr(candidate, "market_type", "") or "").lower()
    volume_tokens = (
        "points",
        "rebounds",
        "assists",
        "pra",
        "threes",
        "yards",
        "receptions",
        "rush",
        "pass",
    )
    if not any(token in market for token in volume_tokens):
        return []
    role = getattr(candidate, "role_stability", None)
    # Missing or default-ish role → do not allow official PLAY quality; WAIT path.
    if role is None:
        return ["MINUTES_WITHOUT_PRODUCTION_EVIDENCE"]
    return []


def same_player_category_conflicts(legs: list[Any]) -> list[str]:
    """Lesson 6 — K dominance ≠ ER; points form ≠ rebounds form on the same ticket."""
    by_player: dict[str, set[str]] = {}
    for item in legs:
        player = getattr(item, "player_key", None)
        if not player:
            continue
        family = market_family(getattr(item, "market_type", None))
        by_player.setdefault(str(player), set()).add(family)
    conflicts: list[str] = []
    pitcher_bundle = {"pitcher_k", "pitcher_er", "pitcher_hits", "pitcher_outs"}
    volume_bundle = {
        "player_points",
        "player_rebounds",
        "player_assists",
        "player_threes",
        "player_pra",
    }
    for player, families in by_player.items():
        if len(families & pitcher_bundle) >= 2:
            conflicts.append(f"SAME_PLAYER_CATEGORY_STACK:{player}:pitcher")
        if len(families & volume_bundle) >= 2:
            conflicts.append(f"SAME_PLAYER_CATEGORY_STACK:{player}:volume")
    return conflicts


def eliminate_weakest_until_stable(
    legs: list[Any],
    *,
    min_legs: int,
    select_weakest,
) -> tuple[list[Any], list[str]]:
    """Lesson 9 — weakest-leg check, drop ticket-killers, re-check the new weakest."""
    kept = list(legs)
    notes: list[str] = []
    while len(kept) > min_legs:
        weakest, criterion, explanation = select_weakest(kept)
        miss = float(getattr(weakest, "miss_by_one_risk", 0) or 0)
        if miss < WEAKEST_FLOOR_MISS:
            break
        notes.append(
            f"Dropped weakest leg ({getattr(weakest, 'selection', weakest.id)}): "
            f"{explanation} [{criterion}]"
        )
        kept = [item for item in kept if item.id != weakest.id]
    # Final re-check: if the remaining weakest is still a ticket-killer, empty the card.
    if kept:
        weakest, _criterion, explanation = select_weakest(kept)
        miss = float(getattr(weakest, "miss_by_one_risk", 0) or 0)
        if miss >= WEAKEST_FLOOR_MISS:
            notes.append(
                f"Card rejected after weakest-leg re-check: {explanation}. No filler legs added."
            )
            return [], notes
    return kept, notes


def card_standard_blockers(card_key: str, legs: list[Any]) -> list[str]:
    """Lesson 8 — Fortress / Max Bet / No Stress / Scripted need different evidence."""
    std = CARD_STANDARDS.get(card_key)
    if not std or not legs:
        return []
    blockers: list[str] = []
    max_miss = std.get("max_miss_by_one")
    if max_miss is not None:
        for item in legs:
            if float(getattr(item, "miss_by_one_risk", 0) or 0) >= float(max_miss):
                blockers.append(f"CARD_STANDARD_MISS_BY_ONE:{card_key}")
                break
    min_conf = std.get("min_confidence")
    if min_conf is not None:
        for item in legs:
            if float(getattr(item, "confidence_score", 0) or 0) < float(min_conf):
                blockers.append(f"CARD_STANDARD_CONFIDENCE:{card_key}")
                break
    max_var = std.get("max_variance")
    if max_var is not None:
        for item in legs:
            if float(getattr(item, "variance", 0) or 0) > float(max_var):
                blockers.append(f"CARD_STANDARD_VARIANCE:{card_key}")
                break
    min_script = std.get("min_script_alignment")
    if min_script is not None:
        for item in legs:
            snap = getattr(item, "snapshot", None) or {}
            script = snap.get("script_alignment") if isinstance(snap, dict) else None
            if script is None:
                script = getattr(item, "script_alignment", None)
            if script is None or float(script) < float(min_script):
                blockers.append(f"CARD_STANDARD_SCRIPT:{card_key}")
                break
    min_families = std.get("min_market_families")
    if min_families is not None:
        families = {market_family(getattr(item, "market_type", None)) for item in legs}
        if len(families) < int(min_families):
            blockers.append(f"CARD_STANDARD_DIVERSITY:{card_key}")
    return list(dict.fromkeys(blockers))


def wait_reasons(candidate: Any, hard_skip_reasons: list[str]) -> list[str]:
    """Lesson 13 — WAIT / NO PICK YET when evidence is incomplete, not a forced SKIP story."""
    reasons: list[str] = []
    codes = set(getattr(candidate, "reason_codes", None) or [])
    if "RESEARCH_INCOMPLETE" in codes or any(
        "required research" in r.lower() for r in hard_skip_reasons
    ):
        reasons.append("WAIT_RESEARCH_INCOMPLETE")
    if "MINUTES_WITHOUT_PRODUCTION_EVIDENCE" in hard_skip_reasons or any(
        "MINUTES_WITHOUT" in r for r in hard_skip_reasons
    ):
        reasons.append("WAIT_PRODUCTION_EVIDENCE")
    if "MARKET_SERIES_MISSING" in hard_skip_reasons:
        reasons.append("WAIT_MARKET_SERIES")
    return reasons


def official_output_label(*, has_qualified_cards: bool, has_play_lean: bool) -> str:
    """Lesson 15 — final output is Decision Cards or explicit NO BET."""
    if has_qualified_cards and has_play_lean:
        return "DECISION_CARDS"
    if has_play_lean and not has_qualified_cards:
        return "NO_BET_CARDS_FAILED_GATES"
    return "NO_BET"
