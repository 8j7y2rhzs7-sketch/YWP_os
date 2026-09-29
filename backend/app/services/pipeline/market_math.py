"""Stage 5 — market comparison with institutional de-vig (Shin/power/multiplicative)."""

from __future__ import annotations

from typing import Any

from app.services.ywp_quant.odds import (
    american_to_decimal,
    american_to_probability,
    devig_best,
    vig_proxy_fair,
)
from app.services.ywp_quant.odds import (
    expected_value as quant_ev,
)


def implied_from_american(odds: int) -> float:
    return american_to_probability(float(odds))


def devig_two_way(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Best de-vig for a two-way market. Returns fair probs for A and B."""
    a = devig_best(float(odds_a), float(odds_b))
    b = devig_best(float(odds_b), float(odds_a))
    return float(a["fair_probability"]), float(b["fair_probability"])


def compare_to_market(
    *,
    model_probability: float,
    american_odds: int,
    opposite_american_odds: int | None = None,
) -> dict[str, Any]:
    """Compare model fair p to market. Prefer Shin/best de-vig when opposite exists."""
    raw_implied = implied_from_american(american_odds)
    if opposite_american_odds is not None:
        details = devig_best(float(american_odds), float(opposite_american_odds))
        fair_implied = float(details["fair_probability"])
        status = f"devigged_{details.get('method', 'best')}"
        vig = float(details.get("overround") or 0.0)
        method_meta = {
            "method": details.get("method"),
            "shin_z": details.get("shin_z"),
            "alternatives": details.get("alternatives"),
        }
    else:
        details = vig_proxy_fair(float(american_odds))
        fair_implied = float(details["fair_probability"])
        status = "raw_implied_vig_proxy"
        vig = float(details.get("overround") or 0.0)
        method_meta = {"method": "vig_proxy"}

    edge = float(model_probability) - float(fair_implied)
    expected_value = quant_ev(float(model_probability), float(american_odds))
    return {
        "status": status,
        "raw_implied_probability": round(raw_implied, 6),
        "fair_implied_probability": round(fair_implied, 6),
        "model_probability": round(float(model_probability), 6),
        "edge_vs_fair": round(edge, 6),
        "expected_value": round(expected_value, 6),
        "vig_estimate": round(vig, 6) if vig is not None else None,
        "opposite_american_odds": opposite_american_odds,
        "devig": method_meta,
        "decimal_odds": american_to_decimal(float(american_odds)),
    }
