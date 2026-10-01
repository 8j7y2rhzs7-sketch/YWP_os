"""Verdict ladder shared with the sports engine.

Thresholds match ``DecisionEngine.evaluate`` (PLAY / LEAN / WATCH / REVIEW /
WAIT / SKIP). Sports code is not switched over to this module, so existing
sports outputs stay on the original path. Markets mode calls these functions.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.services.ywp_quant.sizing import fractional_kelly

PLAY_CONFIDENCE = 85
PLAY_EDGE = 0.03
LEAN_CONFIDENCE = 75
WATCH_CONFIDENCE = 70

# Codes that force SKIP when a hard gate has already fired.
# NO_CLEAN_EDGE is fatal in the sports engine, so a thin edge cannot become WAIT.
DEFAULT_FATAL_CODES = frozenset(
    {
        "IDENTITY_PLAYER_KEY_MISSING",
        "IDENTITY_SELECTION_TOO_THIN",
        "IDENTITY_EVENT_MISSING",
        "HEAVY_JUICE_NOT_SAFETY",
        "FILLER_LEG_TAX",
        "PROTECTIVE_DOG_WITHOUT_AFFIRMATIVE_CASE",
        "LINE_SHAVE_WITHOUT_DISTRIBUTION",
        "MARKET_MEDIAN_DOES_NOT_CLEAR_LINE",
        "MARKET_SERIES_TOO_SHORT",
        "MARKET_SERIES_UNPARSEABLE",
        "PROP_THIN_CLOSE_GATE",
        "PROP_CUSHION_GATE",
        "MISS_BY_ONE_GATE_FAILED",
        "NO_CLEAN_EDGE",
        "ODDS_TOO_EXPENSIVE",
        "DEMO_DATA",
        "NO_INDEPENDENT_PROBABILITY",
        "DATA_QUALITY_BAD",
        "GAME_NOT_PRE_GAME",
        "MARKET_NOT_OPEN",
        "FIRST_START_BACK_EXCLUSION",
        "K_DURATION_GATE_FAILED",
        "LINE_ESCALATION_BLOCKED",
        "LOW_TOTAL_TWO_PATH_GATE_FAILED",
        "PREVIOUS_GAME_RECENCY_BLOCK",
        "EXTRA_TIME_TRAP",
        "STALE_DATA",
        "STALE_PRICE",
        "SOURCE_DISAGREEMENT",
        "THIN_BOOK",
        "THIN_VOLUME",
        "THIN_LIQUIDITY",
        "BRACKET_INVALID",
        "PAIR_NOT_WHITELISTED",
        "VENUE_DISABLED",
        "SPOT_ONLY",
    }
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def edge_class_label(edge: float, confidence: int, reasons: list[str]) -> str:
    """Magnitude label. Unresolved outliers are not Strong or Elite.

    Same bands as ``decision_engine._edge_class_label``.
    """
    if any(code == "MODEL_EDGE_QUARANTINE" or code.startswith("OUTLIER_") for code in reasons):
        return "Outlier"
    if edge >= 0.08 and confidence >= 90:
        return "Elite"
    if edge >= 0.05:
        return "Strong"
    if edge >= 0.03:
        return "Moderate"
    if edge >= settings.minimum_edge:
        return "Marginal"
    return "No Edge"


@dataclass(frozen=True)
class VerdictAssignment:
    decision: str
    confidence: int
    edge_class: str
    tier: str
    suggested_stake_pct: float
    reason_codes: list[str]
    warnings: list[str]
    risk: str


def assign_verdict(
    *,
    edge: float,
    expected_value: float,
    confidence: int,
    reasons: list[str] | None = None,
    hard_skip_reasons: list[str] | None = None,
    review_reasons: list[str] | None = None,
    wait_codes: list[str] | None = None,
    variance: float = 0.35,
    quality: float = 0.8,
    american_odds: float = -110,
    risk_profile: str = "balanced",
    miss_by_one_risk: float = 0.40,
    fatal_codes: frozenset[str] | set[str] | None = None,
) -> VerdictAssignment:
    """Assign PLAY / LEAN / WATCH / REVIEW / WAIT / SKIP using sports thresholds.

    Fees must already be inside ``edge`` and ``expected_value``. This function
    does not look at a market price and will not invent a probability.
    """
    reason_codes = list(dict.fromkeys(reasons or []))
    hard = list(hard_skip_reasons or [])
    review = list(review_reasons or [])
    waits = list(dict.fromkeys(wait_codes or []))
    warnings: list[str] = []

    if edge < settings.minimum_edge or expected_value <= 0:
        hard.append("Current price does not provide a clean positive edge.")
        reason_codes.extend(["NO_CLEAN_EDGE", "ODDS_TOO_EXPENSIVE"])

    confidence = int(clamp(confidence, 35, 97))
    fatal = DEFAULT_FATAL_CODES if fatal_codes is None else set(fatal_codes)
    has_fatal = bool(set(reason_codes) & set(fatal))
    if hard and has_fatal:
        decision = "SKIP"
        confidence = min(confidence, 69)
    elif hard and waits and not has_fatal:
        decision = "WAIT"
        confidence = min(confidence, 72)
        reason_codes.extend(waits)
        reason_codes.append("NO_PICK_YET")
        warnings.append("WAIT — evidence incomplete. Correct output can be NO BET.")
    elif hard:
        decision = "SKIP"
        confidence = min(confidence, 69)
    elif review:
        decision = "REVIEW"
        confidence = min(confidence, 80)
        warnings.extend(review)
    elif confidence >= PLAY_CONFIDENCE and edge >= PLAY_EDGE:
        decision = "PLAY"
    elif confidence >= LEAN_CONFIDENCE and edge >= settings.minimum_edge:
        decision = "LEAN"
    elif confidence >= WATCH_CONFIDENCE:
        decision = "WATCH"
    else:
        decision = "SKIP"
        reason_codes.append("CONFIDENCE_BELOW_THRESHOLD")

    volatility = variance + (1 - quality) * 0.5
    if abs(american_odds) >= 300 or volatility >= 0.72:
        risk = "high"
    elif volatility >= 0.48:
        risk = "medium_high"
    elif volatility >= 0.30:
        risk = "medium"
    else:
        risk = "low"

    if decision == "SKIP":
        tier = "stay_away"
    elif decision == "WAIT":
        tier = "wait"
    elif decision == "REVIEW":
        tier = "review"
    elif confidence >= 90 and risk == "low" and miss_by_one_risk < 0.55:
        tier = "cash_builder"
    elif confidence >= 88 and miss_by_one_risk < 0.55 and risk in {"low", "medium"}:
        tier = "core_parlay"
    elif expected_value >= 0.08:
        tier = "edge_play"
    else:
        tier = "support"

    if decision in {"SKIP", "REVIEW", "WAIT"}:
        suggested = 0.0
    elif confidence >= 92 and risk in {"low", "medium"}:
        suggested = 0.02
    elif confidence >= 85:
        suggested = 0.0125
    else:
        suggested = 0.005
    if risk_profile == "conservative":
        suggested *= 0.75
    elif risk_profile == "aggressive":
        suggested = min(0.025, suggested * 1.15)

    edge_class = edge_class_label(edge, confidence, reason_codes)
    warnings.extend(hard)
    return VerdictAssignment(
        decision=decision,
        confidence=confidence,
        edge_class=edge_class,
        tier=tier,
        suggested_stake_pct=round(suggested, 6),
        reason_codes=list(dict.fromkeys(reason_codes)),
        warnings=list(dict.fromkeys(warnings)),
        risk=risk,
    )


def quarter_kelly_stake(
    probability: float,
    american_odds: float,
    *,
    lower_90: float | None = None,
    fraction: float = 0.25,
) -> dict[str, object]:
    """Quarter-Kelly on the downside probability. Same helper the sports quant uses."""
    return fractional_kelly(
        probability,
        american_odds,
        fraction=fraction,
        lower_90=lower_90,
        uncertainty_haircut=lower_90 is not None,
    )
