"""Decision Board metrics: weakest-leg selection, outliers, market labels, card risk.

Quality scores (confidence / YIS / card score) are NOT win probabilities.
Model win probability is adjusted_probability only when probability_source supports it.
"""

from __future__ import annotations

from typing import Any

from app.models import Recommendation

# Documented outlier thresholds (independent model vs market-implied break-even).
MAX_CLEAN_EDGE = 0.15
OUTLIER_PLUS_MONEY_MODEL_FLOOR = 0.75  # model ≥75% while price is plus-money
OUTLIER_EDGE_REVIEW = 0.15


def _implied_probability(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def market_scope_label(
    market_type: str, market_period: str = "full_game", *, sport: str | None = None
) -> str:
    period = (market_period or "full_game").lower()
    market = (market_type or "").lower()
    sport_l = (sport or "").lower()
    period_label = {
        "full_game": "Full game",
        "f5": "First 5 innings",
        "first_5": "First 5 innings",
        "1h": "1st half",
        "2h": "2nd half",
        "90_min": "90 minutes",
        "regulation": "Regulation",
    }.get(period, period.replace("_", " ").title())

    if "pitcher" in market or "strikeout" in market:
        kind = "Pitcher strikeouts"
    elif "team_total" in market or market.startswith("tt_"):
        kind = "Team total"
    elif "total" in market:
        kind = "Game total"
    elif "run_line" in market or (
        ("spread" in market or "handicap" in market)
        and sport_l in {"mlb", "baseball", "kbo"}
    ):
        kind = "Run line"
    elif "handicap" in market and sport_l in {"soccer", "mls", "epl", "football"}:
        kind = "Goal handicap"
    elif "spread" in market or "handicap" in market:
        kind = "Point spread"
    elif "moneyline" in market or market in {"h2h", "ml"}:
        kind = "Moneyline"
    else:
        kind = market.replace("_", " ").title() or "Market"
    return f"{period_label} · {kind}"


def bookmaker_display_name(book_key: str | None) -> str | None:
    if not book_key:
        return None
    key = book_key.strip().lower()
    labels = {
        "hardrockbet": "Hard Rock Bet",
        "draftkings": "DraftKings",
        "fanduel": "FanDuel",
        "betmgm": "BetMGM",
        "betrivers": "BetRivers",
        "pointsbetus": "PointsBet",
        "williamhill_us": "Caesars",
        "bovada": "Bovada",
    }
    return labels.get(key, book_key.replace("_", " ").title())


def parse_event_teams(event_name: str) -> tuple[str | None, str | None]:
    if " @ " in event_name:
        away, home = event_name.split(" @ ", 1)
        return away.strip() or None, home.strip() or None
    if " vs " in event_name.lower():
        parts = event_name.replace(" VS ", " vs ").split(" vs ", 1)
        if len(parts) == 2:
            return parts[0].strip() or None, parts[1].strip() or None
    return None, None


def verification_status_from_snapshot(snapshot: dict[str, Any] | None) -> str:
    snap = snapshot or {}
    readiness = str(snap.get("readiness") or "").upper()
    if readiness in {"DEMO", "PARTIAL", "VERIFIED"}:
        return readiness
    source = str(snap.get("probability_source") or snap.get("data_source") or "").lower()
    if "demo" in source or "synthetic" in source:
        return "DEMO"
    missing = snap.get("missing_fields") or []
    if missing:
        return "PARTIAL"
    return "VERIFIED" if snap.get("schedule_verified") else "PARTIAL"


def model_win_probability(
    *,
    adjusted_probability: float,
    probability_source: str | None,
) -> float | None:
    """Return model-estimated win probability only for independent/manual sources."""
    source = (probability_source or "").lower()
    if source in {"model", "manual_verified"}:
        return float(adjusted_probability)
    return None


def outlier_review_reasons(
    *,
    adjusted_probability: float,
    american_odds: int,
    probability_source: str | None,
) -> list[str]:
    """Flag unresolved extreme model-vs-price claims for REVIEW (not silent capping)."""
    reasons: list[str] = []
    source = (probability_source or "").lower()
    if source not in {"model", "manual_verified"}:
        return reasons
    implied = _implied_probability(american_odds)
    edge = adjusted_probability - implied
    if abs(edge) > OUTLIER_EDGE_REVIEW:
        reasons.append("OUTLIER_EDGE_REVIEW")
    # Plus-money price with very high model probability is a major discrepancy.
    if american_odds > 0 and adjusted_probability >= OUTLIER_PLUS_MONEY_MODEL_FLOOR:
        reasons.append("OUTLIER_PLUS_MONEY_PROBABILITY")
    # Model claims near-certainty while market is close to a coin flip.
    if adjusted_probability >= 0.85 and 0.42 <= implied <= 0.58:
        reasons.append("OUTLIER_NEAR_CERTAINTY_VS_MARKET")
    return list(dict.fromkeys(reasons))


def select_weakest_leg(
    legs: list[Recommendation],
) -> tuple[Recommendation, str, str]:
    """Pick one weakest leg with a documented criterion.

    Criterion (stable, backend-only):
    1. Lowest confidence_score (YWP quality score, not win %)
    2. Tie-break: lowest ywp_rating (YIS)
    3. Tie-break: highest miss_by_one_risk
    4. Tie-break: worse American price for the bettor (higher underdog / shorter favorite)
    5. Tie-break: recommendation id (stable)
    """
    if not legs:
        raise ValueError("Cannot select weakest leg from an empty card")

    def sort_key(item: Recommendation) -> tuple:
        odds = int(item.american_odds)
        # Higher sort value = weaker. For plus money, larger odds = longer shot = weaker.
        # For minus money, closer to even (e.g. -105 vs -200) is weaker.
        odds_weakness = float(odds) if odds > 0 else (1000 + odds)
        return (
            float(item.confidence_score),
            float(item.ywp_rating),
            -float(item.miss_by_one_risk),
            -odds_weakness,
            item.id,
        )

    weakest = min(legs, key=sort_key)
    tied = [
        item
        for item in legs
        if float(item.confidence_score) == float(weakest.confidence_score)
        and float(item.ywp_rating) == float(weakest.ywp_rating)
    ]
    if len(tied) > 1 and float(weakest.miss_by_one_risk) >= max(
        float(item.miss_by_one_risk) for item in tied
    ):
        criterion = "lowest_quality_then_yis_then_miss_by_one"
        explanation = (
            f"{weakest.selection} is weakest: tied quality "
            f"{weakest.confidence_score}/100 and YIS {float(weakest.ywp_rating):.2f}; "
            f"highest miss-by-1 risk {float(weakest.miss_by_one_risk):.2f}."
        )
    elif any(
        float(item.confidence_score) == float(weakest.confidence_score) and item.id != weakest.id
        for item in legs
    ):
        criterion = "lowest_quality_then_yis"
        explanation = (
            f"{weakest.selection} is weakest: quality tied at "
            f"{weakest.confidence_score}/100; lowest YIS "
            f"{float(weakest.ywp_rating):.2f} breaks the tie "
            f"(not American odds alone)."
        )
    else:
        criterion = "lowest_quality_score"
        explanation = (
            f"{weakest.selection} is weakest: lowest YWP quality score "
            f"{weakest.confidence_score}/100 "
            f"(YIS {float(weakest.ywp_rating):.2f}). "
            f"Quality score is not a win probability."
        )
    return weakest, criterion, explanation


def card_risk(
    legs: list[Recommendation],
) -> tuple[str, str]:
    """Documented card risk from uncertainty, leg count, volatility, miss-by-1."""
    if not legs:
        return "none", "No legs; PASS."
    risk_order = {"low": 0, "medium": 1, "medium_high": 2, "high": 3}
    base = max(legs, key=lambda item: risk_order.get(item.risk, 2)).risk
    reasons: list[str] = [f"Highest leg risk is {base}"]
    if len(legs) >= 4:
        base = "high" if base in {"medium_high", "high"} else "medium_high"
        reasons.append(f"{len(legs)} legs increase joint uncertainty")
    elif len(legs) >= 2 and base == "low":
        base = "medium"
        reasons.append("Multi-leg cards cannot stay Minimal/low")
    high_miss = sum(1 for item in legs if float(item.miss_by_one_risk) >= 0.55)
    if high_miss:
        if risk_order.get(base, 2) < risk_order["medium_high"]:
            base = "medium_high"
        reasons.append(f"{high_miss} elevated miss-by-1 leg(s)")
    avg_var = sum(float(item.variance) for item in legs) / len(legs)
    if avg_var >= 0.55 and risk_order.get(base, 2) < risk_order["medium_high"]:
        base = "medium_high"
        reasons.append(f"Average variance {avg_var:.2f}")
    # Same-event concentration
    events = {item.event_id for item in legs}
    if len(legs) >= 2 and len(events) < len(legs):
        if risk_order.get(base, 2) < risk_order["medium"]:
            base = "medium"
        reasons.append("Correlated same-event legs present")
    return base, "; ".join(reasons) + "."


def joint_win_probability_disclosure(legs: list[Recommendation]) -> dict[str, Any]:
    """Never invent a parlay win % from quality scores or by multiplying unchecked."""
    probs: list[float] = []
    for item in legs:
        snap = item.snapshot or {}
        source = snap.get("probability_source")
        value = model_win_probability(
            adjusted_probability=float(item.adjusted_probability),
            probability_source=str(source) if source else None,
        )
        if value is None:
            return {
                "joint_win_probability": None,
                "joint_probability_status": "unavailable",
                "joint_probability_note": (
                    "Joint win probability unavailable: one or more legs lack an "
                    "independent model win probability. Quality scores are not win odds."
                ),
            }
        probs.append(value)
    if len(probs) <= 1:
        return {
            "joint_win_probability": probs[0] if probs else None,
            "joint_probability_status": "single_leg" if probs else "unavailable",
            "joint_probability_note": (
                "Single-leg model win probability only. Not a parlay estimate."
                if probs
                else "No model win probability available."
            ),
        }
    events = {item.event_id for item in legs}
    if len(events) < len(legs):
        return {
            "joint_win_probability": None,
            "joint_probability_status": "unavailable_dependent_legs",
            "joint_probability_note": (
                "Joint estimate unavailable: legs share events/dependencies. "
                "Do not multiply leg probabilities."
            ),
        }
    product = 1.0
    for value in probs:
        product *= value
    return {
        "joint_win_probability": round(product, 6),
        "joint_probability_status": "independent_product_estimate",
        "joint_probability_note": (
            "Independent-legs product of model win probabilities only. "
            "Not verified; not derived from YIS or quality scores."
        ),
    }
